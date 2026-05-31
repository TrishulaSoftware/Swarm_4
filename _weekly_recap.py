#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=================================================================
WEEKLY FRIDAY RECAP ENGINE
=================================================================
Fires every Friday at 4:30 PM ET via the watchdog.

Posts a recap embed to #macro-pulse showing:
  • Top 5 most accurate predictions this week
  • Overall accuracy rate across all tickers
  • Best/worst performers

Accuracy definition: 
  - A snapshot is "accurate" if spot moved toward Max Pain 
    (i.e., |final_spot - max_pain| < |initial_spot - max_pain|)
  - Uses Friday close vs Monday open spot levels from DB1

=================================================================
"""
import datetime
import requests

# ── ORDS Config ──────────────────────────────────────────────
_ORDS_BASE = "https://g275356d1414552-trishulapicks.adb.us-ashburn-1.oraclecloudapps.com/ords/admin"
_ORDS_AUTH = ("ADMIN", "C1iffyHu5tl3!!!")
_TABLE     = "qmatrix_snapshots"

# ── Discord webhook — macro pulse ─────────────────────────────
WEBHOOK_MACRO = "https://discord.com/api/webhooks/1508273976558882906/Scvp9yK6mmfrEJ7hMu38fJn24Fa7TljEeSs4tL0xHwfOIs_0P26mhrbaFuzwoxEgy5F5"

# Colors
GREEN = 0x3fb950
RED   = 0xf85149
GOLD  = 0xf0c040


def _get_week_snapshots() -> list[dict]:
    """
    Fetch all snapshots from the current trading week (Mon–Fri).
    Returns list of snapshot dicts, newest first.
    """
    today    = datetime.date.today()
    # Monday of this week
    monday   = today - datetime.timedelta(days=today.weekday())
    date_from = monday.strftime("%Y-%m-%d")
    date_to   = today.strftime("%Y-%m-%d")

    try:
        url    = f"{_ORDS_BASE}/{_TABLE}/"
        # ORDS filter: fetch recent records and filter in Python
        params = {
            "limit": 500,
        }
        r = requests.get(url, auth=_ORDS_AUTH, params=params, timeout=15)
        if r.status_code != 200:
            print(f"[RECAP] ORDS fetch error {r.status_code}: {r.text[:120]}")
            return []
        items = r.json().get("items", [])
        # Filter to this week in Python
        filtered = []
        for item in items:
            sd = item.get("scan_date") or item.get("SCAN_DATE", "")
            if date_from <= sd <= date_to:
                filtered.append(item)
        return filtered
    except Exception as e:
        print(f"[RECAP] fetch error: {e}")
        return []


def _normalize(item: dict) -> dict:
    """Normalize Oracle ORDS response keys (may be uppercase)."""
    def g(d, *keys):
        for k in keys:
            v = d.get(k) or d.get(k.upper()) or d.get(k.lower())
            if v is not None:
                return v
        return None

    return {
        "ticker":        g(item, "ticker"),
        "scan_date":     g(item, "scan_date"),
        "scan_time":     g(item, "scan_time"),
        "spot":          float(g(item, "spot") or 0),
        "max_pain":      float(g(item, "max_pain") or 0),
        "net_gex_m":     float(g(item, "net_gex_m") or 0),
        "gex_zero":      g(item, "gex_zero"),
        "whale_bull_pct":float(g(item, "whale_bull_pct") or 0),
        "pc_ratio":      float(g(item, "pc_ratio") or 0),
    }


def _evaluate_accuracy(snapshots: list[dict]) -> list[dict]:
    """
    For each ticker, pair the first (earliest) and last (latest) snapshot of the week.
    Determine if price moved toward Max Pain (GEX gravity accuracy).

    Returns list of dicts:
      ticker, first_spot, last_spot, max_pain, moved_toward, pct_delta, net_gex_m
    """
    from collections import defaultdict

    by_ticker: dict[str, list[dict]] = defaultdict(list)
    for snap in snapshots:
        n = _normalize(snap)
        if n["ticker"]:
            by_ticker[n["ticker"]].append(n)

    results = []
    for ticker, snaps in by_ticker.items():
        if len(snaps) < 2:
            continue
        snaps.sort(key=lambda x: (x["scan_date"], x["scan_time"]))
        first = snaps[0]
        last  = snaps[-1]

        if first["max_pain"] == 0 or first["spot"] == 0:
            continue

        dist_init  = abs(first["spot"] - first["max_pain"])
        dist_final = abs(last["spot"]  - first["max_pain"])
        moved_toward = dist_final < dist_init

        # Net spot move %
        pct_delta = (last["spot"] - first["spot"]) / first["spot"] * 100 if first["spot"] else 0

        results.append({
            "ticker":        ticker,
            "first_spot":    first["spot"],
            "last_spot":     last["spot"],
            "max_pain":      first["max_pain"],
            "moved_toward":  moved_toward,
            "pct_delta":     pct_delta,
            "dist_init":     dist_init,
            "dist_final":    dist_final,
            "accuracy_score": (dist_init - dist_final) / dist_init * 100 if dist_init else 0,
            "net_gex_m":     last["net_gex_m"],
            "num_scans":     len(snaps),
        })

    return results


def build_recap_embed() -> dict | None:
    """
    Build and return the Friday recap Discord embed dict.
    Returns None if insufficient data.
    """
    snapshots = _get_week_snapshots()
    if not snapshots:
        return None

    results = _evaluate_accuracy(snapshots)
    if not results:
        return None

    total     = len(results)
    accurate  = [r for r in results if r["moved_toward"]]
    inaccurate = [r for r in results if not r["moved_toward"]]
    acc_rate  = len(accurate) / total * 100 if total else 0

    # Sort by accuracy score (how far price converged toward max pain)
    accurate.sort(key=lambda x: x["accuracy_score"], reverse=True)
    inaccurate.sort(key=lambda x: x["accuracy_score"])  # worst first

    top5   = accurate[:5]
    best   = accurate[0]   if accurate   else None
    worst  = inaccurate[0] if inaccurate else results[-1]

    today_str = datetime.date.today().strftime("%B %d, %Y")

    # ── Build embed ──────────────────────────────────────────
    fields = []

    # Overall accuracy
    fields.append({
        "name":   "📊 Weekly Accuracy Rate",
        "value":  (
            f"`{acc_rate:.1f}%` convergence to Max Pain  |  "
            f"`{len(accurate)}/{total}` tickers accurate  |  "
            f"`{len(snapshots)}` total scans this week"
        ),
        "inline": False,
    })

    # Top 5 most accurate
    if top5:
        top5_lines = []
        for i, r in enumerate(top5, 1):
            sign  = "+" if r["pct_delta"] >= 0 else ""
            medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i - 1]
            top5_lines.append(
                f"{medal} **{r['ticker']}** — converged `{r['accuracy_score']:.1f}%` toward "
                f"Max Pain `${r['max_pain']:.0f}`  |  move: `{sign}{r['pct_delta']:.2f}%`"
            )
        fields.append({
            "name":   "🏆 Top 5 Most Accurate Predictions",
            "value":  "\n".join(top5_lines),
            "inline": False,
        })

    # Best performer
    if best:
        fields.append({
            "name":   "🌟 Best Performer",
            "value":  (
                f"**{best['ticker']}** — Max Pain convergence `{best['accuracy_score']:.1f}%`  |  "
                f"Spot: `${best['first_spot']:.2f}` → `${best['last_spot']:.2f}`  |  "
                f"Max Pain: `${best['max_pain']:.0f}`"
            ),
            "inline": True,
        })

    # Worst performer
    if worst:
        sign = "+" if worst["pct_delta"] >= 0 else ""
        fields.append({
            "name":   "📉 Weakest Prediction",
            "value":  (
                f"**{worst['ticker']}** — diverged `{abs(worst['accuracy_score']):.1f}%` from Max Pain  |  "
                f"move: `{sign}{worst['pct_delta']:.2f}%`"
            ),
            "inline": True,
        })

    # Tickers with no data this week
    if len(results) < 8:
        fields.append({
            "name":   "ℹ️ Coverage Note",
            "value":  f"Recap based on `{total}` tickers with paired scan data this week.",
            "inline": False,
        })

    embed = {
        "title":       f"📅 Q-MATRIX  —  Friday Recap  |  Week of {today_str}",
        "description": (
            "Weekly performance review of Trishula Q-Matrix sovereign predictions.\n"
            "**Accuracy = spot converging toward Max Pain strike by Friday close.**"
        ),
        "color":       GOLD if acc_rate >= 60 else GREEN if acc_rate >= 40 else RED,
        "fields":      fields,
        "footer":      {"text": "Q-Matrix  ·  Trishula QuantNode  ·  Friday Recap"},
        "timestamp":   datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    return embed


def post_friday_recap():
    """Build and post the Friday recap to Discord."""
    print("[RECAP] Building Friday recap embed...")
    embed = build_recap_embed()
    if embed is None:
        print("[RECAP] No data available for recap. Posting placeholder.")
        embed = {
            "title":       f"📅 Q-MATRIX  —  Friday Recap  |  {datetime.date.today().strftime('%B %d, %Y')}",
            "description": "⚠️ Insufficient scan data this week to generate accuracy metrics.\nEnsure the scanner has run at least twice per ticker this week.",
            "color":       RED,
            "footer":      {"text": "Q-Matrix  ·  Trishula QuantNode  ·  Friday Recap"},
        }

    try:
        r = requests.post(WEBHOOK_MACRO, json={"embeds": [embed]}, timeout=15)
        if r.status_code in (200, 204):
            print("[RECAP] ✓ Friday recap posted to #macro-pulse.")
        else:
            print(f"[RECAP] Discord error {r.status_code}: {r.text[:120]}")
    except Exception as e:
        print(f"[RECAP] Post error: {e}")


def is_friday_recap_time(now: datetime.datetime = None) -> bool:
    """Return True if it is Friday between 16:28 and 16:35 ET."""
    now = now or datetime.datetime.now()
    if now.weekday() != 4:       # 4 = Friday
        return False
    return now.hour == 16 and 28 <= now.minute <= 35


# ── Standalone test ──────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Trishula Weekly Recap")
    parser.add_argument("--force", action="store_true", help="Post recap now regardless of day/time")
    args = parser.parse_args()

    if args.force or is_friday_recap_time():
        post_friday_recap()
    else:
        now = datetime.datetime.now()
        print(f"[RECAP] Not Friday 4:30 PM (now: {now.strftime('%A %H:%M')}). Use --force to post anyway.")
