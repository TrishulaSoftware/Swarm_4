#!/usr/bin/env python3
"""Create qmatrix_snapshots table and enable ORDS REST access."""
import requests
from base64 import b64encode

ORDS_URL = "https://g275356d1414552-trishulapicks.adb.us-ashburn-1.oraclecloudapps.com/ords/admin"
USER     = "ADMIN"
PW       = "C1iffyHu5tl3!!!"
creds    = b64encode(f"{USER}:{PW}".encode()).decode()
HEADERS  = {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}

def sql(stmt, label=""):
    r = requests.post(f"{ORDS_URL}/_/sql", headers=HEADERS,
                      json={"statementText": stmt}, timeout=20)
    resp = r.json() if r.headers.get('content-type','').startswith('application/json') else r.text
    err  = str(resp)
    ok   = r.status_code in (200, 201) and 'ORA-' not in err[:100]
    already = 'ORA-00955' in err or 'ORA-00001' in err
    if ok or already:
        print(f"  [OK] {label}")
    else:
        print(f"  [WARN] {label}: {err[:120]}")
    return ok or already

print("\n[DB1 SETUP] Creating qmatrix_snapshots table...\n")

# Step 1: Drop if broken (ignore errors)
sql("BEGIN EXECUTE IMMEDIATE 'DROP TABLE qmatrix_snapshots'; EXCEPTION WHEN OTHERS THEN NULL; END;", "Drop old table (if exists)")

# Step 2: Create the full table
sql("""
CREATE TABLE qmatrix_snapshots (
  id              NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  scan_ts         TIMESTAMP DEFAULT SYSTIMESTAMP,
  scan_date       VARCHAR2(10),
  scan_time       VARCHAR2(5),
  ticker          VARCHAR2(10),
  spot            NUMBER(12,4),
  expiry          VARCHAR2(10),
  max_pain        NUMBER(12,4),
  call_wall       NUMBER(12,4),
  put_wall        NUMBER(12,4),
  net_gex_m       NUMBER(12,4),
  pc_ratio        NUMBER(8,4),
  gex_zero        NUMBER(12,4),
  iv_skew_pct     NUMBER(8,4),
  whale_poc       NUMBER(12,4),
  whale_bull_pct  NUMBER(6,2),
  top_flow_side   VARCHAR2(4),
  top_flow_k      NUMBER(12,4),
  top_flow_ratio  NUMBER(10,2)
)
""", "Create qmatrix_snapshots")

# Step 3: Enable ORDS REST on the table
sql("""
BEGIN
  ORDS.ENABLE_OBJECT(
    p_enabled     => TRUE,
    p_schema      => 'ADMIN',
    p_object      => 'QMATRIX_SNAPSHOTS',
    p_object_type => 'TABLE',
    p_object_alias => 'qmatrix_snapshots',
    p_auto_rest_auth => FALSE
  );
  COMMIT;
END;
""", "Enable ORDS REST on qmatrix_snapshots")

# Step 4: Test insert via SQL
sql("""
INSERT INTO qmatrix_snapshots
  (scan_date, scan_time, ticker, spot, expiry, max_pain, call_wall, put_wall, net_gex_m, pc_ratio)
VALUES
  ('2026-05-29', '09:30', 'TEST', 750.00, '2026-05-30', 749.00, 755.00, 745.00, 12.50, 0.87)
""", "Test insert row")

sql("COMMIT", "Commit")

# Step 5: Verify row count
r = requests.post(f"{ORDS_URL}/_/sql", headers=HEADERS,
                  json={"statementText": "SELECT COUNT(*) AS CNT FROM qmatrix_snapshots"}, timeout=15)
cnt = r.json().get('items', [{}])[0].get('CNT', '?') if r.status_code == 200 else '?'
print(f"\n  [VERIFY] Rows in qmatrix_snapshots: {cnt}")

# Step 6: Test ORDS REST endpoint directly
r2 = requests.get(f"{ORDS_URL}/qmatrix_snapshots/", headers=HEADERS, timeout=15)
print(f"  [VERIFY] ORDS REST GET: HTTP {r2.status_code}")
if r2.status_code == 200:
    items = r2.json().get('items', [])
    print(f"  [VERIFY] Items via REST: {len(items)}")
    print("\n  [DB1] READY — ORDS REST endpoint live.")
else:
    print(f"  [DB1] REST endpoint issue: {r2.text[:200]}")
