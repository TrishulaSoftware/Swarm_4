#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=================================================================
DB1 SCHEMA V2 SETUP
=================================================================
Creates three new tables in Oracle DB1 (trishulapicks) via ORDS:
  1. intraday_snapshots   -- 15-min bar + GEX/VIX overlay
  2. backtest_results     -- Q-Matrix module accuracy tracking
  3. news_events          -- Macro / earnings calendar

For each table:
  - CREATE TABLE (skip if exists)
  - Enable ORDS REST (ORDS.ENABLE_OBJECT)
  - Test INSERT via /_/sql (ORDS REST POST does not handle
    Oracle DATE/TIMESTAMP NOT NULL columns via JSON)
  - Test SELECT via ORDS REST GET
=================================================================
"""
import sys
import json
import datetime
import requests
from base64 import b64encode

# Force UTF-8 output on Windows
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---- Auth -------------------------------------------------------
ORDS_BASE = "https://g275356d1414552-trishulapicks.adb.us-ashburn-1.oraclecloudapps.com/ords/admin"
USER      = "ADMIN"
PW        = "C1iffyHu5tl3!!!"

_creds   = b64encode(f"{USER}:{PW}".encode()).decode()
HEADERS  = {
    "Authorization": f"Basic {_creds}",
    "Content-Type":  "application/json",
}

# ---- Results tracker --------------------------------------------
results = {}

# =================================================================
# Helpers
# =================================================================

def sql(stmt: str, label: str = "") -> bool:
    """Execute a SQL statement via ORDS /_/sql endpoint."""
    url = f"{ORDS_BASE}/_/sql"
    try:
        r = requests.post(url, headers=HEADERS,
                          json={"statementText": stmt.strip()},
                          timeout=25)
    except Exception as exc:
        print(f"  [ERR ] {label}: connection error -- {exc}")
        return False

    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text}

    body_str = json.dumps(body)
    already  = "ORA-00955" in body_str or "ORA-00001" in body_str
    # Check for errorDetails in items
    sql_err  = any(item.get("errorDetails", "") for item in body.get("items", []))
    ok       = r.status_code in (200, 201) and not sql_err

    if ok or already:
        tag = "[SKIP]" if already else "[OK  ]"
        print(f"  {tag} {label}")
    else:
        details = []
        for item in body.get("items", []):
            ed = item.get("errorDetails", "")
            if ed:
                details.append(ed)
        detail_str = "; ".join(details) if details else body_str[:120]
        print(f"  [WARN] {label}: HTTP {r.status_code} -- {detail_str}")

    return ok or already


def sql_insert(stmt: str, label: str = "") -> bool:
    """Run an INSERT via /_/sql, then COMMIT."""
    ok = sql(stmt, label=label)
    if ok:
        sql("COMMIT", label=f"COMMIT after {label}")
    return ok


def ords_get(table_alias: str, label: str = "", limit: int = 3) -> tuple:
    """GET rows from an ORDS-enabled table."""
    url = f"{ORDS_BASE}/{table_alias}/"
    try:
        r = requests.get(url, headers=HEADERS, params={"limit": limit}, timeout=20)
    except Exception as exc:
        print(f"  [ERR ] GET {label}: {exc}")
        return False, []

    try:
        body = r.json()
    except Exception:
        body = {}

    ok    = r.status_code == 200
    items = body.get("items", [])
    if ok:
        print(f"  [OK  ] GET {label} -- {len(items)} item(s) (total={body.get('count', '?')})")
    else:
        print(f"  [WARN] GET {label}: HTTP {r.status_code} -- {json.dumps(body)[:140]}")
    return ok, items


def section(title: str):
    print(f"\n{'='*62}")
    print(f"  {title}")
    print(f"{'='*62}")


# =================================================================
# TABLE 1 -- intraday_snapshots
# =================================================================

section("TABLE 1: intraday_snapshots")

results["intraday_snapshots"] = {
    "create": False, "ords_enable": False,
    "write":  False, "read":        False,
}

results["intraday_snapshots"]["create"] = sql("""
CREATE TABLE intraday_snapshots (
  id          NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  ticker      VARCHAR2(20)    NOT NULL,
  snap_ts     TIMESTAMP       NOT NULL,
  snap_date   DATE            NOT NULL,
  snap_time   VARCHAR2(10),
  open_price  NUMBER(12,4),
  high_price  NUMBER(12,4),
  low_price   NUMBER(12,4),
  close_price NUMBER(12,4),
  volume      NUMBER(18,0),
  gex_zero    NUMBER(12,4),
  spot        NUMBER(12,4),
  vix_level   NUMBER(8,4)
)
""", label="CREATE TABLE intraday_snapshots")

results["intraday_snapshots"]["ords_enable"] = sql("""
BEGIN
  ORDS.ENABLE_OBJECT(
    p_enabled        => TRUE,
    p_schema         => 'ADMIN',
    p_object         => 'INTRADAY_SNAPSHOTS',
    p_object_type    => 'TABLE',
    p_object_alias   => 'intraday_snapshots',
    p_auto_rest_auth => FALSE
  );
  COMMIT;
