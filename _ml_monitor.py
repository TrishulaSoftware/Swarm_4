#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=================================================================
R2-9 STEP 5 — ML MONITOR
=================================================================
Weekly ML pipeline progress monitor for the Trishula Q-Matrix ML
training pipeline.

Checks:
  1. S3 for latest dataset (rows, size, last modified)
  2. Local ml_features.csv for label coverage + readiness %
  3. SageMaker for active AutoPilot jobs
  4. Computes estimated readiness date
  5. Posts weekly progress update to Discord

Schedule: Run once per week (add to Task Scheduler or cron)
  Example: Every Monday 08:00
    python _ml_monitor.py

Run manually anytime: python _ml_monitor.py
=================================================================
"""

import os
import csv
import json
import math
import datetime
import requests
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────
BASE_DIR         = Path(r"H:\Trishula\Swarm_4_Integration\Salvo_Staging")
FEATURES_CSV     = BASE_DIR / "ml_features.csv"
RAW_CSV          = BASE_DIR / "ml_training_data.csv"
AUTOPILOT_CONFIG = BASE_DIR / "autopilot_config.json"
MONITOR_LOG      = BASE_DIR / "ml_monitor_log.json"

# ── S3 Config ────────────────────────────────────────────────────
S3_BUCKET    = "trishula-ml-data"
S3_PREFIX    = "qmatrix/v1/"
AWS_REGION   = "us-east-2"

# ── Discord Webhook (use mlb_team_props channel for system alerts)
# To add a dedicated #ml-monitor channel, add to config.py and update here
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1505723849830830122/G7nu04eqwEEWzLlHquyTK7Ew4Vle4Rl9FHv5ImeNOKWEPI2LH8iuld6OFEkmMyJflJyR"

# ── Thresholds ────────────────────────────────────────────────────
MIN_LABELED_ROWS = 500     # For AutoPilot launch
MIN_POS_LABELS   = 50
TARGET_COLUMN    = "price_within_1pct_maxpain"
SCANS_PER_DAY    = 18      # 3 scan runs × 6 tickers

# ── Color scheme for Discord embeds ──────────────────────────────
COLORS = {
    "green":  3066993,   # Ready / Good
    "yellow": 16776960,  # In progress / Warning
    "blue":   3447003,   # Info
    "red":    15158332,  # Error / Alert
    "gold":   16748258,  # Milestone
}


def _load_env():
    """Load AWS credentials from .env file."""
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
                return True
            except Exception:
                pass
    return False


# ══════════════════════════════════════════════════════════════════
# DATA CHECKS
# ══════════════════════════════════════════════════════════════════

def check_local_dataset() -> dict:
    """Check local CSV files for row counts and label coverage."""
    result = {
        "raw_csv_exists":      RAW_CSV.exists(),
        "features_csv_exists": FEATURES_CSV.exists(),
        "raw_rows":            0,
        "feature_rows":        0,
        "labeled_rows":        0,
        "unlabeled_rows":      0,
        "label_coverage_pct":  0.0,
        "positive_labels":     0,
        "negative_labels":     0,
        "distinct_tickers":    0,
        "date_from":           "N/A",
        "date_to":             "N/A",
        "rows_per_day":        SCANS_PER_DAY,
    }

    # ── Raw CSV ───────────────────────────────────────────────────
    if RAW_CSV.exists():
        with open(RAW_CSV, "r", encoding="utf-8", newline="") as f:
            result["raw_rows"] = sum(1 for _ in csv.DictReader(f))

    # ── Feature CSV ───────────────────────────────────────────────
    if FEATURES_CSV.exists():
        rows = []
        with open(FEATURES_CSV, "r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))

        result["feature_rows"] = len(rows)

        # Label coverage
        labeled = [r for r in rows if r.get(TARGET_COLUMN, "") not in ("", "None", None)]
        pos     = [r for r in labeled if str(r.get(TARGET_COLUMN, "")) == "1"]
        neg     = [r for r in labeled if str(r.get(TARGET_COLUMN, "")) == "0"]

        result["labeled_rows"]       = len(labeled)
        result["unlabeled_rows"]     = len(rows) - len(labeled)
        result["label_coverage_pct"] = round(len(labeled) / len(rows) * 100, 1) if rows else 0
        result["positive_labels"]    = len(pos)
        result["negative_labels"]    = len(neg)

        # Tickers and dates
        tickers = set(r.get("ticker", "") for r in rows if r.get("ticker"))
        dates   = sorted(set(r.get("scan_date", "") for r in rows if r.get("scan_date")))
        result["distinct_tickers"] = len(tickers)
        result["date_from"] = dates[0] if dates else "N/A"
        result["date_to"]   = dates[-1] if dates else "N/A"

        # Scan rate estimate
        if len(dates) >= 2:
            try:
                d0 = datetime.datetime.strptime(dates[0],  "%Y-%m-%d")
                d1 = datetime.datetime.strptime(dates[-1], "%Y-%m-%d")
                cal_days  = max(1, (d1 - d0).days)
                trd_days  = max(1, int(cal_days * 5 / 7))
                result["rows_per_day"] = round(len(rows) / trd_days, 1)
            except Exception:
                pass

    return result


def check_s3_dataset() -> dict:
    """Check S3 bucket for latest uploaded files."""
    result = {
        "s3_accessible":     False,
        "objects":           [],
        "total_size_kb":     0.0,
        "last_upload":       "N/A",
        "error":             None,
    }

    try:
        import boto3
        _load_env()

        aws_key    = os.environ.get("AWS_ACCESS_KEY_ID")
        aws_secret = os.environ.get("AWS_SECRET_ACCESS_KEY")

        session_kwargs = {"region_name": AWS_REGION}
        if aws_key and aws_secret:
            session_kwargs["aws_access_key_id"]     = aws_key
            session_kwargs["aws_secret_access_key"] = aws_secret

        s3 = boto3.client("s3", **session_kwargs)

        response = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=S3_PREFIX)
        objects  = response.get("Contents", [])

        result["s3_accessible"] = True
        result["objects"]       = [
            {
                "key":       obj["Key"],
                "size_kb":   round(obj["Size"] / 1024, 1),
                "modified":  obj["LastModified"].strftime("%Y-%m-%d %H:%M UTC"),
            }
            for obj in objects
        ]
        result["total_size_kb"] = round(sum(o["size_kb"] for o in result["objects"]), 1)

        if objects:
            latest = max(objects, key=lambda o: o["LastModified"])
            result["last_upload"] = latest["LastModified"].strftime("%Y-%m-%d %H:%M UTC")

    except ImportError:
        result["error"] = "boto3 not installed"
    except Exception as e:
        result["error"] = str(e)[:120]

    return result


def check_sagemaker_jobs() -> dict:
    """Check SageMaker for active or completed AutoPilot jobs."""
    result = {
        "sm_accessible": False,
        "active_jobs":   [],
        "recent_jobs":   [],
        "error":         None,
    }

    try:
        import boto3
        _load_env()

        aws_key    = os.environ.get("AWS_ACCESS_KEY_ID")
        aws_secret = os.environ.get("AWS_SECRET_ACCESS_KEY")

        session_kwargs = {"region_name": AWS_REGION}
        if aws_key and aws_secret:
            session_kwargs["aws_access_key_id"]     = aws_key
            session_kwargs["aws_secret_access_key"] = aws_secret

        sm = boto3.client("sagemaker", **session_kwargs)

        response = sm.list_auto_ml_jobs(
            SortBy="CreationTime",
            SortOrder="Descending",
            MaxResults=10,
        )

        result["sm_accessible"] = True
        jobs = response.get("AutoMLJobSummaries", [])

        # Filter for trishula jobs
        trishula_jobs = [j for j in jobs if "trishula" in j.get("AutoMLJobName", "").lower()]

        for job in trishula_jobs:
            job_info = {
                "name":    job["AutoMLJobName"],
                "status":  job["AutoMLJobStatus"],
                "created": job["CreationTime"].strftime("%Y-%m-%d"),
            }
            if job["AutoMLJobStatus"] in ("InProgress", "Stopping"):
                result["active_jobs"].append(job_info)
            else:
                result["recent_jobs"].append(job_info)

    except ImportError:
        result["error"] = "boto3 not installed"
    except Exception as e:
        result["error"] = str(e)[:120]

    return result


def compute_projections(local: dict) -> dict:
    """Compute readiness date and progress metrics."""
    total_rows    = local["feature_rows"] or local["raw_rows"]
    labeled_rows  = local["labeled_rows"]
    rows_per_day  = local["rows_per_day"]

    rows_needed   = max(0, MIN_LABELED_ROWS - labeled_rows)
    pct_done      = round(labeled_rows / MIN_LABELED_ROWS * 100, 1) if MIN_LABELED_ROWS > 0 else 0

    if rows_needed <= 0:
        days_needed = 0
        ready_date  = datetime.date.today().strftime("%Y-%m-%d")
    else:
        # Labels come in via backtest — but scanner adds rows daily
        # Estimate: after 500+ rows, backtest can be run to fill all labels
        rows_to_500_total = max(0, 500 - total_rows)
        days_to_500 = math.ceil(rows_to_500_total / max(rows_per_day, 1))
        # Convert trading days to calendar days
        days_needed = int(days_to_500 * 7 / 5)
        ready_date  = (datetime.date.today() +
                       datetime.timedelta(days=days_needed)).strftime("%Y-%m-%d")

    weeks_to_readiness = math.ceil(days_needed / 7)

    return {
        "total_rows":           total_rows,
        "labeled_rows":         labeled_rows,
        "rows_per_day":         rows_per_day,
        "rows_to_readiness":    rows_needed,
        "days_to_readiness":    days_needed,
        "weeks_to_readiness":   weeks_to_readiness,
        "projected_ready_date": ready_date,
        "pct_done":             pct_done,
        "is_ready":             labeled_rows >= MIN_LABELED_ROWS,
    }


# ══════════════════════════════════════════════════════════════════
# DISCORD REPORT
# ══════════════════════════════════════════════════════════════════

def build_discord_embed(local: dict, s3: dict, sm: dict, proj: dict) -> dict:
    """Build a rich Discord embed for the weekly ML progress report."""

    now_str  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    is_ready = proj["is_ready"]

    # Color: green if ready, yellow if making progress, blue otherwise
    if is_ready:
        color = COLORS["green"]
        title = "🚀 Q-Matrix ML Pipeline — READY TO LAUNCH"
    elif proj["pct_done"] >= 50:
        color = COLORS["yellow"]
        title = "📈 Q-Matrix ML Pipeline — Halfway There"
    else:
        color = COLORS["blue"]
        title = "🧠 Q-Matrix ML Pipeline — Weekly Progress"

    # Progress bar (20 chars)
    filled = int(proj["pct_done"] / 5)
    bar    = "█" * filled + "░" * (20 - filled)

    # S3 status
    if s3["s3_accessible"] and s3["objects"]:
        s3_status  = f"✅ {len(s3['objects'])} files ({s3['total_size_kb']} KB)"
        s3_updated = f"Last upload: {s3['last_upload']}"
    elif s3["s3_accessible"]:
        s3_status  = "⚠️ Bucket accessible but empty"
        s3_updated = "No uploads yet"
    else:
        s3_status  = f"❌ {s3.get('error', 'Not accessible')}"
        s3_updated = "—"

    # SageMaker status
    if sm["active_jobs"]:
        sm_text = f"🔄 {len(sm['active_jobs'])} job(s) running"
        for j in sm["active_jobs"][:2]:
            sm_text += f"\n  `{j['name']}` → **{j['status']}**"
    elif sm["recent_jobs"]:
        latest = sm["recent_jobs"][0]
        sm_text = f"✅ Last job: `{latest['name']}`\n  Status: **{latest['status']}**"
    elif not sm["sm_accessible"]:
        sm_text = f"❌ {sm.get('error', 'Not accessible')}"
    else:
        sm_text = "No AutoPilot jobs yet — awaiting label readiness"

    fields = [
        {
            "name":   "📊 Dataset Stats",
            "value":  (
                f"**Total rows:** {local['feature_rows'] or local['raw_rows']:,}\n"
                f"**Labeled:**    {local['labeled_rows']:,} ({local['label_coverage_pct']}%)\n"
                f"**Unlabeled:**  {local['unlabeled_rows']:,}\n"
                f"**Tickers:**    {local['distinct_tickers']:,}  |  "
                f"**Dates:** {local['date_from']} → {local['date_to']}"
            ),
            "inline": False,
        },
        {
            "name":   "🎯 AutoPilot Readiness",
            "value":  (
                f"`{bar}` {proj['pct_done']:.1f}%\n"
                f"**Have:** {local['labeled_rows']:,} / **Need:** {MIN_LABELED_ROWS:,} labeled rows\n"
                f"**Rate:** ~{proj['rows_per_day']:.0f} rows/day\n"
                f"**ETA:**  {proj['projected_ready_date']}  ({proj['weeks_to_readiness']}w)"
            ),
            "inline": False,
        },
        {
            "name":   "☁️ S3 Storage",
            "value":  f"{s3_status}\n{s3_updated}",
            "inline": True,
        },
        {
            "name":   "🤖 SageMaker",
            "value":  sm_text,
            "inline": True,
        },
    ]

    # Add launch checklist if near readiness
    if proj["pct_done"] >= 80 or is_ready:
        checklist = []
        checklist.append(f"{'✅' if local['feature_rows'] >= 100 else '⏳'} 100+ rows collected")
        checklist.append(f"{'✅' if s3['s3_accessible'] else '⏳'} S3 bucket live")
        checklist.append(f"{'✅' if local['labeled_rows'] >= MIN_LABELED_ROWS else '⏳'} "
                         f"{MIN_LABELED_ROWS}+ labeled rows")
        checklist.append(f"{'✅' if local['positive_labels'] >= MIN_POS_LABELS else '⏳'} "
                         f"{MIN_POS_LABELS}+ positive class samples")
        checklist.append(f"{'✅' if is_ready else '⏳'} AutoPilot launch")
        fields.append({
            "name":   "🏁 Launch Checklist",
            "value":  "\n".join(checklist),
            "inline": False,
        })

    embed = {
        "title":       title,
        "description": f"Trishula Q-Matrix → SageMaker AutoPilot pipeline status",
        "color":       color,
        "fields":      fields,
        "footer":      {
            "text": f"Trishula ML Monitor  |  {now_str}  |  Target: price_within_1pct_maxpain"
        },
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }

    return embed


def post_to_discord(embed: dict, webhook: str = DISCORD_WEBHOOK) -> bool:
    """Post the embed to Discord."""
    payload = {
        "username":   "Trishula ML Monitor",
        "avatar_url": "https://i.imgur.com/xO4b2nJ.png",
        "embeds":     [embed],
    }
    try:
        r = requests.post(webhook, json=payload, timeout=15)
        if r.status_code == 204:
            print("[DISCORD] ✓ Progress report posted")
            return True
        else:
            print(f"[DISCORD] ✗ HTTP {r.status_code}: {r.text[:200]}")
            return False
    except Exception as e:
        print(f"[DISCORD] ✗ Error: {e}")
        return False


# ══════════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════════

def save_monitor_log(local: dict, s3: dict, sm: dict, proj: dict):
    """Append a run record to ml_monitor_log.json."""
    entry = {
        "ts":    datetime.datetime.now().isoformat(),
        "local": local,
        "s3":    s3,
        "sm":    sm,
        "proj":  proj,
    }

    log = []
    if MONITOR_LOG.exists():
        try:
            with open(MONITOR_LOG, "r", encoding="utf-8") as f:
                log = json.load(f)
        except Exception:
            log = []

    log.append(entry)
    # Keep last 52 entries (1 year of weekly runs)
    log = log[-52:]

    with open(MONITOR_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, default=str)

    print(f"[LOG] Monitor log saved → {MONITOR_LOG} ({len(log)} entries)")


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════

def print_console_report(local: dict, s3: dict, sm: dict, proj: dict):
    """Print a console-formatted status report."""
    print(f"\n{'='*65}")
    print("  TRISHULA ML MONITOR — WEEKLY STATUS")
    print(f"  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*65}")

    # Dataset
    print(f"\n  📊 LOCAL DATASET")
    print(f"    Raw snapshots:      {local['raw_rows']:,}")
    print(f"    Feature rows:       {local['feature_rows']:,}")
    print(f"    Labeled:            {local['labeled_rows']:,} ({local['label_coverage_pct']}%)")
    print(f"    Unlabeled:          {local['unlabeled_rows']:,}")
    print(f"    Pos/Neg labels:     +{local['positive_labels']} / -{local['negative_labels']}")
    print(f"    Tickers:            {local['distinct_tickers']}")
    print(f"    Date range:         {local['date_from']} → {local['date_to']}")
    print(f"    Scan rate:          ~{local['rows_per_day']:.0f} rows/day")

    # S3
    print(f"\n  ☁️  S3 STORAGE  (s3://{S3_BUCKET}/{S3_PREFIX})")
    if s3["s3_accessible"]:
        print(f"    Files:              {len(s3['objects'])}")
        print(f"    Total size:         {s3['total_size_kb']} KB")
        print(f"    Last upload:        {s3['last_upload']}")
        for obj in s3["objects"]:
            print(f"    • {obj['key'].split('/')[-1]:<30} {obj['size_kb']:>8.1f} KB")
    else:
        print(f"    ✗ {s3.get('error', 'Not accessible')}")

    # SageMaker
    print(f"\n  🤖 SAGEMAKER")
    if sm["active_jobs"]:
        for j in sm["active_jobs"]:
            print(f"    ACTIVE: {j['name']}  → {j['status']}")
    elif sm["recent_jobs"]:
        j = sm["recent_jobs"][0]
        print(f"    LAST JOB: {j['name']}  → {j['status']}  ({j['created']})")
    else:
        print(f"    No AutoPilot jobs yet")
    if sm.get("error"):
        print(f"    Error: {sm['error']}")

    # Projection
    filled = int(proj["pct_done"] / 5)
    bar    = "█" * filled + "░" * (20 - filled)
    print(f"\n  🎯 AUTOPILOT READINESS")
    print(f"    [{bar}] {proj['pct_done']:.1f}%")
    print(f"    Have:    {local['labeled_rows']:,} labeled  |  Need: {MIN_LABELED_ROWS:,}")
    print(f"    Rate:    ~{proj['rows_per_day']:.0f} rows/day")
    print(f"    ETA:     {proj['projected_ready_date']} ({proj['weeks_to_readiness']} weeks)")

    status = "✅ READY TO LAUNCH!" if proj["is_ready"] else "⏳ Accumulating..."
    print(f"    Status:  {status}")
    print(f"\n{'='*65}\n")


def main(post_discord: bool = True):
    print(f"\n{'='*60}")
    print("  R2-9 STEP 5: ML MONITOR")
    print(f"  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    # ── Check local datasets ──────────────────────────────────────
    print("[CHECK] Local dataset...")
    local = check_local_dataset()

    # ── Check S3 ──────────────────────────────────────────────────
    print("[CHECK] S3 bucket...")
    s3 = check_s3_dataset()

    # ── Check SageMaker ───────────────────────────────────────────
    print("[CHECK] SageMaker jobs...")
    sm = check_sagemaker_jobs()

    # ── Compute projections ───────────────────────────────────────
    proj = compute_projections(local)

    # ── Print console report ──────────────────────────────────────
    print_console_report(local, s3, sm, proj)

    # ── Post to Discord ───────────────────────────────────────────
    if post_discord:
        print("[DISCORD] Building embed...")
        embed = build_discord_embed(local, s3, sm, proj)
        post_to_discord(embed)
    else:
        print("[DISCORD] Skipped (post_discord=False)")

    # ── Save log ──────────────────────────────────────────────────
    save_monitor_log(local, s3, sm, proj)

    return {
        "local": local,
        "s3":    s3,
        "sm":    sm,
        "proj":  proj,
    }


if __name__ == "__main__":
    import sys
    # Allow --no-discord flag for testing
    post_disc = "--no-discord" not in sys.argv
    result = main(post_discord=post_disc)
    exit(0)
