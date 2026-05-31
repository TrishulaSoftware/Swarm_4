#!/usr/bin/env python3
"""Test OCI DB2 (trishulaledger) and create SBM + Subscriber schema."""
import requests
from requests.auth import HTTPBasicAuth

BASE = "https://g275356d1414552-trishulaledger.adb.us-ashburn-1.oraclecloudapps.com/ords/admin/"
AUTH = HTTPBasicAuth("ADMIN", "C1iffyHu5tl3!!!")

print("\n" + "="*55)
print("  ORACLE DB2 (trishulaledger) -- LIVE TEST")
print("="*55)

# Test connection
r = requests.get(BASE, auth=AUTH, timeout=15)
status = "[PASS]" if r.status_code in (200, 201) else f"HTTP {r.status_code}"
print(f"\n[1/3] Connection: {status}")

# Table definitions
tables = {
    "sbm_picks_history": """CREATE TABLE sbm_picks_history (
        id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        sport VARCHAR2(20), game_date DATE, player VARCHAR2(100),
        team VARCHAR2(10), opp VARCHAR2(10), prop VARCHAR2(50),
        line NUMBER, pick VARCHAR2(10), odds NUMBER,
        confidence NUMBER, result VARCHAR2(10), pnl NUMBER
    )""",
    "subscriber_ledger": """CREATE TABLE subscriber_ledger (
        id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        discord_id VARCHAR2(50), tier VARCHAR2(20), status VARCHAR2(20),
        stripe_customer_id VARCHAR2(100), api_key VARCHAR2(100),
        monthly_requests NUMBER DEFAULT 0, last_active TIMESTAMP
    )""",
    "injury_log": """CREATE TABLE injury_log (
        id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        player VARCHAR2(100), team VARCHAR2(10), sport VARCHAR2(20),
        status VARCHAR2(30), body_part VARCHAR2(50),
        sentiment_score NUMBER, source VARCHAR2(100),
        raw_text VARCHAR2(2000)
    )""",
}

print("\n[2/3] Creating tables...")
for name, ddl in tables.items():
    payload = {"statementType": "run", "statement": ddl}
    try:
        r = requests.post(
            BASE + "sql", auth=AUTH,
            headers={"Content-Type": "application/json"},
            json=payload, timeout=15
        )
        if r.status_code in (200, 201):
            print(f"  [OK] Created: {name}")
        elif "ORA-00955" in r.text:
            print(f"  [OK] Exists:  {name}")
        else:
            print(f"  [INFO] {name}: HTTP {r.status_code} — {r.text[:60]}")
    except Exception as e:
        print(f"  [ERR] {name}: {e}")

print("\n[3/3] Updating .env password...")
from pathlib import Path
env = Path(r"H:\Trishula\Swarm_4_Integration\Swarm_4_SBM_FINAL INTEGRATION\Project-Swarm\trishula-market-data\.env")
txt = env.read_text(encoding="utf-8")
txt = txt.replace("ORACLE2_PASSWORD=", "ORACLE2_PASSWORD=C1iffyHu5tl3!!!")
env.write_text(txt, encoding="utf-8")
print("  [OK] Password saved")

print("\n" + "="*55)
print("  trishulaledger: SBM picks | Subscriber ledger | Injury log")
print("="*55 + "\n")
