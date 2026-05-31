#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=================================================================
TRISHULA SOVEREIGN SCHEDULER WATCHDOG
=================================================================
Replaces Windows Task Scheduler entirely.
Runs as a persistent background process — no admin needed.
Fires Q-Matrix scans at exact market times every trading day.

Fire times (ET):
  09:30 — Market Open sweep
  12:00 — Midday sweep
  15:30 — Power Hour sweep
  18:00 — Monday only: Auto-Backtest (Q-Matrix accuracy)

Background threads (always running):
  - LevelMonitor  — polls spot every 60s, fires Discord break alerts
  - FridayRecap   — posts weekly accuracy recap every Friday 4:30 PM

Start at login: drop shortcut in shell:startup
=================================================================
"""
import time, subprocess, sys, os, datetime, threading
from pathlib import Path

BASE    = Path(r"H:\Trishula\Swarm_4_Integration\Salvo_Staging")
PYTHON  = sys.executable
SCRIPT  = str(BASE / "_run_full_stack.py")
LOG_DIR = BASE / "logs"
LOG_DIR.mkdir(exist_ok=True)

# (hour, minute, log_suffix)
FIRE_TIMES = [
    (9,  30, "open"),
    (12,  0, "midday"),
    (15, 30, "powerhour"),
]

def is_trading_day() -> bool:
    """Mon–Fri, not a US market holiday."""
    import holidays
    today = datetime.date.today()
    if today.weekday() >= 5:
        return False
    try:
        us_holidays = holidays.US(years=today.year)
        return today not in us_holidays
    except Exception:
        return today.weekday() < 5  # fallback

def already_fired(label: str, today_str: str) -> bool:
    """Check sentinel file so we don't double-fire."""
    sentinel = LOG_DIR / f".fired_{label}_{today_str}"
    return sentinel.exists()

def mark_fired(label: str, today_str: str):
    sentinel = LOG_DIR / f".fired_{label}_{today_str}"
    sentinel.touch()

def fire_scan(label: str):
    log_path = str(LOG_DIR / f"scanner_{label}.log")
    print(f"[WATCHDOG] Firing {label} scan → {log_path}")
    with open(log_path, "a", encoding="utf-8") as lf:
        lf.write(f"\n{'='*60}\n")
        lf.write(f"  WATCHDOG FIRE: {datetime.datetime.now()}\n")
        lf.write(f"{'='*60}\n")
        lf.flush()
        proc = subprocess.Popen(
            [PYTHON, SCRIPT],
            cwd=str(BASE),
            stdout=lf,
            stderr=lf,
            encoding="utf-8",
            errors="replace"
        )
        print(f"[WATCHDOG] PID {proc.pid} launched — running in background.")


# ──────────────────────────────────────────────────────────────
# LEVEL MONITOR — background thread
# ──────────────────────────────────────────────────────────────
_level_monitor_thread: threading.Thread | None = None

def _start_level_monitor():
    """Start the level-break alert monitor as a daemon thread."""
    global _level_monitor_thread
    try:
        sys.path.insert(0, str(BASE))
        from _level_monitor import start_level_monitor
        _level_monitor_thread = start_level_monitor()
        print(f"[WATCHDOG] Level Monitor thread started.")
    except Exception as e:
        print(f"[WATCHDOG] Level Monitor failed to start: {e}")


# ──────────────────────────────────────────────────────────────
# FRIDAY RECAP — fires once per Friday after 4:30 PM
# ──────────────────────────────────────────────────────────────
_recap_fired_today: str = ""

def _check_friday_recap(now: datetime.datetime, today_str: str):
    """Post Friday recap if it's time and not already fired today."""
    global _recap_fired_today
    if _recap_fired_today == today_str:
        return  # already fired today
    try:
        from _weekly_recap import is_friday_recap_time, post_friday_recap
        if is_friday_recap_time(now):
            print("[WATCHDOG] Friday 4:30 PM detected — posting weekly recap.")
            t = threading.Thread(target=post_friday_recap, name="FridayRecap", daemon=True)
            t.start()
            _recap_fired_today = today_str
    except Exception as e:
        print(f"[WATCHDOG] Friday recap error: {e}")


# ──────────────────────────────────────────────────────────────
# MONDAY BACKTEST — fires once per Monday at 18:00 ET
# ──────────────────────────────────────────────────────────────
_backtest_fired_today: str = ""

WEBHOOK_MACRO = "https://discord.com/api/webhooks/1508273976558882906/Scvp9yK6mmfrEJ7hMu38fJn24Fa7TljEeSs4tL0xHwfOIs_0P26mhrbaFuzwoxEgy5F5"

def _post_backtest_discord(report: dict):
    """Post Q-Matrix accuracy results as a Discord embed to #macro-pulse."""
    import requests
    acc    = report.get("accuracy", {})
    mp_acc = acc.get("max_pain", {})
    scored = report.get("scored", 0)
    pending = report.get("pending", 0)
    gen    = report.get("generated", "N/A")

    lines = [
        f"**Scored trades:** `{scored}`  |  **Pending:** `{pending}`",
        f"",
        f"**Max Pain Pin Rate:** `{mp_acc.get('pin', 0):.1f}%`",
        f"**Max Pain Hit Rate:** `{mp_acc.get('hit', 0):.1f}%`",
    ]

    gz  = acc.get("gex_zero", {})
    if isinstance(gz, dict):
        lines.append(f"**GEX Zero Pin Rate:** `{gz.get('pin', 0):.1f}%`")
    wp  = acc.get("whale_poc", {})
    if isinstance(wp, dict):
        lines.append(f"**Whale POC Pin Rate:** `{wp.get('pin', 0):.1f}%`")

    embed = {
        "title": "\U0001f4ca  Q-MATRIX — Weekly Accuracy Backtest",
        "description": "\n".join(lines),
        "color": 0x00ffbb,
        "fields": [
            {"name": "Generated",   "value": f"`{gen[:19]}`", "inline": True},
            {"name": "Source",      "value": "`_backtest_qmatrix_accuracy.py`", "inline": True},
        ],
        "footer": {"text": "Q-Matrix  ·  Trishula QuantNode  ·  Monday Auto-Backtest"},
    }
    try:
        resp = requests.post(WEBHOOK_MACRO, json={"embeds": [embed]}, timeout=20)
        if resp.status_code in (200, 204):
            print("[WATCHDOG] Backtest embed posted to Discord.")
        else:
            print(f"[WATCHDOG] Discord backtest post failed: {resp.status_code}")
    except Exception as e:
        print(f"[WATCHDOG] Discord backtest post error: {e}")


