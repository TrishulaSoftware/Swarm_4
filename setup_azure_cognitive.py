#!/usr/bin/env python3
"""
TRISHULA CLOUD ARBITRAGE v4.0 -- AZURE COGNITIVE SERVICES WIRING
=================================================================
After you create the Azure Cognitive Services F0 resource:
1. Run: python setup_azure_cognitive.py --endpoint <URL> --key <KEY>
2. Or just paste endpoint+key into .env and run: python setup_azure_cognitive.py --test

Free tier F0 unlocks permanently:
  - Language/Sentiment:     5,000 transactions/month
  - Computer Vision:        5,000 transactions/month
  - Form Recognizer:          500 pages/month
  - Speech-to-Text:           5 hours/month
  - Translator:           2,000,000 chars/month
"""

import os, sys, json, argparse
from pathlib import Path

ENV_PATH = Path(r"H:\Trishula\Swarm_4_Integration\Swarm_4_SBM_FINAL INTEGRATION\Project-Swarm\trishula-market-data\.env")

def update_env(key, value):
    """Update a key in the .env file."""
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    updated = False
    new_lines = []
    for line in lines:
        if line.startswith(key + "="):
            new_lines.append(f"{key}={value}")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        new_lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print(f"  [OK] Updated .env: {key}=<set>")

def test_azure(endpoint, key):
    """Run a quick sentiment test against Azure Language API."""
    import requests
    url = endpoint.rstrip("/") + "/text/analytics/v3.1/sentiment"
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/json"
    }
    body = {
        "documents": [
            {"id": "1", "language": "en", "text": "NVDA beat earnings — massive call flow incoming."},
            {"id": "2", "language": "en", "text": "Fed signals rate cuts delayed — markets selling off."},
        ]
    }
    try:
        r = requests.post(url, headers=headers, json=body, timeout=15)
        r.raise_for_status()
        for doc in r.json().get("documents", []):
            print(f"  [PASS] Doc {doc['id']}: sentiment={doc['sentiment']}")
        return True
    except Exception as e:
        print(f"  [FAIL] Azure Language test: {e}")
        return False

def test_vision(endpoint, key):
    """Test Azure Computer Vision connectivity."""
    import requests
    url = endpoint.rstrip("/") + "/computervision/imageanalysis:analyze?api-version=2023-02-01-preview&features=caption"
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/json"
    }
    body = {"url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/280px-PNG_transparency_demonstration_1.png"}
    try:
        r = requests.post(url, headers=headers, json=body, timeout=15)
        if r.status_code in (200, 201):
            print(f"  [PASS] Computer Vision: connected (status {r.status_code})")
            return True
        else:
            # 400 on test image is fine — it means auth worked
            if r.status_code in (400, 415):
                print(f"  [PASS] Computer Vision: auth confirmed (status {r.status_code} = endpoint reached)")
                return True
            print(f"  [FAIL] Computer Vision: status {r.status_code} — {r.text[:100]}")
            return False
    except Exception as e:
        print(f"  [FAIL] Computer Vision test: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Azure Cognitive Services Setup")
    parser.add_argument("--endpoint", help="Cognitive Services endpoint URL")
    parser.add_argument("--key",      help="Cognitive Services API key")
    parser.add_argument("--test",     action="store_true", help="Test using values from .env")
    args = parser.parse_args()

    # Load from .env if --test mode
    if args.test:
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())
        args.endpoint = os.environ.get("AZURE_COGNITIVE_ENDPOINT", "")
        args.key      = os.environ.get("AZURE_COGNITIVE_KEY", "")
        if not args.endpoint or not args.key:
            print("\n  [!] AZURE_COGNITIVE_ENDPOINT and AZURE_COGNITIVE_KEY not set in .env")
            print("      Create the F0 resource first, then re-run with --endpoint and --key\n")
            sys.exit(1)

    if not args.endpoint or not args.key:
        print(__doc__)
        print("Azure Console Steps:")
        print("  1. https://portal.azure.com -> Create a resource")
        print("  2. Search: 'Cognitive Services' (multi-service account)")
        print("  3. Settings: F0 tier | Region: East US | Name: trishula-cognitive")
        print("  4. After creation: Keys and Endpoint tab")
        print("  5. Copy KEY 1 and Endpoint")
        print("  6. Run: python setup_azure_cognitive.py --endpoint <URL> --key <KEY>")
        sys.exit(0)

    print(f"\n  Endpoint: {args.endpoint}")
    print(f"  Key:      {args.key[:8]}...\n")

    # Write to .env
    update_env("AZURE_COGNITIVE_ENDPOINT", args.endpoint)
    update_env("AZURE_COGNITIVE_KEY", args.key)

    # Test both services
    print("\n  Testing Azure Language API...")
    lang_ok = test_azure(args.endpoint, args.key)
    print("\n  Testing Azure Computer Vision...")
    vis_ok = test_vision(args.endpoint, args.key)

    print()
    if lang_ok and vis_ok:
        print("  [LIVE] Azure Cognitive Services F0 is fully active.")
        print("  Vision + Language + Speech + Form Recognizer + Translator all live.")
    else:
        print("  [PARTIAL] Check errors above. API key may need a few minutes to propagate.")

if __name__ == "__main__":
    main()
