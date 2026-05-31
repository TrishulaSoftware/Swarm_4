#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=================================================================
R2-9 STEP 2 — ML FEATURE ENGINEERING
=================================================================
Loads ml_training_data.csv and engineers derived features for
the Q-Matrix ML pipeline.

Derived features:
  spot_to_maxpain_pct    = (spot - max_pain) / spot * 100
  spot_to_gexzero_pct    = (spot - gex_zero) / spot * 100  [if gex_zero > 0]
  iv_skew_abs            = abs(iv_skew_pct)
  is_bullish_whale        = 1 if whale_bull_pct > 52 else 0
  gex_regime             = 1 if net_gex_m > 0 else 0
  maxpain_distance_pct   = abs(spot - max_pain) / spot * 100

Target column (placeholder):
  price_within_1pct_maxpain — None until backtest fills in outcomes

Run: python _ml_feature_engineering.py
Inputs:  ml_training_data.csv
Outputs: ml_features.csv
=================================================================
"""

import os
import math
import datetime
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────
BASE_DIR   = Path(r"H:\Trishula\Swarm_4_Integration\Salvo_Staging")
INPUT_CSV  = BASE_DIR / "ml_training_data.csv"
OUTPUT_CSV = BASE_DIR / "ml_features.csv"

# ── Feature columns ──────────────────────────────────────────────
RAW_NUMERIC_COLS = [
    "spot", "max_pain", "call_wall", "put_wall", "net_gex_m",
    "pc_ratio", "gex_zero", "iv_skew_pct", "whale_poc",
    "whale_bull_pct", "vol_spike", "whale_flow_flag",
    "wvf_val", "squeeze_on", "top_flow_k", "top_flow_ratio",
    "stocktwits_bull_pct", "days_to_earnings",
]

DERIVED_COLS = [
    "spot_to_maxpain_pct",
    "spot_to_gexzero_pct",
    "iv_skew_abs",
    "is_bullish_whale",
    "gex_regime",
    "maxpain_distance_pct",
]

ID_COLS = ["id", "scan_date", "scan_time", "ticker", "expiry"]

TARGET_COL = "price_within_1pct_maxpain"  # placeholder — None until backfilled


def safe_float(val, default=None):
    """Convert value to float, returning default on failure."""
    if val is None or val == "" or val == "None":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val, default=None):
    """Convert value to int, returning default on failure."""
    if val is None or val == "" or val == "None":
        return default
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return default


def engineer_features(row: dict) -> dict:
    """
    Given a raw CSV row dict, compute all derived features.
    Returns a new dict with raw + derived columns.
    """
    out = {}

    # ── Identity columns ──────────────────────────────────────────
    for col in ID_COLS:
        out[col] = row.get(col, "")

    # ── Raw numeric features ──────────────────────────────────────
    spot           = safe_float(row.get("spot"))
    max_pain       = safe_float(row.get("max_pain"))
    call_wall      = safe_float(row.get("call_wall"))
    put_wall       = safe_float(row.get("put_wall"))
    net_gex_m      = safe_float(row.get("net_gex_m"))
    pc_ratio       = safe_float(row.get("pc_ratio"))
    gex_zero       = safe_float(row.get("gex_zero"))
    iv_skew_pct    = safe_float(row.get("iv_skew_pct"))
    whale_poc      = safe_float(row.get("whale_poc"))
    whale_bull_pct = safe_float(row.get("whale_bull_pct"))
    vol_spike      = safe_int(row.get("vol_spike"))
    whale_flow_flag= safe_int(row.get("whale_flow_flag"))
    wvf_val        = safe_float(row.get("wvf_val"))
    squeeze_on     = safe_int(row.get("squeeze_on"))
    top_flow_k     = safe_float(row.get("top_flow_k"))
    top_flow_ratio = safe_float(row.get("top_flow_ratio"))
    st_bull_pct    = safe_float(row.get("stocktwits_bull_pct"))
    days_to_earn   = safe_int(row.get("days_to_earnings"))

    out["spot"]            = spot
    out["max_pain"]        = max_pain
    out["call_wall"]       = call_wall
    out["put_wall"]        = put_wall
    out["net_gex_m"]       = net_gex_m
    out["pc_ratio"]        = pc_ratio
    out["gex_zero"]        = gex_zero
    out["iv_skew_pct"]     = iv_skew_pct
    out["whale_poc"]       = whale_poc
    out["whale_bull_pct"]  = whale_bull_pct
    out["vol_spike"]       = vol_spike
    out["whale_flow_flag"] = whale_flow_flag
    out["wvf_val"]         = wvf_val
    out["squeeze_on"]      = squeeze_on
    out["top_flow_k"]      = top_flow_k
    out["top_flow_ratio"]  = top_flow_ratio
    out["stocktwits_bull_pct"] = st_bull_pct
    out["days_to_earnings"]    = days_to_earn

    # ── Derived features ──────────────────────────────────────────

    # 1. spot_to_maxpain_pct = (spot - max_pain) / spot * 100
    if spot and spot != 0 and max_pain is not None:
        out["spot_to_maxpain_pct"] = round((spot - max_pain) / spot * 100, 4)
    else:
        out["spot_to_maxpain_pct"] = None

    # 2. spot_to_gexzero_pct = (spot - gex_zero) / spot * 100  [only if gex_zero > 0]
    if spot and spot != 0 and gex_zero and gex_zero > 0:
        out["spot_to_gexzero_pct"] = round((spot - gex_zero) / spot * 100, 4)
    else:
        out["spot_to_gexzero_pct"] = None

    # 3. iv_skew_abs = abs(iv_skew_pct)
    if iv_skew_pct is not None:
        out["iv_skew_abs"] = round(abs(iv_skew_pct), 4)
    else:
        out["iv_skew_abs"] = None

    # 4. is_bullish_whale = 1 if whale_bull_pct > 52 else 0
    if whale_bull_pct is not None:
        out["is_bullish_whale"] = 1 if whale_bull_pct > 52 else 0
    else:
        out["is_bullish_whale"] = None

    # 5. gex_regime = 1 if net_gex_m > 0 else 0
    #    (positive GEX = long gamma = market maker pinning)
    if net_gex_m is not None:
        out["gex_regime"] = 1 if net_gex_m > 0 else 0
    else:
        out["gex_regime"] = None

    # 6. maxpain_distance_pct = abs(spot - max_pain) / spot * 100
    if spot and spot != 0 and max_pain is not None:
        out["maxpain_distance_pct"] = round(abs(spot - max_pain) / spot * 100, 4)
    else:
        out["maxpain_distance_pct"] = None

    # ── Target column (placeholder) ───────────────────────────────
    # Will be backfilled by _backtest_qmatrix_accuracy.py once
    # we have enough historical outcome data (T+1 close vs max pain)
    out[TARGET_COL] = None

    return out


def compute_distributions(rows: list, col: str) -> dict:
    """Compute basic stats for a numeric column."""
    vals = [r[col] for r in rows if r.get(col) is not None]
    if not vals:
        return {"count": 0, "null_count": len(rows), "min": None, "max": None,
                "mean": None, "median": None, "std": None}
    n = len(vals)
    null_n = len(rows) - n
    total = sum(vals)
    mean  = total / n
    sorted_v = sorted(vals)
    median = sorted_v[n // 2] if n % 2 != 0 else (sorted_v[n//2 - 1] + sorted_v[n//2]) / 2
    variance = sum((v - mean) ** 2 for v in vals) / n
    std = math.sqrt(variance)
    return {
        "count":      n,
        "null_count": null_n,
        "min":        round(min(vals), 4),
        "max":        round(max(vals), 4),
        "mean":       round(mean, 4),
        "median":     round(median, 4),
        "std":        round(std, 4),
    }


def print_feature_summary(rows: list):
    """Print shape, null counts, and distributions for all features."""
    all_feature_cols = (
        RAW_NUMERIC_COLS + DERIVED_COLS + [TARGET_COL]
    )

    n_rows = len(rows)
    n_cols = len(all_feature_cols) + len(ID_COLS)

    print(f"\n{'='*70}")
    print(f"  ML FEATURE ENGINEERING SUMMARY")
    print(f"  Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")
    print(f"\n  Shape: {n_rows:,} rows × {n_cols} columns")
    print(f"  Raw features:     {len(RAW_NUMERIC_COLS)}")
    print(f"  Derived features: {len(DERIVED_COLS)}")
    print(f"  Target column:    {TARGET_COL} (None until backtest fills)")

    # Ticker breakdown
    tickers = {}
    for r in rows:
        t = r.get("ticker", "?")
        tickers[t] = tickers.get(t, 0) + 1
    print(f"\n  Tickers: {', '.join(sorted(tickers.keys()))}")

    # Date range
    dates = [r.get("scan_date", "") for r in rows if r.get("scan_date")]
    if dates:
        print(f"  Date range: {min(dates)} → {max(dates)}")

    # Feature distributions
    print(f"\n  {'FEATURE':<26} {'COUNT':>6} {'NULLS':>6} {'MIN':>10} {'MAX':>10} "
          f"{'MEAN':>10} {'MEDIAN':>10} {'STD':>10}")
    print(f"  {'-'*96}")

    for col in all_feature_cols:
        stats = compute_distributions(rows, col)
        if stats["count"] == 0:
            print(f"  {col:<26} {'0':>6} {stats['null_count']:>6} "
                  f"{'N/A':>10} {'N/A':>10} {'N/A':>10} {'N/A':>10} {'N/A':>10}")
        else:
            print(f"  {col:<26} {stats['count']:>6,} {stats['null_count']:>6} "
                  f"{str(stats['min']):>10} {str(stats['max']):>10} "
                  f"{str(stats['mean']):>10} {str(stats['median']):>10} "
                  f"{str(stats['std']):>10}")

    # GEX regime breakdown
    regime_rows = [r for r in rows if r.get("gex_regime") is not None]
    if regime_rows:
        long_gamma  = sum(1 for r in regime_rows if r["gex_regime"] == 1)
        short_gamma = sum(1 for r in regime_rows if r["gex_regime"] == 0)
        print(f"\n  GEX Regime breakdown:")
        print(f"    Long Gamma  (net_gex_m > 0): {long_gamma:4d}  "
              f"({long_gamma/len(regime_rows)*100:.1f}%)")
        print(f"    Short Gamma (net_gex_m ≤ 0): {short_gamma:4d}  "
              f"({short_gamma/len(regime_rows)*100:.1f}%)")

    # Bullish whale breakdown
    whale_rows = [r for r in rows if r.get("is_bullish_whale") is not None]
    if whale_rows:
        bull_whale = sum(1 for r in whale_rows if r["is_bullish_whale"] == 1)
        bear_whale = sum(1 for r in whale_rows if r["is_bullish_whale"] == 0)
        print(f"\n  Whale Flow breakdown:")
        print(f"    Bullish (whale_bull_pct > 52): {bull_whale:4d}  "
              f"({bull_whale/len(whale_rows)*100:.1f}%)")
        print(f"    Bearish (whale_bull_pct ≤ 52): {bear_whale:4d}  "
              f"({bear_whale/len(whale_rows)*100:.1f}%)")

    # Target label coverage
    labeled = sum(1 for r in rows if r.get(TARGET_COL) is not None)
    print(f"\n  Target Label Coverage:")
    print(f"    Labeled:   {labeled:4d} / {n_rows} ({labeled/n_rows*100:.1f}%)")
    print(f"    Unlabeled: {n_rows - labeled:4d} / {n_rows}")
    print(f"\n  NOTE: Target labels require T+1 price outcomes.")
    print(f"        Run _backtest_qmatrix_accuracy.py to backfill.")

    print(f"\n  Output: {OUTPUT_CSV}")
    print(f"{'='*70}\n")


def main():
    import csv

    print(f"\n{'='*60}")
    print("  R2-9 STEP 2: ML FEATURE ENGINEERING")
    print(f"  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # ── Load raw CSV ──────────────────────────────────────────────
    if not INPUT_CSV.exists():
        print(f"[FATAL] Input not found: {INPUT_CSV}")
        print("  Run _export_db1_to_csv.py first.")
        return False

    raw_rows = []
    with open(INPUT_CSV, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_rows.append(dict(row))

    print(f"[CSV] Loaded {len(raw_rows)} raw rows from {INPUT_CSV}")

    if not raw_rows:
        print("[FATAL] No rows in input CSV.")
        return False

    # ── Engineer features ─────────────────────────────────────────
    print("[FEAT] Engineering features...")
    engineered = []
    skipped = 0
    for row in raw_rows:
        # Skip rows with no spot price (un-parseable)
        if not row.get("spot"):
            skipped += 1
            continue
        feat_row = engineer_features(row)
        engineered.append(feat_row)

    print(f"[FEAT] Engineered {len(engineered)} rows ({skipped} skipped - no spot)")

    # ── Write output CSV ──────────────────────────────────────────
    fieldnames = (
        ID_COLS +
        RAW_NUMERIC_COLS +
        DERIVED_COLS +
        [TARGET_COL]
    )

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in engineered:
            writer.writerow({k: ("" if v is None else v) for k, v in row.items()})

    print(f"[CSV] ✓ Wrote {len(engineered)} rows → {OUTPUT_CSV}")

    # ── Print summary ──────────────────────────────────────────────
    print_feature_summary(engineered)

    return True


if __name__ == "__main__":
    ok = main()
    exit(0 if ok else 1)