def _check_monday_backtest(now: datetime.datetime, today_str: str, dry_run: bool = False):
    """
    Fire _backtest_qmatrix_accuracy.py on Monday at 18:00 ET.
    After completion, read qmatrix_accuracy_report.json and post embed.
    Dry-run mode just prints instead of executing.
    """
    global _backtest_fired_today

    # Must be Monday (weekday == 0) and 18:00 exactly
    if now.weekday() != 0:
        return  # Not Monday
    if not (now.hour == 18 and now.minute == 0):
        return  # Not 18:00
    if _backtest_fired_today == today_str:
        return  # Already fired today

    _backtest_fired_today = today_str
    print(f"[WATCHDOG] Monday 18:00 ET — firing Q-Matrix accuracy backtest.")

    if dry_run:
        print("[WATCHDOG] [DRY-RUN] Would execute: python _backtest_qmatrix_accuracy.py")
        print("[WATCHDOG] [DRY-RUN] Would read: qmatrix_accuracy_report.json")
        print("[WATCHDOG] [DRY-RUN] Would post accuracy embed to Discord.")
        return

    # Run the backtest script
    backtest_script = str(BASE / "_backtest_qmatrix_accuracy.py")
    log_path        = str(LOG_DIR / "backtest_monday.log")
    print(f"[WATCHDOG] Running backtest → {log_path}")
    try:
        with open(log_path, "a", encoding="utf-8") as lf:
            lf.write(f"\n{'='*60}\n")
            lf.write(f"  MONDAY BACKTEST: {datetime.datetime.now()}\n")
            lf.write(f"{'='*60}\n")
            proc = subprocess.Popen(
                [PYTHON, backtest_script],
                cwd=str(BASE),
                stdout=lf,
                stderr=lf,
                encoding="utf-8",
                errors="replace",
            )
            print(f"[WATCHDOG] Backtest PID {proc.pid} running...")
            proc.wait(timeout=300)  # 5-minute timeout
            print(f"[WATCHDOG] Backtest completed (exit code {proc.returncode}).")
    except subprocess.TimeoutExpired:
        print("[WATCHDOG] Backtest timed out after 300s — posting with available data.")
    except Exception as e:
        print(f"[WATCHDOG] Backtest subprocess error: {e}")

    # Read and post the report
    report_path = BASE / "qmatrix_accuracy_report.json"
    try:
        import json
        if report_path.exists():
            with open(report_path, "r", encoding="utf-8") as f:
                report = json.load(f)
            _post_backtest_discord(report)
        else:
            print(f"[WATCHDOG] Report not found: {report_path}")
    except Exception as e:
        print(f"[WATCHDOG] Failed to read/post backtest report: {e}")




# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────
def main():
    print(f"[WATCHDOG] Trishula Sovereign Scheduler ARMED")
    print(f"[WATCHDOG] Python:  {PYTHON}")
    print(f"[WATCHDOG] Script:  {SCRIPT}")
    print(f"[WATCHDOG] Fires:   09:30 | 12:00 | 15:30 ET (Mon-Fri)")
    print(f"[WATCHDOG] Logs:    {LOG_DIR}")
    print(f"[WATCHDOG] Extras:  LevelMonitor + FridayRecap threads")
    print(f"[WATCHDOG] Running... Ctrl+C to stop.\n")

    # Launch background threads
    _start_level_monitor()

    fired_today = set()

    while True:
        now       = datetime.datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        h, m      = now.hour, now.minute

        # Reset fired set at midnight
        if h == 0 and m == 0:
            fired_today.clear()

        if is_trading_day():
            for fire_h, fire_m, label in FIRE_TIMES:
                key = f"{label}_{today_str}"
                if h == fire_h and m == fire_m and key not in fired_today:
                    fire_scan(label)
                    mark_fired(label, today_str)
                    fired_today.add(key)

        # Friday 4:30 PM recap check
        _check_friday_recap(now, today_str)

        # Monday 18:00 backtest check
        _check_monday_backtest(now, today_str)

        # Status heartbeat every 30 min
        if m in (0, 30) and now.second < 30:
            next_fires = []
            for fire_h, fire_m, label in FIRE_TIMES:
                fire_time = now.replace(hour=fire_h, minute=fire_m, second=0, microsecond=0)
                if fire_time > now:
                    next_fires.append(f"{label}@{fire_h:02d}:{fire_m:02d}")
            if next_fires:
                print(f"[WATCHDOG] {now.strftime('%H:%M')} — Next: {', '.join(next_fires)}")
            else:
                print(f"[WATCHDOG] {now.strftime('%H:%M')} — All scans complete for today.")

            # Monitor thread health check
            if _level_monitor_thread and not _level_monitor_thread.is_alive():
                print("[WATCHDOG] ⚠️  Level Monitor thread died — restarting.")
                _start_level_monitor()

        time.sleep(30)  # check every 30 seconds

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[WATCHDOG] Stopped.")
