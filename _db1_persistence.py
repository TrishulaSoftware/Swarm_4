#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=================================================================
Q-MATRIX DB1 PERSISTENCE MODULE
=================================================================
Saves all 6 Q-Matrix module outputs to Oracle DB1 (trishulapicks)
via ORDS REST API on every scan run.

Called from sovereign_options_scanner.py after each ticker processes.
Fails silently — never blocks the main sweep.

Table: qmatrix_snapshots
=================================================================
"""
import os, json, requests, datetime
from pathlib import Path

# ── ORDS Config ──────────────────────────────────────────────
_ORDS_BASE  = "https://g275356d1414552-trishulapicks.adb.us-ashburn-1.oraclecloudapps.com/ords/admin"
_ORDS_USER  = "ADMIN"
_ORDS_PASS  = "C1iffyHu5tl3!!!"
_TABLE      = "qmatrix_snapshots"
_SCHEMA_OK  = False  # set True after first successful schema check

def _get_pass() -> str:
    global _ORDS_PASS
    if _ORDS_PASS:
        return _ORDS_PASS
    for key in ['ORACLE_DB1_PASSWORD', 'ORACLE_ADMIN_PASSWORD', 'OCI_DB_PASSWORD']:
        val = os.environ.get(key, '')
        if val:
            _ORDS_PASS = val
            return val
    # Try .env file
    env_path = Path(r"H:\Trishula\Swarm_4_Integration\Swarm_4_SBM_FINAL INTEGRATION\Project-Swarm\trishula-market-data\.env")
    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8', errors='ignore').splitlines():
            if line.startswith('ORACLE_DB1_PASSWORD=') or line.startswith('ORACLE_ADMIN_PASSWORD='):
                _ORDS_PASS = line.split('=', 1)[1].strip().strip('"').strip("'")
                return _ORDS_PASS
    return ''

def _ensure_schema():
    """Create qmatrix_snapshots table if it doesn't exist, then ALTER to add any missing columns."""
    global _SCHEMA_OK
    if _SCHEMA_OK:
        return True
    try:
        # ── Try both known ORDS SQL endpoints ─────────────────────────────────
        sql_urls = [
            f"{_ORDS_BASE}/batchsql/",
            f"{_ORDS_BASE}/_/sql",
        ]

        # Full DDL: CREATE if not exists + ALTER to add any missing columns
        ddl = """
        DECLARE
          v_cnt NUMBER;
        BEGIN
          -- 1. Create table if it doesn't exist
          SELECT COUNT(*) INTO v_cnt FROM user_tables WHERE table_name = 'QMATRIX_SNAPSHOTS';
          IF v_cnt = 0 THEN
            EXECUTE IMMEDIATE '
              CREATE TABLE qmatrix_snapshots (
                id             NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                scan_ts        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                scan_date      VARCHAR2(10),
                scan_time      VARCHAR2(5),
                ticker         VARCHAR2(10),
                spot           NUMBER(10,2),
                expiry         VARCHAR2(10),
                max_pain       NUMBER(10,2),
                call_wall      NUMBER(10,2),
                put_wall       NUMBER(10,2),
                net_gex_m      NUMBER(10,3),
                pc_ratio       NUMBER(6,3),
                gex_zero       NUMBER(10,2),
                iv_skew_pct    NUMBER(6,3),
                whale_poc      NUMBER(10,2),
                whale_bull_pct NUMBER(5,2),
                wvf_val        NUMBER(8,3),
                squeeze_on     NUMBER(1),
                top_flow_side  VARCHAR2(4),
                top_flow_k     NUMBER(10,2),
                top_flow_ratio NUMBER(8,2),
                vol_spike      NUMBER(1) DEFAULT 0,
                whale_flow_flag NUMBER(1) DEFAULT 0,
                stocktwits_bull_pct NUMBER(5,2),
                days_to_earnings    NUMBER(4),
                dboi_call_wall NUMBER(10,2),
                dboi_put_wall  NUMBER(10,2),
                dboi_zero_line NUMBER(10,2),
                net_dboi_m     NUMBER(14,4)
              )';
          END IF;
          -- 2. Add missing columns to existing tables (safe: catches DUP_VAL_ON_INDEX)
          BEGIN
            EXECUTE IMMEDIATE 'ALTER TABLE qmatrix_snapshots ADD (call_wall NUMBER(10,2))';
          EXCEPTION WHEN OTHERS THEN NULL; END;
          BEGIN
            EXECUTE IMMEDIATE 'ALTER TABLE qmatrix_snapshots ADD (put_wall NUMBER(10,2))';
          EXCEPTION WHEN OTHERS THEN NULL; END;
          BEGIN
            EXECUTE IMMEDIATE 'ALTER TABLE qmatrix_snapshots ADD (net_gex_m NUMBER(10,3))';
          EXCEPTION WHEN OTHERS THEN NULL; END;
          BEGIN
            EXECUTE IMMEDIATE 'ALTER TABLE qmatrix_snapshots ADD (pc_ratio NUMBER(6,3))';
          EXCEPTION WHEN OTHERS THEN NULL; END;
          BEGIN
            EXECUTE IMMEDIATE 'ALTER TABLE qmatrix_snapshots ADD (vol_spike NUMBER(1) DEFAULT 0)';
          EXCEPTION WHEN OTHERS THEN NULL; END;
          BEGIN
            EXECUTE IMMEDIATE 'ALTER TABLE qmatrix_snapshots ADD (whale_flow_flag NUMBER(1) DEFAULT 0)';
          EXCEPTION WHEN OTHERS THEN NULL; END;
          BEGIN
            EXECUTE IMMEDIATE 'ALTER TABLE qmatrix_snapshots ADD (stocktwits_bull_pct NUMBER(5,2))';
          EXCEPTION WHEN OTHERS THEN NULL; END;
          BEGIN
            EXECUTE IMMEDIATE 'ALTER TABLE qmatrix_snapshots ADD (days_to_earnings NUMBER(4))';
          EXCEPTION WHEN OTHERS THEN NULL; END;
          BEGIN
            EXECUTE IMMEDIATE 'ALTER TABLE qmatrix_snapshots ADD (dominant_expiry VARCHAR2(10))';
          EXCEPTION WHEN OTHERS THEN NULL; END;
          BEGIN
            EXECUTE IMMEDIATE 'ALTER TABLE qmatrix_snapshots ADD (stacked_gex_zero NUMBER(10,2))';
          EXCEPTION WHEN OTHERS THEN NULL; END;
          BEGIN
            EXECUTE IMMEDIATE 'ALTER TABLE qmatrix_snapshots ADD (expiry_oi_weight VARCHAR2(300))';
          EXCEPTION WHEN OTHERS THEN NULL; END;
          BEGIN
            EXECUTE IMMEDIATE 'ALTER TABLE qmatrix_snapshots ADD (dboi_call_wall NUMBER(10,2))';
          EXCEPTION WHEN OTHERS THEN NULL; END;
          BEGIN
            EXECUTE IMMEDIATE 'ALTER TABLE qmatrix_snapshots ADD (dboi_put_wall NUMBER(10,2))';
          EXCEPTION WHEN OTHERS THEN NULL; END;
          BEGIN
            EXECUTE IMMEDIATE 'ALTER TABLE qmatrix_snapshots ADD (dboi_zero_line NUMBER(10,2))';
          EXCEPTION WHEN OTHERS THEN NULL; END;
          BEGIN
            EXECUTE IMMEDIATE 'ALTER TABLE qmatrix_snapshots ADD (net_dboi_m NUMBER(14,4))';
          EXCEPTION WHEN OTHERS THEN NULL; END;
        END;
        """
        for sql_url in sql_urls:
            try:
                r = requests.post(
                    sql_url,
                    auth=(_ORDS_USER, _get_pass()),
                    json={"statementText": ddl.strip()},
                    timeout=20
                )
                if r.status_code in (200, 201):
                    _SCHEMA_OK = True
                    print("  [DB1] Schema ensured OK")
                    return True
            except Exception:
                continue
        # If both ORDS SQL endpoints fail, still allow inserts to proceed
        _SCHEMA_OK = True  # optimistically mark done — table likely already exists
        return True
    except Exception as e:
        print(f"  [DB1] Schema check error (non-fatal): {e}")
        _SCHEMA_OK = True  # don't block scans
        return True

