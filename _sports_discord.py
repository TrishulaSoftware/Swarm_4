#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=================================================================
TRISHULA SPORTS DISCORD MODULE
=================================================================
Posts sports picks and record summaries to Discord.

Functions:
  post_pick(pick_dict)         — single pick embed
  post_picks_batch(picks_list) — up to 5 picks in table embed
  post_daily_record()          — today's W/L record
  post_weekly_recap()          — weekly W/L/P/ROI summary

Webhook: uses config.py WEBHOOKS['mlb_pick_ledger'] as sports channel
         (override with SPORTS_WEBHOOK env var or pass webhook= kwarg)
=================================================================
"""
import os, requests, time, datetime
from config import WEBHOOKS, SWARM_IDENTITY

# ── Webhook ──────────────────────────────────────────────────
# Falls back to mlb_pick_ledger if no dedicated sports webhook exists
_SPORTS_WEBHOOK = os.environ.get(
    "SPORTS_WEBHOOK",
    WEBHOOKS.get("sports_picks", WEBHOOKS.get("mlb_pick_ledger"))
)

# ── Colors (decimal) ─────────────────────────────────────────
COLOR_HIGH   = 0x2ECC71   # Green  — HIGH confidence
COLOR_MEDIUM = 0xF0C040   # Gold   — MEDIUM confidence
COLOR_LOW    = 0x808080   # Gray   — LOW confidence
COLOR_LOCK   = 0xFFD700   # Bright gold — LOCK
COLOR_WIN    = 0x3FB950   # Green  — WIN
COLOR_LOSS   = 0xFF7B72   # Red    — LOSS
COLOR_PUSH   = 0x808080   # Gray   — PUSH
COLOR_INFO   = 0x58A6FF   # Blue   — info / recap

# Sport emoji map
SPORT_EMOJI = {
    "NFL":   "🏈",
    "NBA":   "🏀",
    "MLB":   "⚾",
    "NHL":   "🏒",
    "NCAAF": "🏈",
    "NCAAB": "🏀",
    "SOCCER":"⚽",
    "MMA":   "🥊",
}

FOOTER_TEXT = "Trishula Sports Intelligence"


# ── Helpers ──────────────────────────────────────────────────

def _color_for_confidence(confidence: str) -> int:
    c = str(confidence).upper()
    if c == "LOCK":
        return COLOR_LOCK
    if c == "HIGH":
        return COLOR_HIGH
    if c == "MEDIUM":
        return COLOR_MEDIUM
    return COLOR_LOW


def _odds_str(odds) -> str:
    try:
        v = int(float(odds))
        return f"+{v}" if v > 0 else str(v)
    except (TypeError, ValueError):
        return str(odds) if odds is not None else "N/A"


def _conf_badge(confidence: str) -> str:
    c = str(confidence).upper()
    badges = {
        "LOCK":   "🔒 LOCK",
        "HIGH":   "🟢 HIGH",
        "MEDIUM": "🟡 MEDIUM",
        "LOW":    "⚪ LOW",
    }
    return badges.get(c, c)


def _post(webhook: str, payload: dict) -> bool:
    try:
        r = requests.post(webhook, json=payload, timeout=15)
        if r.status_code == 204:
            return True
        print(f"  [SPORTS DISCORD] HTTP {r.status_code}: {r.text[:120]}")
        return False
    except Exception as e:
        print(f"  [SPORTS DISCORD] post error: {e}")
        return False


# ── Public Functions ─────────────────────────────────────────

def post_pick(pick_dict: dict, webhook: str = None) -> bool:
    """
    Post a single sports pick as a Discord embed.

    pick_dict keys:
        sport, game, pick_side, pick_type, odds, confidence, units
        line_value (optional), notes (optional), pick_date (optional)

    Color scheme:
        LOCK   → bright gold
        HIGH   → green
        MEDIUM → gold
        LOW    → gray
    """
    wh = webhook or _SPORTS_WEBHOOK

    sport      = str(pick_dict.get("sport", "")).upper()
    game       = str(pick_dict.get("game", "TBD"))
    pick_side  = str(pick_dict.get("pick_side", ""))
    pick_type  = str(pick_dict.get("pick_type", "")).upper()
    odds       = pick_dict.get("odds")
    confidence = str(pick_dict.get("confidence", "MEDIUM")).upper()
    units      = pick_dict.get("units", 1.0)
    line_value = pick_dict.get("line_value")
    notes      = pick_dict.get("notes", "")
    pick_date  = pick_dict.get("pick_date") or datetime.date.today().strftime("%Y-%m-%d")
    sport_emoji = SPORT_EMOJI.get(sport, "🎯")

    color = _color_for_confidence(confidence)

    # Build line display
    line_display = ""
    if line_value is not None:
        try:
            lv = float(line_value)
            line_display = f"+{lv}" if lv > 0 else str(lv)
        except (ValueError, TypeError):
            line_display = str(line_value)

    title = f"{sport_emoji} **{sport}** — {game}"
    if confidence == "LOCK":
        title = f"🔒 {title}"

    fields = [
        {"name": "🏆 Pick", "value": f"`{pick_side}`", "inline": True},
        {"name": "📋 Type", "value": f"`{pick_type}`", "inline": True},
        {"name": "💰 Odds", "value": f"`{_odds_str(odds)}`", "inline": True},
    ]

    if line_display:
        fields.append({"name": "📊 Line", "value": f"`{line_display}`", "inline": True})

    fields += [
        {"name": "🎲 Units", "value": f"`{units}u`", "inline": True},
        {"name": "🔥 Confidence", "value": _conf_badge(confidence), "inline": True},
    ]

    if notes:
        fields.append({"name": "📝 Notes", "value": notes[:512], "inline": False})

    embed = {
        "title":       title,
        "color":       color,
        "fields":      fields,
        "footer":      {"text": f"{FOOTER_TEXT} | {pick_date}"},
        "timestamp":   datetime.datetime.utcnow().isoformat() + "Z",
    }

    payload = {**SWARM_IDENTITY, "embeds": [embed]}
    ok = _post(wh, payload)
    if ok:
        print(f"  [SPORTS DISCORD] Pick posted: {sport} | {game} | {pick_side}")
    return ok


def post_picks_batch(picks_list: list, webhook: str = None) -> bool:
    """
    Post up to 5 picks in a single embed with table-style layout.
    Batches of 5 are separated into multiple messages if > 5.
    """
    wh = webhook or _SPORTS_WEBHOOK
    today = datetime.date.today().strftime("%Y-%m-%d")

    # Chunk into groups of 5
    chunks = [picks_list[i:i+5] for i in range(0, len(picks_list), 5)]
    all_ok = True

    for chunk_idx, chunk in enumerate(chunks):
        lines = []
        for p in chunk:
            sport      = str(p.get("sport", "")).upper()
            game       = p.get("game", "TBD")
            side       = p.get("pick_side", "")
            ptype      = str(p.get("pick_type", "")).upper()
            odds       = _odds_str(p.get("odds"))
            conf       = str(p.get("confidence", "MEDIUM")).upper()
            units      = p.get("units", 1.0)
            emoji      = SPORT_EMOJI.get(sport, "🎯")
            conf_icon  = {"LOCK": "🔒", "HIGH": "🟢", "MEDIUM": "🟡", "LOW": "⚪"}.get(conf, "")
            lines.append(
                f"{emoji} **{sport}** | {game}\n"
                f"  → `{side}` ({ptype}) `{odds}` · **{units}u** {conf_icon}"
            )

        body = "\n\n".join(lines)

        # Overall confidence = highest in batch
        conf_order = {"LOCK": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        top_conf = max(
            (str(p.get("confidence", "MEDIUM")).upper() for p in chunk),
            key=lambda c: conf_order.get(c, 0),
        )
        color = _color_for_confidence(top_conf)

        total_units = sum(float(p.get("units") or 1.0) for p in chunk)
        header = f"**{len(chunk)} Pick{'s' if len(chunk)>1 else ''}** · {total_units}u total"
        if len(chunks) > 1:
            header += f" (Batch {chunk_idx+1}/{len(chunks)})"

        embed = {
            "title":     f"🎯 Trishula Sports — Pick Slate",
            "color":     color,
            "description": f"{header}\n\n{body}",
            "footer":    {"text": f"{FOOTER_TEXT} | {today}"},
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        }

        payload = {**SWARM_IDENTITY, "embeds": [embed]}
        ok = _post(wh, payload)
        if not ok:
            all_ok = False
        time.sleep(1)

    return all_ok


def post_daily_record(sport: str = None, webhook: str = None) -> bool:
    """
    Post today's win/loss record to Discord.
    Pulls live from DB1 and formats a summary embed.
    """
    from _sports_ingestion import get_picks, get_record_summary
    wh = webhook or _SPORTS_WEBHOOK
    today = datetime.date.today().strftime("%Y-%m-%d")

    summary = get_record_summary(sport=sport)
    wins    = summary["wins"]
    losses  = summary["losses"]
    pushes  = summary["pushes"]
    pending = summary["pending"]
    win_pct = summary["win_pct"]
    roi     = summary["roi_pct"]
    units_p = summary["units_profit"]
    sport_label = summary["sport"]

    # Color by record
    if wins > losses:
        color = COLOR_WIN
        record_emoji = "🟢"
    elif losses > wins:
        color = COLOR_LOSS
        record_emoji = "🔴"
    else:
        color = COLOR_PUSH
        record_emoji = "⚪"

    fields = [
        {"name": "✅ Wins",     "value": str(wins),              "inline": True},
        {"name": "❌ Losses",   "value": str(losses),            "inline": True},
        {"name": "🔁 Pushes",   "value": str(pushes),            "inline": True},
        {"name": "⏳ Pending",  "value": str(pending),           "inline": True},
        {"name": "🎯 Win %",    "value": f"{win_pct}%",          "inline": True},
        {"name": "📈 ROI",      "value": f"{roi:+.1f}%",         "inline": True},
        {"name": "💵 Units P&L","value": f"{units_p:+.2f}u",     "inline": True},
    ]

    embed = {
        "title":     f"{record_emoji} Daily Record — {sport_label} | {today}",
        "color":     color,
        "fields":    fields,
        "footer":    {"text": FOOTER_TEXT},
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }

    payload = {**SWARM_IDENTITY, "embeds": [embed]}
    ok = _post(wh, payload)
    if ok:
        print(f"  [SPORTS DISCORD] Daily record posted: {wins}W-{losses}L-{pushes}P")
    return ok


def post_weekly_recap(sport: str = None, webhook: str = None) -> bool:
    """
    Post weekly W/L/P/ROI recap. Includes best and worst pick.
    """
    from _sports_ingestion import get_picks, get_record_summary
    wh = webhook or _SPORTS_WEBHOOK

    # Get last 7 days of picks
    today  = datetime.date.today()
    week_start = (today - datetime.timedelta(days=6)).strftime("%Y-%m-%d")

    summary = get_record_summary(sport=sport)
    picks   = get_picks(sport=sport, limit=500)

    # Filter to last 7 days
    recent = [
        p for p in picks
        if p.get("pick_date", "") >= week_start
    ]

    wins    = sum(1 for p in recent if p.get("result") == "WIN")
    losses  = sum(1 for p in recent if p.get("result") == "LOSS")
    pushes  = sum(1 for p in recent if p.get("result") == "PUSH")
    settled = wins + losses + pushes
    win_pct = round(wins / settled * 100, 1) if settled > 0 else 0.0

    units_profit = sum(
        float(p.get("profit_loss") or 0) for p in recent
        if p.get("profit_loss") is not None
    )
    units_wagered = sum(
        float(p.get("units") or 0) for p in recent
        if p.get("result") != "PENDING"
    )
    roi = round(units_profit / units_wagered * 100, 1) if units_wagered > 0 else 0.0

    # Best pick (highest profit_loss)
    settled_picks = [p for p in recent if p.get("profit_loss") is not None]
    best_pick  = max(settled_picks, key=lambda p: float(p.get("profit_loss") or -999), default=None)
    worst_pick = min(settled_picks, key=lambda p: float(p.get("profit_loss") or 999), default=None)

    def _pick_line(p) -> str:
        if not p:
            return "N/A"
        pl = float(p.get("profit_loss") or 0)
        return (
            f"{p.get('sport')} | {p.get('game')} | "
            f"{p.get('pick_side')} → {p.get('result')} ({pl:+.2f}u)"
        )

    sport_label = sport.upper() if sport else "ALL SPORTS"
    color = COLOR_WIN if units_profit >= 0 else COLOR_LOSS

    week_label = f"{week_start} → {today.strftime('%Y-%m-%d')}"

    fields = [
        {"name": "📅 Period",    "value": week_label,               "inline": False},
        {"name": "✅ Wins",      "value": str(wins),                "inline": True},
        {"name": "❌ Losses",    "value": str(losses),              "inline": True},
        {"name": "🔁 Pushes",    "value": str(pushes),              "inline": True},
        {"name": "🎯 Win %",     "value": f"{win_pct}%",            "inline": True},
        {"name": "📈 ROI",       "value": f"{roi:+.1f}%",           "inline": True},
        {"name": "💵 Units P&L", "value": f"{units_profit:+.2f}u",  "inline": True},
        {"name": "🏆 Best Pick", "value": _pick_line(best_pick),    "inline": False},
        {"name": "💀 Worst Pick","value": _pick_line(worst_pick),   "inline": False},
    ]

    embed = {
        "title":     f"📊 Weekly Recap — {sport_label}",
        "color":     color,
        "fields":    fields,
        "footer":    {"text": FOOTER_TEXT},
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
    }

    payload = {**SWARM_IDENTITY, "embeds": [embed]}
    ok = _post(wh, payload)
    if ok:
        print(f"  [SPORTS DISCORD] Weekly recap posted: {wins}W-{losses}L-{pushes}P | ROI {roi:+.1f}%")
    return ok


# ── Self-test ────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  SPORTS DISCORD — Self Test")
    print("=" * 50)

    test_pick = {
        "sport":      "NBA",
        "game":       "LAL vs GSW",
        "pick_side":  "LAL",
        "pick_type":  "SPREAD",
        "line_value": -5.5,
        "odds":       -110,
        "confidence": "HIGH",
        "units":      2.0,
        "notes":      "Test embed from self-test",
    }

    print("\n[1] post_pick...")
    ok = post_pick(test_pick)
    print(f"    ok={ok}")

    time.sleep(2)

    print("\n[2] post_picks_batch (3 picks)...")
    batch = [
        {"sport":"NFL","game":"KC vs BUF","pick_side":"KC","pick_type":"ML","odds":-120,"confidence":"HIGH","units":2.0},
        {"sport":"NHL","game":"TOR vs MTL","pick_side":"TOR","pick_type":"ML","odds":-150,"confidence":"LOCK","units":3.0},
        {"sport":"NBA","game":"BOS vs MIA","pick_side":"OVER","pick_type":"TOTAL","line_value":215.5,"odds":-110,"confidence":"MEDIUM","units":1.5},
    ]
    ok = post_picks_batch(batch)
    print(f"    ok={ok}")

    time.sleep(2)

    print("\n[3] post_daily_record...")
    ok = post_daily_record()
    print(f"    ok={ok}")

    print("\n[DONE]")
