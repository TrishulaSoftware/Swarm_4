#!/usr/bin/env python3
"""
TRISHULA -- ORACLE AUTONOMOUS DB CLIENT (ORDS REST)
====================================================
Connects to Oracle Autonomous DB via HTTPS REST API (ORDS).
No native DLL required — pure requests. Works on Windows with AppLocker.

Setup:
  1. In OCI Console -> trishulapicks -> Database Actions -> SQL
  2. Run the ORDS enable block (see ORDS_SETUP_SQL below)
  3. Set ORACLE_ORDS_URL in .env

ORDS_SETUP_SQL = '''
  BEGIN
    ORDS.ENABLE_SCHEMA(
      p_enabled => TRUE,
      p_schema_name => 'ADMIN',
      p_url_mapping_type => 'BASE_PATH',
      p_url_mapping_pattern => 'admin',
      p_auto_rest_auth => FALSE
    );
    COMMIT;
  END;
'''
"""

import os, json, requests
from pathlib import Path
from base64 import b64encode

# Load .env
ENV_PATH = Path(r"H:\Trishula\Swarm_4_Integration\Swarm_4_SBM_FINAL INTEGRATION\Project-Swarm\trishula-market-data\.env")
for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

# ORDS base URL format:
# https://<db-hostname>/ords/<schema>/
# The hostname comes from the DB Connection -> Connection Strings -> HTTPS URL
ORDS_URL    = os.environ.get("ORACLE_ORDS_URL", "")
DB_USER     = os.environ.get("ORACLE_USER", "ADMIN")
DB_PW       = os.environ.get("ORACLE_PASSWORD", "C1iffyHu5tl3!!!")

def get_auth_header():
    creds = b64encode(f"{DB_USER}:{DB_PW}".encode()).decode()
    return {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}

def run_sql(sql: str, binds: dict = None) -> dict:
    """Execute SQL via ORDS REST endpoint."""
    if not ORDS_URL:
        return {"error": "ORACLE_ORDS_URL not set in .env"}
    url = ORDS_URL.rstrip("/") + "/_/sql"
    payload = {"statementText": sql}
    if binds:
        payload["binds"] = [{"name": k, "data_type": "VARCHAR", "value": v} for k, v in binds.items()]
    r = requests.post(url, headers=get_auth_header(), json=payload, timeout=15)
    r.raise_for_status()
    return r.json()

def insert_qmatrix_snapshot(symbol, spot, max_pain, net_gex, pc_ratio, expiry, sweep_type):
    """Insert a Q-Matrix scan snapshot into Oracle."""
    sql = """INSERT INTO qmatrix_snapshots 
             (symbol, spot, max_pain, net_gex, pc_ratio, expiry, sweep_type)
             VALUES (:1, :2, :3, :4, :5, :6, :7)"""
    return run_sql(sql)

def get_recent_snapshots(symbol: str, limit: int = 10) -> list:
    """Get recent Q-Matrix snapshots for a symbol."""
    sql = f"SELECT * FROM qmatrix_snapshots WHERE symbol='{symbol}' ORDER BY snap_ts DESC FETCH FIRST {limit} ROWS ONLY"
    result = run_sql(sql)
    return result.get("items", [])

if __name__ == "__main__":
    print("\n" + "="*55)
    print("  ORACLE AUTONOMOUS DB -- ORDS REST TEST")
    print("="*55)

    if not ORDS_URL:
        print("\n  [!] ORACLE_ORDS_URL not set yet.")
        print("\n  To get your ORDS URL:")
        print("  1. OCI Console -> trishulapicks -> Database Actions")
        print("  2. SQL tab -> run ORDS enable block (see docstring above)")
        print("  3. Database Connection -> Connection Strings -> copy HTTPS URL")
        print("     Format: https://g275356d1414552.adb.us-ashburn-1.oraclecloudapps.com/ords/admin/")
        print("  4. Add to .env: ORACLE_ORDS_URL=https://...")
        print()
        print("  Alternatively: connect from OCI Micro VM where AppLocker is not active")
        print("  SSH to 158.101.102.176 -> python3 _test_oracle_db.py (no DLL issue on Linux)")
    else:
        try:
            result = run_sql("SELECT SYSDATE FROM DUAL")
            print(f"  [PASS] ORDS REST connected — Oracle date: {result}")
        except Exception as e:
            print(f"  [FAIL] {e}")

    print("="*55 + "\n")