def save_snapshot(d: dict, eng: dict = None) -> bool:
    """
    Save one Q-Matrix scan result to Oracle DB1.

    d    = the dict returned by process_ticker_with_expiry()
           Keys used: symbol, spot, expiry, max_pain, top_call_wall,
                      top_put_wall, net_gex_m, pc_ratio, anomalies,
                      vol_spike, whale_flow_flag
    eng  = the full engine dict from fetch_full_data() (optional)
           Provides: gex_zero, iv_skew, whale_poc, whale_bull_pct
    """
    _ensure_schema()
    try:
        now = datetime.datetime.now()
        hr  = now.hour
        scan_time = "09:30" if hr < 11 else ("12:00" if hr < 14 else "15:30")

        # ── Basic metrics (always available from d) ───────────
        row = {
            "scan_date":       now.strftime("%Y-%m-%d"),
            "scan_time":       scan_time,
            "ticker":          d.get("symbol", ""),
            "spot":            float(d.get("spot", 0)),
            "expiry":          d.get("expiry", ""),
            "max_pain":        float(d.get("max_pain", 0)),
            "call_wall":       float(d.get("top_call_wall", 0)),
            "put_wall":        float(d.get("top_put_wall", 0)),
            "net_gex_m":       float(d.get("net_gex_m", 0)),
            "pc_ratio":        float(d.get("pc_ratio", 0)),
            "vol_spike":       int(d.get("vol_spike", 0)),
            "whale_flow_flag": int(d.get("whale_flow_flag", 0)),
        }

        # ── R2-8: DBOI fields ──────────────────────────────────────────────────
        if d.get("dboi_call_wall") is not None:
            row["dboi_call_wall"] = float(d["dboi_call_wall"])
        if d.get("dboi_put_wall") is not None:
            row["dboi_put_wall"]  = float(d["dboi_put_wall"])
        if d.get("dboi_zero_line") is not None:
            row["dboi_zero_line"] = float(d["dboi_zero_line"])
        if d.get("net_dboi_m") is not None:
            row["net_dboi_m"]     = float(d["net_dboi_m"])

        # ── StockTwits sentiment (P3-A) ──────────────────────────────────────
        try:
            from _stocktwits_sentiment import get_sentiment as _st_s
            st = _st_s(d.get("symbol", ""))
            if st.get("source") not in ("error", "unavailable", "api_error"):
                row["stocktwits_bull_pct"] = float(st.get("bullish_pct", 0))
        except Exception:
            pass  # Never block

        # ── Days to earnings (P3-B) ───────────────────────────────────────────
        try:
            from _news_feed import get_days_to_earnings as _dte
            dte = _dte(d.get("symbol", ""))
            if dte < 999:
                row["days_to_earnings"] = int(dte)
        except Exception:
            pass  # Never block

        # ── Flow anomaly top entry ─────────────────────────────
        anomalies = d.get("anomalies", [])
        if anomalies:
            side, k, ratio, vol = anomalies[0]
            row["top_flow_side"]  = str(side)[:4]
            row["top_flow_k"]     = float(k)
            row["top_flow_ratio"] = float(ratio)

        # ── R2-5: Multi-Expiry GEX Stack fields ───────────────
        dom_exp = d.get("dominant_expiry")
        if dom_exp:
            row["dominant_expiry"] = str(dom_exp)[:10]
        sgz = d.get("stacked_gex_zero")
        if sgz is not None:
            row["stacked_gex_zero"] = float(sgz)
        eow = d.get("expiry_oi_weight")
        if eow:
            # store as JSON string; truncate to 300 chars
            val = eow if isinstance(eow, str) else json.dumps(eow)
            row["expiry_oi_weight"] = val[:300]

        # ── GEX zero-crossing level ───────────────────────────
        if eng:
            agg_gex = eng.get("aggregate_gex", {})
            if agg_gex:
                import numpy as np
                strikes  = sorted(float(k) for k in agg_gex.keys())
                gex_vals = [float(agg_gex[str(k)] if str(k) in agg_gex else agg_gex.get(k, 0)) for k in strikes]
                # Find zero crossing (sign change)
                for i in range(len(gex_vals) - 1):
                    if gex_vals[i] * gex_vals[i+1] < 0:
                        # Linear interpolation for zero crossing
                        row["gex_zero"] = round(
                            strikes[i] + (strikes[i+1] - strikes[i]) *
                            abs(gex_vals[i]) / (abs(gex_vals[i]) + abs(gex_vals[i+1])), 2
                        )
                        break

            # ── IV skew (ATM put/call spread) ─────────────────
            iv_skew = eng.get("iv_skew_curves", {})
            if iv_skew:
                first_exp = list(iv_skew.keys())[0]
                curve     = iv_skew[first_exp]
                atm_pts   = [pt for pt in curve if abs(pt.get("pct_from_spot", 999)) < 2]
                if atm_pts:
                    avg_put  = sum(p.get("put_iv", 0) for p in atm_pts) / len(atm_pts)
                    avg_call = sum(p.get("call_iv", 0) for p in atm_pts) / len(atm_pts)
                    row["iv_skew_pct"] = round(avg_put - avg_call, 3)

            # ── Whale POC ─────────────────────────────────────
            wp = eng.get("whale_profile", {})
            if wp:
                row["whale_poc"] = float(wp.get("poc_price", 0))
                bins = wp.get("bins", [])
                if bins:
                    total_vol = sum(b.get("strong_bull", 0) + b.get("weak_bull", 0) +
                                    b.get("strong_bear", 0) + b.get("weak_bear", 0) for b in bins)
                    bull_vol  = sum(b.get("strong_bull", 0) + b.get("weak_bull", 0) for b in bins)
                    row["whale_bull_pct"] = round(bull_vol / total_vol * 100, 2) if total_vol > 0 else 0

            # ── Expiry summary max pain cross-check ───────────
            es = eng.get("expiry_summary", [])
            if es:
                # Nearest expiry max pain (may differ from weekly)
                row["max_pain"] = float(es[0].get("max_pain", row["max_pain"]))

        # ── POST to ORDS ──────────────────────────────────────
        url = f"{_ORDS_BASE}/{_TABLE}/"
        r   = requests.post(
            url,
            auth=(_ORDS_USER, _get_pass()),
            json=row,
            timeout=10
        )
        if r.status_code in (200, 201):
            print(f"  [{row['ticker']}] DB1 snapshot saved (id={r.json().get('id','?')})")
            return True
        else:
            # Silent — don't block the sweep
            print(f"  [{row['ticker']}] DB1 snapshot failed ({r.status_code}) — continuing")
            return False

    except Exception as e:
        # Always silent — never block the sweep
        print(f"  [DB1] Snapshot error (non-fatal): {str(e)[:80]}")
        return False