END;
""", label="Enable ORDS REST on intraday_snapshots")

# Test write via /_/sql
now_ts   = datetime.datetime.now()
ts_str   = now_ts.strftime("%Y-%m-%d %H:%M:%S")
results["intraday_snapshots"]["write"] = sql_insert(
    f"INSERT INTO intraday_snapshots "
    f"(ticker,snap_ts,snap_date,snap_time,open_price,high_price,low_price,close_price,volume,gex_zero,spot,vix_level) "
    f"VALUES ('SPY',TO_TIMESTAMP('{ts_str}','YYYY-MM-DD HH24:MI:SS'),"
    f"TRUNC(TO_TIMESTAMP('{ts_str}','YYYY-MM-DD HH24:MI:SS')),"
    f"'{now_ts.strftime('%H:%M')}',528.10,529.45,527.80,529.00,4500000,527.50,529.00,16.42)",
    label="INSERT test row into intraday_snapshots"
)

ok_get, rows = ords_get("intraday_snapshots", label="intraday_snapshots")
results["intraday_snapshots"]["read"] = ok_get
if rows:
    r0 = rows[0]
    print(f"    id={r0.get('id')} ticker={r0.get('ticker')} snap_time={r0.get('snap_time')} "
          f"close={r0.get('close_price')} vix={r0.get('vix_level')}")


# =================================================================
# TABLE 2 -- backtest_results
# =================================================================

section("TABLE 2: backtest_results")

results["backtest_results"] = {
    "create": False, "ords_enable": False,
    "write":  False, "read":        False,
}

results["backtest_results"]["create"] = sql("""
CREATE TABLE backtest_results (
  id                NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  scan_date         DATE            NOT NULL,
  ticker            VARCHAR2(20)    NOT NULL,
  module            VARCHAR2(50),
  predicted_value   NUMBER(12,4),
  actual_value      NUMBER(12,4),
  pct_distance      NUMBER(8,4),
  grade             VARCHAR2(20),
  direction_correct NUMBER(1),
  scored_at         TIMESTAMP DEFAULT SYSTIMESTAMP
)
""", label="CREATE TABLE backtest_results")

results["backtest_results"]["ords_enable"] = sql("""
BEGIN
  ORDS.ENABLE_OBJECT(
    p_enabled        => TRUE,
    p_schema         => 'ADMIN',
    p_object         => 'BACKTEST_RESULTS',
    p_object_type    => 'TABLE',
    p_object_alias   => 'backtest_results',
    p_auto_rest_auth => FALSE
  );
  COMMIT;
