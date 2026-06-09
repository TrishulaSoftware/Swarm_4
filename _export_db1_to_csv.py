#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# PYTHONIOENCODING=utf-8
"""
=================================================================
R2-9 STEP 1 -- DB1 qmatrix_snapshots -> CSV EXPORTER
=================================================================
Fetches ALL rows from qmatrix_snapshots via ORDS (paginated)
and writes to ml_training_data.csv with all numeric ML columns.

Run: python _export_db1_to_csv.py
Output: H:\\Trishula\\Swarm_4_Integration\\Salvo_Staging\\ml_training_data.csv
=================================================================
"""

import os
import csv
import json
import requests
import datetime
from pathlib import Path

# ── ORDS Config ──────────────────────────────────────────────────
ORDS_BASE = "https://g275356d1414552-trishulapicks.adb.us-ashburn-1.oraclecloudapps.com/ords/admin"
ORDS_USER = "ADMIN"
ORDS_PASS = "C1iffyHu5tl3!!!"
TABLE     = "qmatrix_snapshots"

# ── Output paths ─────────────────────────────────────────────────
BASE_DIR  = Path(r"H:\Trishula\Swarm_4_Integration\Salvo_Staging")
OUT_CSV   = BASE_DIR / "ml_training_data.csv"

# ── Columns to export ────────────────────────────────────────────
# All columns in DB schema order — numeric ML features highlighted
ALL_COLUMNS = [
    "id", "scan_date", "scan_time", "ticker", "expiry",
    # ── Core numeric ML features ──────────────────────────────────
    "spot",           # Current price
    "max_pain",       # Max pain strike
    "call_wall",      # Largest call GEX strike
    "put_wall",       # Largest put GEX strike
    "net_gex_m",      # Net GEX in millions (positive=long gamma)
    "pc_ratio",       # Put/Call ratio
    "gex_zero",       # GEX zero-crossing level
    "iv_skew_pct",    # ATM IV skew (put IV - call IV)
    "whale_poc",      # Whale volume POC price
    "whale_bull_pct", # % of whale vol that was bullish
    "vol_spike",      # 0/1 volume spike flag
    "whale_flow_flag",# 0/1 unusual whale flow flag
    # ── Additional context columns ───────────────────────────────
    "wvf_val",
    "squeeze_on",
    "top_flow_side",
    "top_flow_k",
    "top_flow_ratio",
    "stocktwits_bull_pct",
    "days_to_earnings",
    "scan_ts",
]

def fetch_all_rows(page_size: int = 500) -> list:
    """Paginate through all qmatrix_snapshots rows via ORDS."""
    all_rows = []
    offset   = 0
    page_num = 0

    print(f"[DB1] Starting paginated fetch from {TABLE} ...")
    while True:
        page_num += 1
        url    = f"{ORDS_BASE}/{TABLE}/"
        params = {
            "limit":   page_size,
            "offset":  offset,
            "orderby": "id",  # oldest first for consistent ordering
        }
        try:
            r = requests.get(
                url,
                auth=(ORDS_USER, ORDS_PASS),
                params=params,
                timeout=30
            )
            if r.status_code != 200:
                print(f"  [ERR] HTTP {r.status_code} on page {page_num} — stopping.")
                break

            body  = r.json()
            items = body.get("items", [])
            count = body.get("count", 0)
            total = body.get("totalResults", "?")

            print(f"  [PAGE {page_num}] Fetched {len(items)} rows "
                  f"(offset={offset}, total={total})")

            if not items:
                break

            all_rows.extend(items)
            offset += len(items)

            # ORDS pagination: check if there's a 'next' link
            links = body.get("links", [])
            has_next = any(lk.get("rel") == "next" for lk in links)
            if not has_next or len(items) < page_size:
                break

        except requests.exceptions.Timeout:
            print(f"  [WARN] Timeout on page {page_num} — retrying once...")
            import time; time.sleep(5)
            try:
                r = requests.get(url, auth=(ORDS_USER, ORDS_PASS),
                                 params=params, timeout=60)
                body  = r.json()
                items = body.get("items", [])
                if not items:
                    break
                all_rows.extend(items)
                offset += len(items)
            except Exception as e:
                print(f"  [ERR] Retry failed: {e}")
                break
        except Exception as e:
            print(f"  [ERR] Fetch error on page {page_num}: {e}")
            break

    print(f"[DB1] Total rows fetched: {len(all_rows)}")
    return all_rows