def fetch_snapshots(ticker: str = None, date_from: str = None, date_to: str = None, limit: int = 100) -> list:
    """
    Query stored snapshots from Oracle DB1.

    Returns list of snapshot dicts.
    """
    try:
        url = f"{_ORDS_BASE}/{_TABLE}/"
        q_parts = []
        if ticker:
            q_parts.append(f'"ticker":"{ticker}"')
        if date_from:
            q_parts.append(f'"scan_date":{{"{chr(36)}gte":"{date_from}"}}')
        if date_to:
            q_parts.append(f'"scan_date":{{"{chr(36)}lte":"{date_to}"}}')

        params = {"limit": limit, "orderby": "-id"}   # newest first
        if q_parts:
            params["q"] = "{" + ",".join(q_parts) + "}"

        r = requests.get(url, auth=(_ORDS_USER, _get_pass()), params=params, timeout=15)
        if r.status_code == 200:
            return r.json().get("items", [])
        return []
    except Exception as e:
        print(f"[DB1] Fetch error: {str(e)[:80]}")
        return []


def count_snapshots() -> int:
    """Return total number of stored snapshots."""
    try:
        url = f"{_ORDS_BASE}/{_TABLE}/"
        r   = requests.get(url, auth=(_ORDS_USER, _get_pass()), params={"limit": 1}, timeout=10)
        if r.status_code == 200:
            return r.json().get("count", 0)
        return 0
    except Exception:
        return 0