END;
""", label="Enable ORDS REST on backtest_results")

date_str = now_ts.strftime("%Y-%m-%d")
results["backtest_results"]["write"] = sql_insert(
    f"INSERT INTO backtest_results "
    f"(scan_date,ticker,module,predicted_value,actual_value,pct_distance,grade,direction_correct,scored_at) "
    f"VALUES (TO_DATE('{date_str}','YYYY-MM-DD'),'SPY','max_pain',"
    f"528.00,529.00,0.1894,'HIT',1,"
    f"TO_TIMESTAMP('{ts_str}','YYYY-MM-DD HH24:MI:SS'))",
    label="INSERT test row into backtest_results (max_pain)"
)

# Insert additional module examples
for mod, pred, act, pct, grade, dc in [
    ("gex_zero",  527.50, 527.80, 0.0568, "BULLSEYE", 1),
    ("whale_poc", 525.00, 529.00, 0.7619, "CLOSE",    1),
    ("iv_skew",   530.00, 529.00, 0.1887, "HIT",      0),
    ("whale_bull", 0.60,   0.55,   8.33,  "MISS",     0),
]:
    sql_insert(
        f"INSERT INTO backtest_results "
        f"(scan_date,ticker,module,predicted_value,actual_value,pct_distance,grade,direction_correct,scored_at) "
        f"VALUES (TO_DATE('{date_str}','YYYY-MM-DD'),'SPY','{mod}',"
        f"{pred},{act},{pct},'{grade}',{dc},"
        f"TO_TIMESTAMP('{ts_str}','YYYY-MM-DD HH24:MI:SS'))",
        label=f"  INSERT backtest_results ({mod})"
    )

ok_get2, rows2 = ords_get("backtest_results", label="backtest_results")
results["backtest_results"]["read"] = ok_get2
if rows2:
    print(f"    Sample: module={rows2[0].get('module')} grade={rows2[0].get('grade')} "
          f"pct_dist={rows2[0].get('pct_distance')}")


# =================================================================
# TABLE 3 -- news_events
# =================================================================

section("TABLE 3: news_events")

results["news_events"] = {
    "create": False, "ords_enable": False,
    "write":  False, "read":        False,
}

results["news_events"]["create"] = sql("""
CREATE TABLE news_events (
  id           NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  event_date   DATE           NOT NULL,
  ticker       VARCHAR2(20),
  event_type   VARCHAR2(50),
  event_name   VARCHAR2(200),
  impact       VARCHAR2(20),
  created_at   TIMESTAMP DEFAULT SYSTIMESTAMP
)
""", label="CREATE TABLE news_events")

results["news_events"]["ords_enable"] = sql("""
BEGIN
  ORDS.ENABLE_OBJECT(
    p_enabled        => TRUE,
    p_schema         => 'ADMIN',
    p_object         => 'NEWS_EVENTS',
    p_object_type    => 'TABLE',
    p_object_alias   => 'news_events',
    p_auto_rest_auth => FALSE
  );
  COMMIT;
END;
""", label="Enable ORDS REST on news_events")

# Macro events (ticker = NULL)
for etype, ename, impact in [
    ("FED",  "FOMC Rate Decision (TEST)",          "HIGH"),
    ("CPI",  "CPI Print June 2026 (TEST)",         "HIGH"),
    ("OPEX", "Monthly OPEX June 2026 (TEST)",      "MEDIUM"),
    ("JOBS", "Non-Farm Payrolls June 2026 (TEST)", "HIGH"),
]:
    ok_w = sql_insert(
        f"INSERT INTO news_events (event_date,ticker,event_type,event_name,impact,created_at) "
        f"VALUES (TO_DATE('{date_str}','YYYY-MM-DD'),NULL,'{etype}','{ename}','{impact}',"
        f"TO_TIMESTAMP('{ts_str}','YYYY-MM-DD HH24:MI:SS'))",
        label=f"  INSERT news_events ({etype})"
    )
    if etype == "FED":
        results["news_events"]["write"] = ok_w

# Ticker-scoped events
for tkr, etype, ename, impact in [
    ("NVDA", "EARNINGS", "NVDA Q1 2027 Earnings (TEST)",       "HIGH"),
    ("AAPL", "EARNINGS", "AAPL Q3 FY2026 Earnings (TEST)",     "HIGH"),
    ("SPY",  "OPEX",     "SPY Weekly Expiry Jun 20 2026 (TEST)", "MEDIUM"),
]:
    sql_insert(
        f"INSERT INTO news_events (event_date,ticker,event_type,event_name,impact,created_at) "
        f"VALUES (TO_DATE('{date_str}','YYYY-MM-DD'),'{tkr}','{etype}','{ename}','{impact}',"
        f"TO_TIMESTAMP('{ts_str}','YYYY-MM-DD HH24:MI:SS'))",
        label=f"  INSERT news_events ({tkr}/{etype})"
    )

ok_get3, rows3 = ords_get("news_events", label="news_events", limit=5)
results["news_events"]["read"] = ok_get3
if rows3:
    for row in rows3[:3]:
        print(f"    id={row.get('id')} type={row.get('event_type')} ticker={row.get('ticker')} impact={row.get('impact')}")


# =================================================================
# SUMMARY
# =================================================================

section("SUMMARY")

all_ok = True
for tname, checks in results.items():
    flags = "  ".join(
        ("OK" if v else "FAIL") + " " + k for k, v in checks.items()
    )
    status = "PASS" if all(checks.values()) else "PARTIAL" if any(checks.values()) else "FAIL"
    print(f"  [{status:7s}] {tname:<25s}  {flags}")
    if not all(checks.values()):
        all_ok = False

print()
print(f"  Overall: {'ALL TABLES READY' if all_ok else 'SOME ISSUES -- see above'}")
print()

# Machine-readable output for caller agent
print("\n[JSON_RESULTS]")
print(json.dumps(results, indent=2))
