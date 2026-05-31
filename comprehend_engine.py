#!/usr/bin/env python3
"""
TRISHULA -- AWS COMPREHEND + TEXTRACT NLP ENGINE
=================================================
Fires when AWS 24-hour hold lifts (~8 PM May 26).
Provides:
  - Comprehend: NLP sentiment + entity extraction on injury/news text
  - Textract: PDF line sheet extraction (earnings reports, injury PDFs)

Usage:
  from comprehend_engine import analyze_text, extract_pdf
"""
import os, json, boto3
from pathlib import Path

# ── AWS Client Factory ─────────────────────────────────────
def _comprehend():
    return boto3.client(
        "comprehend",
        region_name=os.getenv("AWS_REGION", "us-east-2"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )

def _textract():
    return boto3.client(
        "textract",
        region_name=os.getenv("AWS_REGION", "us-east-2"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )

# ── Comprehend: Sentiment Analysis ────────────────────────
def analyze_sentiment(text: str) -> dict:
    """Returns sentiment (POSITIVE/NEGATIVE/NEUTRAL/MIXED) + scores."""
    try:
        r = _comprehend().detect_sentiment(Text=text[:4500], LanguageCode="en")
        return {
            "sentiment":   r["Sentiment"],
            "positive":    round(r["SentimentScore"]["Positive"], 4),
            "negative":    round(r["SentimentScore"]["Negative"], 4),
            "neutral":     round(r["SentimentScore"]["Neutral"], 4),
            "mixed":       round(r["SentimentScore"]["Mixed"], 4),
        }
    except Exception as e:
        return {"sentiment": "ERROR", "error": str(e)}

# ── Comprehend: Entity Extraction ─────────────────────────
def extract_entities(text: str) -> list:
    """Extracts named entities: PERSON, ORGANIZATION, LOCATION, EVENT, etc."""
    try:
        r = _comprehend().detect_entities(Text=text[:4500], LanguageCode="en")
        return [
            {"text": e["Text"], "type": e["Type"], "score": round(e["Score"], 3)}
            for e in r["Entities"]
            if e["Score"] > 0.85
        ]
    except Exception as e:
        return [{"error": str(e)}]

# ── Comprehend: Key Phrases ───────────────────────────────
def extract_key_phrases(text: str) -> list:
    """Extracts key phrases — good for injury report parsing."""
    try:
        r = _comprehend().detect_key_phrases(Text=text[:4500], LanguageCode="en")
        return [p["Text"] for p in r["KeyPhrases"] if p["Score"] > 0.85]
    except Exception as e:
        return [f"ERROR: {e}"]

# ── Full NLP Profile ──────────────────────────────────────
def analyze_text(text: str, context: str = "") -> dict:
    """Full NLP pass: sentiment + entities + key phrases."""
    sentiment = analyze_sentiment(text)
    entities  = extract_entities(text)
    phrases   = extract_key_phrases(text)

    # Flag injury-relevant keywords
    injury_flags = [
        kw for kw in ["injury", "injured", "out", "questionable", "doubtful",
                       "DNP", "IL", "DL", "knee", "hamstring", "ankle", "wrist",
                       "concussion", "surgery", "season", "scratch"]
        if kw.lower() in text.lower()
    ]

    return {
        "context":       context,
        "sentiment":     sentiment,
        "entities":      entities,
        "key_phrases":   phrases[:10],
        "injury_flags":  injury_flags,
        "injury_alert":  len(injury_flags) > 2,
    }

# ── Textract: PDF Text Extraction ────────────────────────
def extract_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extracts text from a PDF byte stream using Textract."""
    try:
        r = _textract().detect_document_text(Document={"Bytes": pdf_bytes})
        lines = [b["Text"] for b in r["Blocks"] if b["BlockType"] == "LINE"]
        return "\n".join(lines)
    except Exception as e:
        return f"ERROR: {e}"

def extract_pdf_file(pdf_path: str) -> str:
    """Extracts text from a local PDF file using Textract."""
    return extract_pdf_bytes(Path(pdf_path).read_bytes())

# ── Self Test ─────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "="*55)
    print("  AWS COMPREHEND + TEXTRACT — LIVE TEST")
    print("="*55)

    # Injury report test
    test_text = (
        "Jayson Tatum is listed as doubtful for tonight's game "
        "due to a right ankle injury. He did not practice Wednesday. "
        "The Celtics will be without their star forward."
    )
    print(f"\n[1/2] Comprehend NLP on injury text:")
    print(f"  Input: '{test_text[:60]}...'")

    result = analyze_text(test_text, context="injury_sniper")
    print(f"  Sentiment:     {result['sentiment']['sentiment']}")
    print(f"  Negative score:{result['sentiment']['negative']}")
    print(f"  Injury flags:  {result['injury_flags']}")
    print(f"  Injury alert:  {result['injury_alert']}")
    print(f"  Entities:      {[e['text'] for e in result['entities']]}")

    print(f"\n[2/2] Textract: pass a PDF path via extract_pdf_file(path)")
    print(f"  (No PDF available in test — Textract client initialized)")
    try:
        _textract()
        print(f"  [PASS] Textract client ready")
    except Exception as e:
        print(f"  [FAIL] {e}")

    print("\n" + "="*55)
    print("  Comprehend: 50K units/mo free (12 mo)")
    print("  Textract:   1,000 pages/mo free (3 mo)")
    print("="*55 + "\n")