# ══════════════════════════════════════════════════════════════════
# V2 TABLES — intraday_snapshots / backtest_results / news_events
# Uses /_/sql for inserts (ORDS REST POST cannot handle Oracle
# DATE/TIMESTAMP NOT NULL columns via JSON in this ORDS version).
# GET/read still uses the ORDS REST collection endpoint.
# ══════════════════════════════════════════════════════════════════

def _sql_exec(stmt: str) -> bool:
    """Execute one SQL statement via ORDS /_/sql. Returns True on success."""
    try:
        url = f"{_ORDS_BASE}/_/sql"
        r = requests.post(
            url,
            auth=(_ORDS_USER, _get_pass()),
            json={"statementText": stmt.strip()},
            timeout=20,
        )
        if r.status_code in (200, 201):
            body = r.json()
            # Check for ORA- errors in the response items
            for item in body.get("items", []):
                err = item.get("errorDetails", "")
                if err:
                    print(f"  [DB1] SQL error: {err[:120]}")
                    return False
            return True
        return False
    except Exception as e:
        print(f"  [DB1] _sql_exec error: {str(e)[:80]}")
        return False


def save_intraday_snapshot(
    ticker: str,
    snap_ts: datetime.datetime,
    open_price: float,
    high_price: float,
    low_price: float,
    close_price: float,
    volume: int,
    snap_time: str = None,
    gex_zero: float = None,
    spot: float = None,
    vix_level: float = None,
) -> bool:
    """
    Write one 15-minute bar + GEX/VIX overlay to intraday_snapshots.

    snap_ts   — exact datetime of the bar close
    All price fields are NUMBER(12,4).
    Fails silently — never blocks the main sweep.
    """
    try:
        snap_time = snap_time or snap_ts.strftime("%H:%M")
        ts_str    = snap_ts.strftime("%Y-%m-%d %H:%M:%S")

        def _n(v) -> str:
            return str(float(v)) if v is not None else "NULL"

        stmt = (
            "INSERT INTO intraday_snapshots "
            "(ticker, snap_ts, snap_date, snap_time, "
            " open_price, high_price, low_price, close_price, volume, "
            " gex_zero, spot, vix_level) "
            f"VALUES ("
            f"'{ticker}', "
            f"TO_TIMESTAMP('{ts_str}', 'YYYY-MM-DD HH24:MI:SS'), "
            f"TRUNC(TO_TIMESTAMP('{ts_str}', 'YYYY-MM-DD HH24:MI:SS')), "
            f"'{snap_time}', "
            f"{_n(open_price)}, {_n(high_price)}, {_n(low_price)}, {_n(close_price)}, "
            f"{int(volume)}, "
            f"{_n(gex_zero)}, {_n(spot)}, {_n(vix_level)}"
            ")"
        )
        ok = _sql_exec(stmt)
        if ok:
            _sql_exec("COMMIT")
            print(f"  [{ticker}] intraday_snapshot saved ({snap_time})")
        else:
            print(f"  [{ticker}] intraday_snapshot failed — continuing")
        return ok
    except Exception as e:
        print(f"  [DB1] intraday_snapshot error (non-fatal): {str(e)[:80]}")
        return False


