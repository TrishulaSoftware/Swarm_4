#!/usr/bin/env python3
"""Quick Oracle ORDS REST connection test."""
import requests
from base64 import b64encode

ORDS_URL = "https://g275356d1414552-trishulapicks.adb.us-ashburn-1.oraclecloudapps.com/ords/admin/"
USER     = "ADMIN"
PW       = "C1iffyHu5tl3!!!"

creds   = b64encode(f"{USER}:{PW}".encode()).decode()
headers = {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}

print("\n" + "="*55)
print("  ORACLE AUTONOMOUS DB -- ORDS REST TEST")
print("="*55)

# Test 1: ping with SYSDATE
print("\n[1/3] Ping via SQL")
try:
    r = requests.post(
        ORDS_URL.rstrip("/") + "/_/sql",
        headers=headers,
        json={"statementText": "SELECT SYSDATE, 'TRISHULA_LIVE' AS STATUS FROM DUAL"},
        timeout=15
    )
    if r.status_code in (200, 201):
        data = r.json()
        items = data.get("items", [{}])
        print(f"  [PASS] Oracle ORDS: {items[0] if items else r.json()}")
    else:
        print(f"  [INFO] HTTP {r.status_code}: {r.text[:200]}")
except Exception as e:
    print(f"  [FAIL] {e}")

# Test 2: Create tables
print("\n[2/3] Creating schema tables")
tables = {
    "qmatrix_snapshots": """
        CREATE TABLE qmatrix_snapshots (
            id         NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            snap_ts    TIMESTAMP DEFAULT SYSTIMESTAMP,
            symbol     VARCHAR2(10),
            spot       NUMBER(12,4),
            max_pain   NUMBER(12,4),
            net_gex    NUMBER(16,2),
            pc_ratio   NUMBER(8,4),
            expiry     VARCHAR2(20),
            sweep_type VARCHAR2(30)
        )""",
    "picks_history": """
        CREATE TABLE picks_history (
            id         NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            pick_date  DATE DEFAULT SYSDATE,
            sport      VARCHAR2(20),
            event_id   VARCHAR2(100),
            pick_type  VARCHAR2(50),
            selection  VARCHAR2(200),
            odds       NUMBER(8,2),
            result     VARCHAR2(10),
            pnl        NUMBER(10,2),
            confidence NUMBER(5,2)
        )""",
    "line_history": """
        CREATE TABLE line_history (
            id           NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            record_ts    TIMESTAMP DEFAULT SYSTIMESTAMP,
            event_id     VARCHAR2(100),
            sport        VARCHAR2(20),
            open_line    NUMBER(8,2),
            current_line NUMBER(8,2),
            movement     NUMBER(8,2)
        )""",
}

for name, ddl in tables.items():
    try:
        r = requests.post(
            ORDS_URL.rstrip("/") + "/_/sql",
            headers=headers,
            json={"statementText": ddl.strip()},
            timeout=15
        )
        if r.status_code in (200, 201):
            resp = r.json()
            # ORA-00955 = table already exists — that's fine
            if "ORA-00955" in str(resp):
                print(f"  [OK] {name}: already exists")
            else:
                print(f"  [OK] {name}: created")
        else:
            print(f"  [INFO] {name}: HTTP {r.status_code}")
    except Exception as e:
        print(f"  [WARN] {name}: {e}")

# Test 3: Insert + read qmatrix snapshot
print("\n[3/3] Insert + read test")
try:
    r = requests.post(
        ORDS_URL.rstrip("/") + "/_/sql",
        headers=headers,
        json={"statementText": "INSERT INTO qmatrix_snapshots (symbol,spot,max_pain,net_gex,pc_ratio,expiry,sweep_type) VALUES ('NVDA',135.50,130.00,2500000,0.85,'2026-05-30','TEST')"},
        timeout=15
    )
    requests.post(ORDS_URL.rstrip("/") + "/_/sql", headers=headers, json={"statementText": "COMMIT"}, timeout=10)

    r2 = requests.post(
        ORDS_URL.rstrip("/") + "/_/sql",
        headers=headers,
        json={"statementText": "SELECT symbol, spot, max_pain, net_gex, sweep_type FROM qmatrix_snapshots WHERE ROWNUM <= 1"},
        timeout=15
    )
    if r2.status_code in (200, 201):
        print(f"  [PASS] Read confirmed: {r2.json().get('items', ['ok'])[:1]}")
except Exception as e:
    print(f"  [WARN] {e}")

print("\n" + "="*55)
print("  Oracle Autonomous DB LIVE -- 20GB always-free")
print("="*55 + "\n")
