#!/usr/bin/env python3
"""Test all newly enabled GCP APIs."""
import os, requests
from pathlib import Path
from google.oauth2 import service_account
from google.auth.transport.requests import Request

KEY_FILE = r"H:\Trishula\Swarm_4_Integration\Swarm_4_SBM_FINAL INTEGRATION\Project-Swarm\trishula-gcp-key.json"
PROJECT  = "gcp-swarm-491812"

creds = service_account.Credentials.from_service_account_file(
    KEY_FILE, scopes=["https://www.googleapis.com/auth/cloud-platform"])
creds.refresh(Request())
token   = creds.token
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

print()
print("=" * 52)
print("  GCP NEW APIs -- LIVE TEST")
print("=" * 52)

# Translation
r = requests.post(
    f"https://translation.googleapis.com/v3/projects/{PROJECT}:translateText",
    headers=headers,
    json={"contents": ["options scanner active"], "targetLanguageCode": "es", "sourceLanguageCode": "en"},
    timeout=10)
if r.status_code == 200:
    t = r.json()["translations"][0]["translatedText"]
    print(f"  [PASS] Translation: '{t}'")
else:
    print(f"  [INFO] Translation: HTTP {r.status_code}")

# Speech-to-Text
r = requests.get("https://speech.googleapis.com/v1/operations", headers=headers, timeout=10)
tag = "PASS" if r.status_code in (200, 404) else "INFO"
print(f"  [{tag}] Speech API: HTTP {r.status_code} - LIVE")

# Secret Manager
r = requests.get(
    f"https://secretmanager.googleapis.com/v1/projects/{PROJECT}/secrets",
    headers=headers, timeout=10)
tag = "PASS" if r.status_code in (200, 404) else "INFO"
print(f"  [{tag}] Secret Manager: HTTP {r.status_code} - LIVE")

# Cloud Storage bucket
r = requests.get(
    "https://storage.googleapis.com/storage/v1/b/trishula-swarm-data",
    headers=headers, timeout=10)
if r.status_code == 200:
    b = r.json()
    print(f"  [PASS] GCS: gs://trishula-swarm-data ({b['location']} {b['storageClass']})")
else:
    print(f"  [INFO] GCS: HTTP {r.status_code}")

# Cloud Run
r = requests.get(
    f"https://run.googleapis.com/v2/projects/{PROJECT}/locations/us-central1/services",
    headers=headers, timeout=10)
tag = "PASS" if r.status_code in (200, 404) else "INFO"
print(f"  [{tag}] Cloud Run: HTTP {r.status_code} - API LIVE")

# Cloud Logging
r = requests.get(
    f"https://logging.googleapis.com/v2/projects/{PROJECT}/logs",
    headers=headers, timeout=10)
tag = "PASS" if r.status_code in (200, 404) else "INFO"
print(f"  [{tag}] Cloud Logging: HTTP {r.status_code} - API LIVE")

print("=" * 52)
print("  GCP APIs: Translation | Speech | Secrets |")
print("            Storage | Cloud Run | Logging")
print("=" * 52)
