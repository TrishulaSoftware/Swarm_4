#!/usr/bin/env python3
"""
TRISHULA -- OCI SDK SETUP + AI SERVICES WIRING
================================================
Run after you have:
  1. Your Tenancy OCID  (profile -> Tenancy -> copy OCID)
  2. Your User OCID     (profile -> My Profile -> copy OCID)
  3. Your OCI API key   (profile -> My Profile -> API Keys -> generate)

Usage:
  python setup_oci_sdk.py --tenancy <OCID> --user <OCID> --region us-ashburn-1

This script:
  1. Creates ~/.oci/config
  2. Generates a new API key pair
  3. Tests Vision, Language, Document Understanding, Anomaly Detection
  4. Prints the public key to paste in OCI console
"""

import os, sys, argparse, subprocess
from pathlib import Path

OCI_DIR    = Path.home() / ".oci"
CONFIG_PATH = OCI_DIR / "config"
KEY_PATH    = OCI_DIR / "trishula_oci_key.pem"
PUB_PATH    = OCI_DIR / "trishula_oci_key_public.pem"

def generate_keys():
    """Generate RSA key pair for OCI API authentication."""
    OCI_DIR.mkdir(exist_ok=True)
    if KEY_PATH.exists():
        print(f"  [OK] Key already exists: {KEY_PATH}")
        return
    print("  Generating RSA key pair...")
    subprocess.run([
        "openssl", "genrsa", "-out", str(KEY_PATH), "2048"
    ], check=True, capture_output=True)
    subprocess.run([
        "openssl", "rsa", "-pubout",
        "-in",  str(KEY_PATH),
        "-out", str(PUB_PATH)
    ], check=True, capture_output=True)
    # Set permissions (Windows-compatible best effort)
    try:
        os.chmod(KEY_PATH, 0o600)
    except Exception:
        pass
    print(f"  [OK] Private key: {KEY_PATH}")
    print(f"  [OK] Public key:  {PUB_PATH}")

def write_config(tenancy: str, user: str, region: str, fingerprint: str = "PENDING"):
    """Write the OCI config file."""
    OCI_DIR.mkdir(exist_ok=True)
    config_text = f"""[DEFAULT]
user={user}
tenancy={tenancy}
region={region}
key_file={KEY_PATH}
fingerprint={fingerprint}
"""
    CONFIG_PATH.write_text(config_text)
    print(f"  [OK] OCI config written: {CONFIG_PATH}")

def test_oci_services(tenancy: str, region: str):
    """Test all 4 OCI AI Services."""
    try:
        import oci
    except ImportError:
        print("  [!] oci SDK not installed. Run: pip install oci")
        return

    print("\n  Testing OCI AI Services...")
    config = oci.config.from_file()

    # Vision
    try:
        vision = oci.ai_vision.AIServiceVisionClient(config)
        print("  [PASS] OCI Vision: SDK initialized")
    except Exception as e:
        print(f"  [FAIL] OCI Vision: {e}")

    # Language
    try:
        lang = oci.ai_language.AIServiceLanguageClient(config)
        # Quick sentiment test
        compartment = tenancy  # root compartment
        result = lang.detect_language_sentiments(
            oci.ai_language.models.DetectLanguageSentimentsDetails(
                text="NVDA crushed earnings — massive bullish momentum confirmed."
            )
        )
        sentiment = result.data.aspects[0].sentiment if result.data.aspects else "UNKNOWN"
        print(f"  [PASS] OCI Language: sentiment={sentiment}")
    except Exception as e:
        print(f"  [FAIL] OCI Language: {e}")

    # Document Understanding
    try:
        doc = oci.ai_document.AIServiceDocumentClient(config)
        print("  [PASS] OCI Document Understanding: SDK initialized")
    except Exception as e:
        print(f"  [FAIL] OCI Document Understanding: {e}")

    # Anomaly Detection
    try:
        anom = oci.ai_anomaly_detection.AnomalyDetectionClient(config)
        print("  [PASS] OCI Anomaly Detection: SDK initialized")
    except Exception as e:
        print(f"  [FAIL] OCI Anomaly Detection: {e}")

def main():
    parser = argparse.ArgumentParser(description="OCI SDK Setup")
    parser.add_argument("--tenancy", required=True, help="Tenancy OCID")
    parser.add_argument("--user",    required=True, help="User OCID")
    parser.add_argument("--region",  default="us-ashburn-1")
    parser.add_argument("--fingerprint", default="PENDING", help="Key fingerprint (after uploading public key to OCI)")
    parser.add_argument("--test", action="store_true", help="Only run service tests (config already written)")
    args = parser.parse_args()

    if not args.test:
        print("\n[1/3] Generating OCI API key pair...")
        generate_keys()

        print("\n[2/3] Writing OCI config...")
        write_config(args.tenancy, args.user, args.region, args.fingerprint)

        print("\n[3/3] PUBLIC KEY -- Paste this in OCI Console:")
        print("  Profile -> My Profile -> API Keys -> Add API Key -> Paste public key")
        print()
        print(PUB_PATH.read_text() if PUB_PATH.exists() else "  [Key not generated yet]")

    print("\n[TEST] Running OCI AI Service connectivity tests...")
    test_oci_services(args.tenancy, args.region)

    print("\n  NEXT: Paste the public key above into OCI Console -> My Profile -> API Keys")
    print("  Then re-run with --fingerprint <fingerprint shown in OCI after upload>\n")

if __name__ == "__main__":
    main()