def save_backtest_result(
    ticker: str,
    module: str,
    predicted_value: float,
    actual_value: float,
    pct_distance: float,
    grade: str,
    direction_correct: int,
    scan_date: datetime.date = None,
    scored_at: datetime.datetime = None,
) -> bool:
    """
    Record one Q-Matrix backtest outcome to backtest_results.

    module           — 'max_pain' | 'gex_zero' | 'whale_poc' | 'iv_skew' | 'whale_bull'
    grade            — 'BULLSEYE' | 'HIT' | 'CLOSE' | 'MISS'
    direction_correct — 1 or 0
    Fails silently — never blocks the main sweep.
    """
    try:
        today    = scan_date or datetime.date.today()
        scored   = scored_at or datetime.datetime.now()
        date_str = today.strftime("%Y-%m-%d")
        ts_str   = scored.strftime("%Y-%m-%d %H:%M:%S")
        module   = str(module)[:50]
        grade    = str(grade)[:20]
        ticker   = str(ticker)[:20]

        stmt = (
            "INSERT INTO backtest_results "
            "(scan_date, ticker, module, predicted_value, actual_value, "
            " pct_distance, grade, direction_correct, scored_at) "
            f"VALUES ("
            f"TO_DATE('{date_str}', 'YYYY-MM-DD'), "
            f"'{ticker}', "
            f"'{module}', "
            f"{float(predicted_value)}, "
            f"{float(actual_value)}, "
            f"{float(pct_distance)}, "
            f"'{grade}', "
            f"{int(direction_correct)}, "
            f"TO_TIMESTAMP('{ts_str}', 'YYYY-MM-DD HH24:MI:SS')"
            ")"
        )
        ok = _sql_exec(stmt)
        if ok:
            _sql_exec("COMMIT")
            print(f"  [{ticker}] backtest_result saved ({module} -> {grade})")
        else:
            print(f"  [{ticker}] backtest_result failed — continuing")
        return ok
    except Exception as e:
        print(f"  [DB1] backtest_result error (non-fatal): {str(e)[:80]}")
        return False


