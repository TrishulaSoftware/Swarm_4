#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=================================================================
R2-9 STEP 4 — SAGEMAKER AUTOPILOT PREP
=================================================================
Checks current ML dataset readiness and pre-stages the AutoPilot
configuration JSON ready to submit when we have enough labeled data.

Current state:
  - 100+ rows collected in qmatrix_snapshots
  - 0 rows labeled (target = price_within_1pct_maxpain)
  - Needed: 500+ labeled rows for AutoPilot binary classification

This script:
  1. Reads ml_features.csv to assess current state
  2. Computes projected readiness date based on scan rate
  3. Saves autopilot_config.json (ready to submit when labels arrive)
  4. Reports current status

Run: python _sagemaker_prep.py
=================================================================
"""

import os
import csv
import json
import datetime
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────
BASE_DIR         = Path(r"H:\Trishula\Swarm_4_Integration\Salvo_Staging")
FEATURES_CSV     = BASE_DIR / "ml_features.csv"
RAW_CSV          = BASE_DIR / "ml_training_data.csv"
AUTOPILOT_CONFIG = BASE_DIR / "autopilot_config.json"

# ── S3 / SageMaker Config ─────────────────────────────────────────
S3_BUCKET        = "trishula-ml-data"
S3_INPUT_PATH    = f"s3://{S3_BUCKET}/qmatrix/v1/ml_features.csv"
S3_OUTPUT_PATH   = f"s3://{S3_BUCKET}/sagemaker/autopilot/"
AWS_REGION       = "us-east-2"

# ── AutoPilot Requirements ────────────────────────────────────────
MIN_LABELED_ROWS     = 500    # Minimum for AutoPilot binary classification
MIN_LABELED_POS      = 50     # Minimum positive class samples
TARGET_COLUMN        = "price_within_1pct_maxpain"

# ── Scan rate estimation ──────────────────────────────────────────
# Scanner runs 3x/day (09:30, 12:00, 15:30), 6 tickers per run
# = ~18 snapshots/day on trading days (~252/year)
SCANS_PER_DAY        = 18
TRADING_DAYS_PER_WEEK = 5

# ── AutoPilot job name ────────────────────────────────────────────
JOB_NAME = f"trishula-qmatrix-autopilot-{datetime.date.today().strftime('%Y%m%d')}"


def load_features() -> list:
    """Load ml_features.csv into list of dicts."""
    if not FEATURES_CSV.exists():
        print(f"[WARN] {FEATURES_CSV.name} not found — trying raw CSV...")
        if RAW_CSV.exists():
            with open(RAW_CSV, "r", encoding="utf-8", newline="") as f:
                return list(csv.DictReader(f))
        return []

    with open(FEATURES_CSV, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def assess_readiness(rows: list) -> dict:
    """Assess current ML dataset readiness."""
    total_rows = len(rows)

    # Label coverage
    labeled_rows = [r for r in rows if r.get(TARGET_COLUMN, "") not in ("", "None", None)]
    labeled_pos  = [r for r in labeled_rows if str(r.get(TARGET_COLUMN, "")) == "1"]
    labeled_neg  = [r for r in labeled_rows if str(r.get(TARGET_COLUMN, "")) == "0"]

    n_labeled = len(labeled_rows)
    n_pos     = len(labeled_pos)
    n_neg     = len(labeled_neg)

    # Feature coverage (for key ML columns)
    key_features = [
        "spot", "max_pain", "net_gex_m", "whale_bull_pct",
        "spot_to_maxpain_pct", "gex_regime", "is_bullish_whale",
        "maxpain_distance_pct",
    ]
    feature_coverage = {}
    for feat in key_features:
        non_null = sum(1 for r in rows if r.get(feat, "") not in ("", "None", None))
        feature_coverage[feat] = {
            "count":    non_null,
            "coverage": round(non_null / total_rows * 100, 1) if total_rows > 0 else 0
        }

    # Date range
    dates = sorted(set(r.get("scan_date", "") for r in rows if r.get("scan_date")))

    # Scan rate (rows added per trading day)
    if len(dates) >= 2:
        from_date  = datetime.datetime.strptime(dates[0],  "%Y-%m-%d")
        to_date    = datetime.datetime.strptime(dates[-1], "%Y-%m-%d")
        total_days = (to_date - from_date).days
        # Estimate trading days (~5/7 of calendar days)
        trading_days = max(1, int(total_days * 5 / 7))
        rows_per_day = round(total_rows / trading_days, 1)
    else:
        trading_days = 1
        rows_per_day = SCANS_PER_DAY

    # Projected rows needed for labels
    rows_needed_total    = max(0, MIN_LABELED_ROWS - n_labeled)
    days_to_readiness    = math.ceil(rows_needed_total / max(rows_per_day, 1))
    projected_ready_date = (datetime.date.today() +
                            datetime.timedelta(days=int(days_to_readiness * 7 / 5)))

    # Can we launch AutoPilot?
    can_launch = (n_labeled >= MIN_LABELED_ROWS and n_pos >= MIN_LABELED_POS)

    return {
        "total_rows":         total_rows,
        "labeled_rows":       n_labeled,
        "unlabeled_rows":     total_rows - n_labeled,
        "label_coverage_pct": round(n_labeled / total_rows * 100, 1) if total_rows > 0 else 0,
        "positive_labels":    n_pos,
        "negative_labels":    n_neg,
        "distinct_tickers":   len(set(r.get("ticker", "") for r in rows)),
        "distinct_dates":     len(dates),
        "date_from":          dates[0] if dates else "N/A",
        "date_to":            dates[-1] if dates else "N/A",
        "rows_per_day":       rows_per_day,
        "rows_needed_for_readiness": rows_needed_total,
        "days_to_readiness":  days_to_readiness,
        "projected_ready_date": projected_ready_date.strftime("%Y-%m-%d"),
        "can_launch_autopilot": can_launch,
        "feature_coverage":   feature_coverage,
        "features_available": len(key_features),
        "min_labeled_required": MIN_LABELED_ROWS,
    }


def build_autopilot_config(readiness: dict) -> dict:
    """
    Build the SageMaker AutoPilot job configuration JSON.
    This is staged now and ready to submit when labels arrive.
    """

    # Feature columns for AutoPilot (exclude ID and target)
    feature_cols = [
        # Raw Q-Matrix features
        "spot", "max_pain", "call_wall", "put_wall",
        "net_gex_m", "pc_ratio", "gex_zero", "iv_skew_pct",
        "whale_poc", "whale_bull_pct", "vol_spike", "whale_flow_flag",
        "wvf_val", "squeeze_on", "top_flow_ratio",
        "stocktwits_bull_pct", "days_to_earnings",
        # Derived features
        "spot_to_maxpain_pct", "spot_to_gexzero_pct",
        "iv_skew_abs", "is_bullish_whale", "gex_regime",
        "maxpain_distance_pct",
    ]

    config = {
        "job_name":         JOB_NAME,
        "problem_type":     "BinaryClassification",
        "target_column":    TARGET_COLUMN,
        "feature_columns":  feature_cols,
        "objective_metric": "F1",       # F1 best for imbalanced binary class
        "objective_type":   "Maximize",

        "input_data_config": {
            "s3_uri":          S3_INPUT_PATH,
            "content_type":    "text/csv",
            "compression":     "None",
            "split_type":      "Line",
            "header_present":  True,
        },

        "output_data_config": {
            "s3_output_path": S3_OUTPUT_PATH,
        },

        "auto_ml_job_config": {
            "completion_criteria": {
                "max_candidates":              100,    # Try up to 100 models
                "max_runtime_per_training_job": 3600,  # 1 hr per model
                "max_auto_ml_job_runtime_in_seconds": 86400,  # 24hr total cap
            },
            "security_config": {
                "enable_inter_container_traffic_encryption": False,
                "volume_kms_key_id": None,
            },
        },

        "role_arn": "arn:aws:iam::YOUR_ACCOUNT_ID:role/SageMakerExecutionRole",

        "tags": [
            {"Key": "project",   "Value": "trishula-qmatrix"},
            {"Key": "pipeline",  "Value": "r2-9-ml"},
            {"Key": "version",   "Value": "v1"},
        ],

        # ── Submission command (boto3 snippet) ──────────────────────
        "boto3_submit_snippet": """
