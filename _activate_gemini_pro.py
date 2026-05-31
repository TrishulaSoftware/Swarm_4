#!/usr/bin/env python3
"""Wire Gemini 2.5 Pro and test both Gemini models."""
import os
from pathlib import Path

ENV = Path(r"H:\Trishula\Swarm_4_Integration\Swarm_4_SBM_FINAL INTEGRATION\Project-Swarm\trishula-market-data\.env")

# Load env
for line in ENV.read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

# Wire Gemini Pro
txt = ENV.read_text(encoding="utf-8")
if "GEMINI_PRO_MODEL" not in txt:
    txt = txt.rstrip() + "\nGEMINI_PRO_MODEL=gemini-2.5-pro-exp-03-25\nGEMINI_FLASH_MODEL=gemini-2.5-flash-preview-05-20\n"
    ENV.write_text(txt, encoding="utf-8")
    print("[OK] Gemini Pro model wired to .env")

import google.generativeai as genai
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY", ""))

print()
print("=" * 50)
print("  GEMINI MODELS -- LIVE TEST")
print("=" * 50)

models = [
    ("FLASH", "gemini-2.5-flash-preview-05-20"),
    ("PRO  ", "gemini-2.5-pro-exp-03-25"),
]

for label, model_id in models:
    try:
        m = genai.GenerativeModel(model_id)
        r = m.generate_content("Reply with exactly: TRISHULA_OK")
        print(f"  [{label}] {r.text.strip()[:40]}")
    except Exception as e:
        print(f"  [{label}] {str(e)[:70]}")

print("=" * 50)
print("  Flash: 1,500 req/day | Pro: ~3K req/mo")
print("=" * 50)
