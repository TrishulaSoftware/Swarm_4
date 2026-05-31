#!/usr/bin/env python3
"""
TRISHULA CLOUD ARBITRAGE v4.0 -- GCP ADC SETUP
===============================================
Sets up Application Default Credentials for GCP Cloud APIs
(Natural Language, Vision, Speech, Translation).

Gemini works via GOOGLE_API_KEY. The Cloud APIs (NL, Vision, etc.)
use OAuth ADC. This script sets them up via the service account key
OR via the Google Cloud SDK browser flow.

Run: python setup_gcp_adc.py
"""

import os, json, sys
from pathlib import Path

# Check if GOOGLE_APPLICATION_CREDENTIALS is already set
existing = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
if existing and Path(existing).exists():
    print(f"[OK] ADC already configured: {existing}")
    sys.exit(0)

# Check common service account key locations
search_paths = [
    Path(r"H:\Trishula\Swarm_4_Integration\Swarm_4_SBM_FINAL INTEGRATION\Project-Swarm"),
    Path(r"H:\Trishula\Swarm_4_Integration"),
    Path(r"H:\Trishula\Swarm_4_Integration\Salvo_Staging"),
    Path.home() / ".config" / "gcloud",
]

sa_key = None
for search in search_paths:
    if search.exists():
        for f in search.rglob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8", errors="ignore"))
                if data.get("type") == "service_account":
                    sa_key = f
                    break
            except Exception:
                pass
    if sa_key:
        break

if sa_key:
    print(f"[FOUND] Service account key: {sa_key}")
    print(f"  Add to .env:  GOOGLE_APPLICATION_CREDENTIALS={sa_key}")
    print(f"  Or run: $env:GOOGLE_APPLICATION_CREDENTIALS='{sa_key}'")
else:
    print("[NOT FOUND] No service account key JSON found.")
    print()
    print("Two options to fix GCP Cloud API auth:")
    print()
    print("OPTION A -- Service Account Key (Recommended for servers):")
    print("  1. Go to: https://console.cloud.google.com/iam-admin/serviceaccounts")
    print("  2. Select your project -> your service account")
    print("  3. Keys tab -> Add Key -> JSON -> Download")
    print("  4. Save to: H:\\Trishula\\Swarm_4_Integration\\gcp-sa-key.json")
    print("  5. Add to .env: GOOGLE_APPLICATION_CREDENTIALS=H:\\Trishula\\Swarm_4_Integration\\gcp-sa-key.json")
    print()
    print("OPTION B -- gcloud CLI (One-time browser auth):")
    print("  1. Download gcloud CLI: https://cloud.google.com/sdk/docs/install")
    print("  2. Run: gcloud auth application-default login")
    print("  3. Complete browser OAuth flow")
    print()
    print("APIs to enable in GCP Console (all free):")
    print("  https://console.cloud.google.com/apis/library/language.googleapis.com")
    print("  https://console.cloud.google.com/apis/library/vision.googleapis.com")
    print("  https://console.cloud.google.com/apis/library/speech.googleapis.com")
    print("  https://console.cloud.google.com/apis/library/translate.googleapis.com")