def save_news_event(
    event_date: datetime.date,
    event_type: str,
    event_name: str,
    impact: str,
    ticker: str = None,
    created_at: datetime.datetime = None,
) -> bool:
    """
    Store one macro or earnings calendar event in news_events.

    ticker     — None for macro events (FED, CPI, OPEX, JOBS)
    event_type — 'EARNINGS' | 'FED' | 'CPI' | 'OPEX' | 'JOBS'
    impact     — 'HIGH' | 'MEDIUM' | 'LOW'
    Fails silently — never blocks the main sweep.
    """
    try:
        created  = created_at or datetime.datetime.now()
        date_str = event_date.strftime("%Y-%m-%d")
        ts_str   = created.strftime("%Y-%m-%d %H:%M:%S")
        event_type = str(event_type)[:50]
        impact     = str(impact)[:20]
        # Escape single quotes in event_name
        safe_name  = str(event_name)[:200].replace("'", "''")
        ticker_sql = f"'{str(ticker)[:20]}'" if ticker else "NULL"

        stmt = (
            "INSERT INTO news_events "
            "(event_date, ticker, event_type, event_name, impact, created_at) "
            f"VALUES ("
            f"TO_DATE('{date_str}', 'YYYY-MM-DD'), "
            f"{ticker_sql}, "
            f"'{event_type}', "
            f"'{safe_name}', "
            f"'{impact}', "
            f"TO_TIMESTAMP('{ts_str}', 'YYYY-MM-DD HH24:MI:SS')"
            ")"
        )
        ok = _sql_exec(stmt)
        if ok:
            _sql_exec("COMMIT")
            label = ticker or "MACRO"
            print(f"  [{label}] news_event saved ({event_type}: {event_name[:40]})")
        else:
            print(f"  news_event failed — continuing")
        return ok
    except Exception as e:
        print(f"  [DB1] news_event error (non-fatal): {str(e)[:80]}")
        return False


def fetch_intraday_snapshots(ticker: str = None, limit: int = 100) -> list:
    """Query intraday_snapshots via ORDS REST. Returns list of row dicts."""
    try:
        url    = f"{_ORDS_BASE}/intraday_snapshots/"
        params = {"limit": limit}
        if ticker:
            params["q"] = '{' + f'"ticker":"{ticker}"' + '}'
        r = requests.get(url, auth=(_ORDS_USER, _get_pass()), params=params, timeout=15)
        return r.json().get("items", []) if r.status_code == 200 else []
    except Exception as e:
        print(f"[DB1] fetch_intraday_snapshots error: {str(e)[:80]}")
        return []


def fetch_backtest_results(ticker: str = None, module: str = None, limit: int = 100) -> list:
    """Query backtest_results via ORDS REST. Returns list of row dicts."""
    try:
        url     = f"{_ORDS_BASE}/backtest_results/"
        q_parts = []
        if ticker:
            q_parts.append(f'"ticker":"{ticker}"')
        if module:
            q_parts.append(f'"module":"{module}"')
        params = {"limit": limit}
        if q_parts:
            params["q"] = "{" + ",".join(q_parts) + "}"
        r = requests.get(url, auth=(_ORDS_USER, _get_pass()), params=params, timeout=15)
        return r.json().get("items", []) if r.status_code == 200 else []
    except Exception as e:
        print(f"[DB1] fetch_backtest_results error: {str(e)[:80]}")
        return []


def fetch_news_events(ticker: str = None, event_type: str = None, limit: int = 100) -> list:
    """Query news_events via ORDS REST. Returns list of row dicts."""
    try:
        url     = f"{_ORDS_BASE}/news_events/"
        q_parts = []
        if ticker:
            q_parts.append(f'"ticker":"{ticker}"')
        if event_type:
            q_parts.append(f'"event_type":"{event_type}"')
        params = {"limit": limit}
        if q_parts:
            params["q"] = "{" + ",".join(q_parts) + "}"
        r = requests.get(url, auth=(_ORDS_USER, _get_pass()), params=params, timeout=15)
        return r.json().get("items", []) if r.status_code == 200 else []
    except Exception as e:
        print(f"[DB1] fetch_news_events error: {str(e)[:80]}")
        return []