import boto3
import json

with open('autopilot_config.json', 'r') as f:
    cfg = json.load(f)

sm = boto3.client('sagemaker', region_name='us-east-2')

response = sm.create_auto_ml_job(
    AutoMLJobName=cfg['job_name'],
    InputDataConfig=[{
        'DataSource': {
            'S3DataSource': {
                'S3DataType': 'S3Prefix',
                'S3Uri': cfg['input_data_config']['s3_uri'],
            }
        },
        'TargetAttributeName': cfg['target_column'],
        'ContentType':         cfg['input_data_config']['content_type'],
    }],
    OutputDataConfig={
        'S3OutputPath': cfg['output_data_config']['s3_output_path'],
    },
    ProblemType=cfg['problem_type'],
    AutoMLJobObjective={
        'MetricName': cfg['objective_metric'],
    },
    AutoMLJobConfig=cfg['auto_ml_job_config'],
    RoleArn=cfg['role_arn'],
    Tags=cfg['tags'],
)
print(f"AutoPilot job submitted: {response['AutoMLJobArn']}")
""",

        # ── Readiness status ────────────────────────────────────────
        "_readiness_at_config_creation": {
            "generated_at":          datetime.datetime.now().isoformat(),
            "total_rows":            readiness["total_rows"],
            "labeled_rows":          readiness["labeled_rows"],
            "label_coverage_pct":    readiness["label_coverage_pct"],
            "projected_ready_date":  readiness["projected_ready_date"],
            "can_launch_now":        readiness["can_launch_autopilot"],
        },
    }

    return config


def print_status_report(readiness: dict):
    """Print a formatted status report."""
    r = readiness

    print(f"\n{'='*65}")
    print("  SAGEMAKER AUTOPILOT READINESS REPORT")
    print(f"  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*65}")

    print(f"\n  📊 CURRENT DATASET")
    print(f"  {'─'*40}")
    print(f"    Total rows collected:  {r['total_rows']:>6,}")
    print(f"    Labeled rows:          {r['labeled_rows']:>6,}  ({r['label_coverage_pct']}%)")
    print(f"    Unlabeled rows:        {r['unlabeled_rows']:>6,}")
    print(f"    Positive labels:       {r['positive_labels']:>6,}")
    print(f"    Negative labels:       {r['negative_labels']:>6,}")
    print(f"    Distinct tickers:      {r['distinct_tickers']:>6,}")
    print(f"    Date range:            {r['date_from']} → {r['date_to']}")
    print(f"    Features available:    {r['features_available']:>6,}")

    print(f"\n  🎯 AUTOPILOT REQUIREMENTS")
    print(f"  {'─'*40}")
    print(f"    Min labeled rows:      {r['min_labeled_required']:>6,}")
    print(f"    Have:                  {r['labeled_rows']:>6,}")
    print(f"    Still needed:          {r['rows_needed_for_readiness']:>6,}")
    print(f"    Min positive samples:  {MIN_LABELED_POS:>6,}")

    print(f"\n  📈 SCAN RATE & PROJECTION")
    print(f"  {'─'*40}")
    print(f"    Rows per trading day:  ~{r['rows_per_day']:>5.1f}")
    print(f"    Rows/week (5 days):    ~{r['rows_per_day']*5:>5.0f}")
    print(f"    Rows/month (~21 days): ~{r['rows_per_day']*21:>5.0f}")
    print(f"    Days to readiness:     {r['days_to_readiness']:>6,} trading days")
    print(f"    Projected ready date:  {r['projected_ready_date']}")

    print(f"\n  ⚡ FEATURE COVERAGE")
    print(f"  {'─'*40}")
    for feat, stats in r["feature_coverage"].items():
        bar = "█" * int(stats["coverage"] / 5) + "░" * (20 - int(stats["coverage"] / 5))
        print(f"    {feat:<25} {bar}  {stats['coverage']:5.1f}%")

    status_sym  = "✅" if r["can_launch_autopilot"] else "⏳"
    status_text = "READY TO LAUNCH" if r["can_launch_autopilot"] else "ACCUMULATING DATA"
    print(f"\n  {status_sym} STATUS: {status_text}")

    if not r["can_launch_autopilot"]:
        print(f"\n  What's needed:")
        print(f"    1. Backfill {r['rows_needed_for_readiness']:,} more labeled rows")
        print(f"       → Run _backtest_qmatrix_accuracy.py to add T+1 outcomes")
        print(f"    2. Estimated arrival: {r['projected_ready_date']}")
        print(f"       (based on ~{r['rows_per_day']:.0f} scans/day × labeling backfill)")
        print(f"    3. Once ready, run: python _sagemaker_launch.py")

    print(f"\n  Config staged at: {AUTOPILOT_CONFIG}")
    print(f"{'='*65}\n")


def check_existing_jobs():
    """Check for any existing AutoPilot jobs in SageMaker."""
    try:
        import boto3

        _load_env_for_check()
        sm = boto3.client("sagemaker", region_name=AWS_REGION)
        response = sm.list_auto_ml_jobs(
            SortBy="CreationTime",
            SortOrder="Descending",
            MaxResults=5,
            NameContains="trishula",
        )
        jobs = response.get("AutoMLJobSummaries", [])
        if jobs:
            print(f"\n  [SAGEMAKER] Existing AutoPilot jobs:")
            for job in jobs:
                print(f"    {job['AutoMLJobName']}  → {job['AutoMLJobStatus']}  "
                      f"({job['CreationTime'].strftime('%Y-%m-%d')})")
        else:
            print(f"\n  [SAGEMAKER] No existing AutoPilot jobs found.")
        return jobs
    except Exception as e:
        print(f"\n  [SAGEMAKER] Could not check existing jobs: {e}")
        return []


def _load_env_for_check():
    """Load .env for boto3."""
    env_paths = [
        Path(r"H:\Trishula\Swarm_4_Integration\Swarm_4_SBM_FINAL INTEGRATION\Project-Swarm\trishula-market-data\.env"),
        BASE_DIR / ".env",
    ]
    for env_path in env_paths:
        if env_path.exists():
            try:
                for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        if key.startswith("AWS_") and key not in os.environ:
                            os.environ[key] = val
                return
            except Exception:
                pass


import math  # needed for ceil in assess_readiness


def main():
    print(f"\n{'='*60}")
    print("  R2-9 STEP 4: SAGEMAKER AUTOPILOT PREP")
    print(f"  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # ── Load features ─────────────────────────────────────────────
    rows = load_features()
    print(f"[DATA] Loaded {len(rows)} rows from feature dataset")

    if not rows:
        print("[FATAL] No data found. Run export + feature engineering first.")
        return False

    # ── Assess readiness ──────────────────────────────────────────
    readiness = assess_readiness(rows)

    # ── Print status report ───────────────────────────────────────
    print_status_report(readiness)

    # ── Build and save AutoPilot config ──────────────────────────
    config = build_autopilot_config(readiness)

    with open(AUTOPILOT_CONFIG, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, default=str)
    print(f"[CONFIG] ✓ AutoPilot config saved → {AUTOPILOT_CONFIG}")

    # ── Check existing SageMaker jobs ─────────────────────────────
    check_existing_jobs()

    # ── If enough labeled data — offer to launch ───────────────────
    if readiness["can_launch_autopilot"]:
        print("\n" + "="*65)
        print("  🚀 AUTOPILOT IS READY TO LAUNCH!")
        print("="*65)
        print(f"\n  Enough labeled data exists ({readiness['labeled_rows']} rows).")
        print(f"  To submit the AutoPilot job:")
        print(f"\n    python -c \"")
        print(f"    import boto3, json")
        print(f"    # Follow snippet in autopilot_config.json")
        print(f"    \"")
        print(f"\n  Or integrate into _ml_monitor.py to auto-submit.")
    else:
        pct_done = readiness["labeled_rows"] / readiness["min_labeled_required"] * 100
        print(f"\n  Progress toward launch: {pct_done:.1f}% of required labels")
        print(f"  Estimated readiness:    {readiness['projected_ready_date']}")

    return True


if __name__ == "__main__":
    ok = main()
    exit(0 if ok else 1)
