#!/usr/bin/env python3
"""
TRISHULA CLOUD ARBITRAGE v4.0 -- AI LAYER ACTIVATION TEST
==========================================================
Validates that free-tier AI services are live across all 4 clouds.
Run after enabling APIs in each console.

Usage: python enable_cloud_ai.py
"""

import os, sys, json, time
from pathlib import Path

# Load .env from market data dir
ENV_PATH = Path(__file__).parent.parent / "Swarm_4_SBM_FINAL INTEGRATION" / "Project-Swarm" / "trishula-market-data" / ".env"
if ENV_PATH.exists():
    for line in ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

PASS = "\033[92m[PASS]\033[0m"
FAIL = "\033[91m[FAIL]\033[0m"
SKIP = "\033[93m[SKIP]\033[0m"

results = {}

# ─── 1. GCP Gemini (already active) ──────────────────────────────────────────
print("\n=== GCP: Gemini 2.5 Flash ===")
try:
    import google.generativeai as genai
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY", ""))
    model = genai.GenerativeModel("gemini-2.5-flash")
    r = model.generate_content("Say: ONLINE")
    print(f"  {PASS} Gemini 2.5 Flash: {r.text.strip()[:40]}")
    results["gemini_flash"] = "PASS"
except Exception as e:
    print(f"  {FAIL} Gemini: {e}")
    results["gemini_flash"] = f"FAIL: {e}"

# ─── 2. GCP Natural Language API ─────────────────────────────────────────────
print("\n=== GCP: Natural Language API ===")
try:
    from google.cloud import language_v2
    client = language_v2.LanguageServiceClient()
    doc = language_v2.Document(content="NVDA earnings beat sent the market higher.", type_=language_v2.Document.Type.PLAIN_TEXT)
    sentiment = client.analyze_sentiment(request={"document": doc}).document_sentiment
    print(f"  {PASS} Natural Language API: score={sentiment.score:.2f} magnitude={sentiment.magnitude:.2f}")
    results["gcp_nlp"] = "PASS"
except ImportError:
    print(f"  {SKIP} google-cloud-language not installed. Run: pip install google-cloud-language")
    results["gcp_nlp"] = "SKIP: package missing"
except Exception as e:
    print(f"  {FAIL} NL API: {e}")
    results["gcp_nlp"] = f"FAIL: {e}"

# ─── 3. GCP Cloud Vision API ─────────────────────────────────────────────────
print("\n=== GCP: Cloud Vision API ===")
try:
    from google.cloud import vision
    client = vision.ImageAnnotatorClient()
    # Minimal test — just verify client initializes with credentials
    print(f"  {PASS} Cloud Vision API client initialized successfully")
    results["gcp_vision"] = "PASS"
except ImportError:
    print(f"  {SKIP} google-cloud-vision not installed. Run: pip install google-cloud-vision")
    results["gcp_vision"] = "SKIP: package missing"
except Exception as e:
    print(f"  {FAIL} Vision API: {e}")
    results["gcp_vision"] = f"FAIL: {e}"

# ─── 4. AWS Comprehend ────────────────────────────────────────────────────────
print("\n=== AWS: Comprehend ===")
try:
    import boto3
    comp = boto3.client("comprehend",
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    )
    r = comp.detect_sentiment(Text="The Fed held rates steady, boosting equities.", LanguageCode="en")
    print(f"  {PASS} Comprehend: sentiment={r['Sentiment']}  scores={json.dumps({k: round(v,2) for k,v in r['SentimentScore'].items()})}")
    results["aws_comprehend"] = "PASS"
except Exception as e:
    print(f"  {FAIL} Comprehend: {e}")
    results["aws_comprehend"] = f"FAIL: {e}"

# ─── 5. AWS Rekognition ───────────────────────────────────────────────────────
print("\n=== AWS: Rekognition ===")
try:
    import boto3
    rek = boto3.client("rekognition",
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    )
    # Just call list_collections to verify access (no image needed)
    rek.list_collections()
    print(f"  {PASS} Rekognition: API access confirmed")
    results["aws_rekognition"] = "PASS"
except Exception as e:
    print(f"  {FAIL} Rekognition: {e}")
    results["aws_rekognition"] = f"FAIL: {e}"

# ─── 6. AWS DynamoDB (already live) ──────────────────────────────────────────
print("\n=== AWS: DynamoDB ===")
try:
    import boto3
    ddb = boto3.resource("dynamodb",
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    )
    tables = [t.name for t in ddb.tables.all()]
    trishula_tables = [t for t in tables if "trishula" in t.lower()]
    print(f"  {PASS} DynamoDB: {len(trishula_tables)} Trishula tables live: {trishula_tables}")
    results["aws_dynamodb"] = "PASS"
except Exception as e:
    print(f"  {FAIL} DynamoDB: {e}")
    results["aws_dynamodb"] = f"FAIL: {e}"

# ─── 7. Azure Cognitive Services ─────────────────────────────────────────────
print("\n=== Azure: Cognitive Services ===")
azure_endpoint = os.environ.get("AZURE_COGNITIVE_ENDPOINT", "")
azure_key = os.environ.get("AZURE_COGNITIVE_KEY", "")
if not azure_endpoint or not azure_key:
    print(f"  {SKIP} AZURE_COGNITIVE_ENDPOINT / AZURE_COGNITIVE_KEY not in .env")
    print(f"         Action: Create F0 resource in Azure Portal, then add to .env")
    results["azure_cognitive"] = "SKIP: not configured"
else:
    try:
        import requests
        url = azure_endpoint.rstrip("/") + "/text/analytics/v3.1/sentiment"
        headers = {"Ocp-Apim-Subscription-Key": azure_key, "Content-Type": "application/json"}
        body = {"documents": [{"id": "1", "language": "en", "text": "Markets rallied on strong jobs data."}]}
        r = requests.post(url, headers=headers, json=body, timeout=10)
        sentiment = r.json()["documents"][0]["sentiment"]
        print(f"  {PASS} Azure Language F0: sentiment={sentiment}")
        results["azure_cognitive"] = "PASS"
    except Exception as e:
        print(f"  {FAIL} Azure Cognitive: {e}")
        results["azure_cognitive"] = f"FAIL: {e}"

# ─── Summary ──────────────────────────────────────────────────────────────────
print("\n" + "="*55)
print("  TRISHULA AI LAYER -- ACTIVATION SUMMARY")
print("="*55)
passed = sum(1 for v in results.values() if v == "PASS")
total  = len(results)
for svc, status in results.items():
    icon = PASS if status == "PASS" else (SKIP if status.startswith("SKIP") else FAIL)
    print(f"  {icon} {svc:<25} {status}")
print(f"\n  Score: {passed}/{total} services live")
print("="*55)