def normalize_row(row: dict) -> dict:
    """Normalize a raw ORDS row to our export schema."""
    out = {}
    for col in ALL_COLUMNS:
        val = row.get(col)
        if val is None:
            out[col] = ""
        else:
            # Oracle returns numbers as floats/ints, timestamps as strings
            out[col] = val
    return out


def write_csv(rows: list, path: Path) -> int:
    """Write normalized rows to CSV. Returns count written."""
    if not rows:
        print("[WARN] No rows to write!")
        return 0

    # Build fieldnames — use ALL_COLUMNS order
    fieldnames = ALL_COLUMNS

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        written = 0
        for row in rows:
            norm = normalize_row(row)
            writer.writerow(norm)
            written += 1

    return written


def print_summary(rows: list):
    """Print basic data summary."""
    if not rows:
        return

    numeric_cols = [
        "spot", "max_pain", "call_wall", "put_wall", "net_gex_m",
        "pc_ratio", "gex_zero", "iv_skew_pct", "whale_poc",
        "whale_bull_pct", "vol_spike", "whale_flow_flag"
    ]

    print(f"\n{'='*60}")
    print(f"  EXPORT SUMMARY — {len(rows)} rows")
    print(f"{'='*60}")

    # Ticker distribution
    tickers = {}
    dates   = set()
    for r in rows:
        t = r.get("ticker", "UNKNOWN")
        tickers[t] = tickers.get(t, 0) + 1
        d = r.get("scan_date", "")
        if d:
            dates.add(d)

    print(f"\n  Tickers ({len(tickers)} unique):")
    for tk, cnt in sorted(tickers.items(), key=lambda x: -x[1])[:15]:
        print(f"    {tk:8s}  {cnt:3d} rows")

    print(f"\n  Date range: {min(dates) if dates else 'N/A'} → {max(dates) if dates else 'N/A'}")
    print(f"  Distinct scan dates: {len(dates)}")

    # Null coverage for ML features
    print(f"\n  ML Feature Coverage (non-null %):")
    for col in numeric_cols:
        non_null = sum(1 for r in rows if r.get(col) is not None and r.get(col) != "")
        pct = non_null / len(rows) * 100
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"    {col:22s} {bar}  {pct:5.1f}% ({non_null}/{len(rows)})")

    print(f"\n  Output: {OUT_CSV}")
    print(f"{'='*60}\n")


def main():
    print(f"\n{'='*60}")
    print("  R2-9 STEP 1: DB1 -> CSV EXPORT")
    print(f"  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # 1. Fetch all rows
    rows = fetch_all_rows(page_size=500)

    if not rows:
        print("[FATAL] No rows returned. Check ORDS connectivity.")
        return False

    # 2. Write CSV
    print(f"\n[CSV] Writing {len(rows)} rows to {OUT_CSV} ...")
    written = write_csv(rows, OUT_CSV)
    print(f"[CSV] Wrote {written} rows -> {OUT_CSV}")

    # 3. Print summary
    print_summary(rows)

    # 4. Also dump raw JSON for debugging
    raw_json = BASE_DIR / "ml_raw_snapshots.json"
    with open(raw_json, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, default=str)
    print(f"[JSON] Raw dump -> {raw_json}")

    return True


if __name__ == "__main__":
    ok = main()
    exit(0 if ok else 1)
