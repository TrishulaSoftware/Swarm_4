# -*- coding: utf-8 -*-
"""
TRISHULA SWARM -- MLB DISCORD DISPATCH ENGINE
Handles: Base Team Props + Alternate Props (F5 / 1st Inning)
Channels: #mlb-team-props
"""

import requests
import time
import sys
from config import WEBHOOKS, SWARM_IDENTITY, COLORS
from datetime import date

SLATE_DATE = date.today().strftime("%B %d, %Y")
WEBHOOK = WEBHOOKS["mlb_team_props"]

# ============================================================
#  BASE TEAM PROPS — 05/19/2026 Full Slate
# ============================================================
BASE_GAMES = [
    {"away": "ATL", "awayFull": "Atlanta Braves",          "home": "MIA", "homeFull": "Miami Marlins",
     "awaySpread": "-1.5", "awayML": "-126", "homeSpread": "+1.5", "homeML": "+108", "total": "o8 / u8",
     "awayStreak": "W1", "homeStreak": "L4", "hfAdv": "MIA +0.2 Runs", "h2h": "ATL 8-2 L10",
     "pick": "ATL -1.5", "pickType": "Run Line (-1.5)", "confidence": "84%",
     "rationale": "ATL bats firing on all cylinders. MIA bullpen is bottom-3 in the league. ATL covers the run line with high probability."},
    {"away": "BAL", "awayFull": "Baltimore Orioles",        "home": "TB",  "homeFull": "Tampa Bay Rays",
     "awaySpread": "+1.5", "awayML": "+108", "homeSpread": "-1.5", "homeML": "-100", "total": "o7.5 / u7.5",
     "awayStreak": "W1", "homeStreak": "W1", "hfAdv": "TB +0.5 Runs", "h2h": "TB 6-4 L10",
     "pick": "TB +0.5 F5 Spread", "pickType": "F5 Run Line (+0.5)", "confidence": "100%",
     "rationale": "LOCK. TB covered +0.5 First 5 Innings Spread in 4 of their last 4 home games at 100%."},
    {"away": "CLE", "awayFull": "Cleveland Guardians",     "home": "DET", "homeFull": "Detroit Tigers",
     "awaySpread": "+1.5", "awayML": "-125", "homeSpread": "-1.5", "homeML": "+108", "total": "o8 / u8",
     "awayStreak": "W3", "homeStreak": "L1", "hfAdv": "DET +0.8 Runs", "h2h": "CLE 4-1 L5",
     "pick": "DET +0.5 F5 Spread", "pickType": "F5 Run Line (+0.5)", "confidence": "100%",
     "rationale": "LOCK. DET covered +0.5 F5 Spread in 4 of their last 4 games vs CLE at 100%."},
    {"away": "CIN", "awayFull": "Cincinnati Reds",         "home": "PHI", "homeFull": "Philadelphia Phillies",
     "awaySpread": "+1.5", "awayML": "+110", "homeSpread": "-1.5", "homeML": "-137", "total": "o8.5 / u8.5",
     "awayStreak": "L2", "homeStreak": "W3", "hfAdv": "PHI +1.4 Runs", "h2h": "PHI 4-2 L6",
     "pick": "PHI +0.5 F5 Spread", "pickType": "F5 Run Line (+0.5)", "confidence": "100%",
     "rationale": "LOCK. PHI covered +0.5 F5 Spread in 6 of their last 6 games vs CIN at 100%."},
    {"away": "SF",  "awayFull": "San Francisco Giants",    "home": "ARI", "homeFull": "Arizona Diamondbacks",
     "awaySpread": "+1.5", "awayML": "+105", "homeSpread": "-1.5", "homeML": "-124", "total": "o8.5 / u8.5",
     "awayStreak": "L1", "homeStreak": "W3", "hfAdv": "ARI +0.6 Runs", "h2h": "ARI 4-0 L4",
     "pick": "ARI +0.5 F5 Spread", "pickType": "F5 Run Line (+0.5)", "confidence": "100%",
     "rationale": "LOCK. ARI covered +0.5 F5 Spread in 4 of their last 4 home games vs SF at 100%."},
    {"away": "MIL", "awayFull": "Milwaukee Brewers",       "home": "CHC", "homeFull": "Chicago Cubs",
     "awaySpread": "+1.5", "awayML": "+125", "homeSpread": "-1.5", "homeML": "-152", "total": "o8.5 / u8.5",
     "awayStreak": "L2", "homeStreak": "W4", "hfAdv": "CHC +1.1 Runs", "h2h": "CHC 3-2 L5",
     "pick": "CHC +0.5 F5 Spread", "pickType": "F5 Run Line (+0.5)", "confidence": "91%",
     "rationale": "CHC covered +0.5 F5 Spread in 10 of their last 11 home games. Wind blowing out at Wrigley."},
    {"away": "STL", "awayFull": "St. Louis Cardinals",     "home": "PIT", "homeFull": "Pittsburgh Pirates",
     "awaySpread": "-1.5", "awayML": "+100", "homeSpread": "+1.5", "homeML": "-120", "total": "o8 / u8",
     "awayStreak": "W2", "homeStreak": "L1", "hfAdv": "PIT +0.4 Runs", "h2h": "STL 3-2 L5",
     "pick": "PIT +0.5 F5 Spread", "pickType": "F5 Run Line (+0.5)", "confidence": "83%",
     "rationale": "PIT covered +0.5 F5 Spread in 5 of their last 6 home games vs STL at 83%."},
    {"away": "ATH", "awayFull": "Oakland Athletics",       "home": "LAA", "homeFull": "Los Angeles Angels",
     "awaySpread": "+1.5", "awayML": "+124", "homeSpread": "-1.5", "homeML": "-156", "total": "o4.5 / u4.5",
     "awayStreak": "L1", "homeStreak": "W2", "hfAdv": "LAA +0.6 Runs", "h2h": "LAA 3-2 L5",
     "pick": "OVER 4.5 F5 Total", "pickType": "F5 Game Total (4.5)", "confidence": "83%",
     "rationale": "ATH and LAA hit Over 4.5 First 5 Innings Game Total in 5 of their last 6 meetings at 83%."},
    {"away": "CWS", "awayFull": "Chicago White Sox",       "home": "SEA", "homeFull": "Seattle Mariners",
     "awaySpread": "+1.5", "awayML": "+132", "homeSpread": "-1.5", "homeML": "-110", "total": "o7.5 / u7.5",
     "awayStreak": "L5", "homeStreak": "W2", "hfAdv": "SEA +1.0 Runs", "h2h": "SEA 5-1 L6",
     "pick": "SEA -0.5 F5 Spread", "pickType": "F5 Run Line (-0.5)", "confidence": "83%",
     "rationale": "SEA covered -0.5 F5 Spread in 5 of their last 6 games vs CWS. CWS is the worst team in baseball."},
    {"away": "TOR", "awayFull": "Toronto Blue Jays",       "home": "NYY", "homeFull": "New York Yankees",
     "awaySpread": "+1.5", "awayML": "+165", "homeSpread": "-1.5", "homeML": "-155", "total": "o8.5 / u8.5",
     "awayStreak": "L4", "homeStreak": "W5", "hfAdv": "NYY +1.5 Runs", "h2h": "NYY 4-1 L5",
     "pick": "NYY -1.5", "pickType": "Run Line (-1.5)", "confidence": "88%",
     "rationale": "LOCK. NYY surging with a W5 streak. TOR bats are ice cold. Run line is the highest-EV play on the board."},
    {"away": "BOS", "awayFull": "Boston Red Sox",          "home": "KC",  "homeFull": "Kansas City Royals",
     "awaySpread": "-1.5", "awayML": "-111", "homeSpread": "+1.5", "homeML": "-111", "total": "o9 / u9",
     "awayStreak": "W2", "homeStreak": "L2", "hfAdv": "KC +0.7 Runs", "h2h": "BOS 4-1 L5",
     "pick": "BOS ML", "pickType": "Moneyline (-111)", "confidence": "70%",
     "rationale": "BOS bats match up well against KC rotation. Solid value play at near even-money."},
    {"away": "NYM", "awayFull": "New York Mets",           "home": "WSH", "homeFull": "Washington Nationals",
     "awaySpread": "-1.5", "awayML": "-145", "homeSpread": "+1.5", "homeML": "+126", "total": "o9.5 / u9.5",
     "awayStreak": "W3", "homeStreak": "L2", "hfAdv": "WSH +0.6 Runs", "h2h": "NYM 3-2 L5",
     "pick": "WSH +ML", "pickType": "Moneyline (+126)", "confidence": "68%",
     "rationale": "Value play. System flags +126 as +EV on WSH. NYM on road and potentially looking ahead."},
    {"away": "LAD", "awayFull": "Los Angeles Dodgers",     "home": "SD",  "homeFull": "San Diego Padres",
     "awaySpread": "-1.5", "awayML": "-160", "homeSpread": "+1.5", "homeML": "+138", "total": "o8.5 / u8.5",
     "awayStreak": "W3", "homeStreak": "L1", "hfAdv": "SD +0.8 Runs", "h2h": "LAD 7-3 L10",
     "pick": "LAD -1.5", "pickType": "Run Line (-1.5)", "confidence": "80%",
     "rationale": "LAD dominating this rivalry. Elite pitching matchup favors LAD covering the run line."},
    {"away": "HOU", "awayFull": "Houston Astros",          "home": "MIN", "homeFull": "Minnesota Twins",
     "awaySpread": "-1.5", "awayML": "-145", "homeSpread": "+1.5", "homeML": "+125", "total": "o9 / u9",
     "awayStreak": "L1", "homeStreak": "L2", "hfAdv": "MIN +0.9 Runs", "h2h": "HOU 7-3 L10",
     "pick": "MIN +ML", "pickType": "Moneyline (+125)", "confidence": "65%",
     "rationale": "Plus-money value on MIN at home. HOU road struggles and MIN hitting lefties well this season."},
]

# ============================================================
#  ALTERNATE PROPS — F5 Spreads + NRFI/YRFI (05/19/2026)
# ============================================================
ALT_GAMES = [
    {"away": "BAL", "home": "TB",
     "f5awayML": "+108", "f5homeML": "-160", "firstInning": "o0.5 / u0.5",
     "pitcherEdge": "TB (F5 Home Dominance)", "weather": "Dome",
     "pick": "TB +0.5 F5 Spread", "pickType": "F5 Run Line (+0.5)", "confidence": "100%",
     "rationale": "LOCK. TB covered +0.5 F5 in 4 of their last 4 home games vs BAL. 100%."},
    {"away": "CLE", "home": "DET",
     "f5awayML": "-125", "f5homeML": "+108", "firstInning": "o0.5 / u0.5",
     "pitcherEdge": "DET (F5 Home vs CLE)", "weather": "Mild",
     "pick": "DET +0.5 F5 Spread", "pickType": "F5 Run Line (+0.5)", "confidence": "100%",
     "rationale": "LOCK. DET covered +0.5 F5 in 4 of last 4 vs CLE. 100% hit rate."},
    {"away": "CIN", "home": "PHI",
     "f5awayML": "+110", "f5homeML": "-136", "firstInning": "o0.5 / u0.5",
     "pitcherEdge": "PHI (Jesus Luzardo B matchup +0.3 edge)", "weather": "Clear",
     "pick": "PHI +0.5 F5 Spread", "pickType": "F5 Run Line (+0.5)", "confidence": "100%",
     "rationale": "LOCK. PHI covered +0.5 F5 in 6 of their last 6 vs CIN. Perfect hit rate."},
    {"away": "SF", "home": "ARI",
     "f5awayML": "+105", "f5homeML": "-145", "firstInning": "o0.5 / u0.5",
     "pitcherEdge": "ARI (F5 Home Dominance vs SF)", "weather": "Dome",
     "pick": "ARI +0.5 F5 Spread", "pickType": "F5 Run Line (+0.5)", "confidence": "100%",
     "rationale": "LOCK. ARI covered +0.5 F5 in 4 of their last 4 home games vs SF. 100%."},
    {"away": "MIL", "home": "CHC",
     "f5awayML": "+125", "f5homeML": "-140", "firstInning": "o0.5 / u0.5",
     "pitcherEdge": "CHC (Wrigley F5 dominance)", "weather": "Wind Out",
     "pick": "CHC +0.5 F5 Spread", "pickType": "F5 Run Line (+0.5)", "confidence": "91%",
     "rationale": "CHC covered F5 in 10 of their last 11 home games. Wrigley wind factor."},
    {"away": "STL", "home": "PIT",
     "f5awayML": "+100", "f5homeML": "-144", "firstInning": "o0.5 / u0.5",
     "pitcherEdge": "PIT (F5 Home vs STL)", "weather": "Clear",
     "pick": "PIT +0.5 F5 Spread", "pickType": "F5 Run Line (+0.5)", "confidence": "83%",
     "rationale": "PIT covered F5 in 5 of their last 6 home games vs STL. 83%."},
    {"away": "ATH", "home": "LAA",
     "f5awayML": "+124", "f5homeML": "-125", "firstInning": "o0.5 / u0.5",
     "pitcherEdge": "Both offenses score early", "weather": "Marine Layer",
     "pick": "OVER 4.5 F5 Total", "pickType": "F5 Game Total (o4.5)", "confidence": "83%",
     "rationale": "ATH vs LAA hit Over 4.5 F5 in 5 of their last 6 meetings. Both teams score early."},
    {"away": "CWS", "home": "SEA",
     "f5awayML": "+132", "f5homeML": "-110", "firstInning": "o0.5 / u0.5",
     "pitcherEdge": "SEA (F5 Dominance)", "weather": "Roof Closed",
     "pick": "SEA -0.5 F5 Spread", "pickType": "F5 Run Line (-0.5)", "confidence": "83%",
     "rationale": "SEA covered -0.5 F5 in 5 of last 6 vs CWS. CWS bats go cold early."},
    {"away": "ATL", "home": "MIA",
     "f5awayML": "N/A", "f5homeML": "N/A", "firstInning": "N/A",
     "pitcherEdge": "MIA vs ATL Custom Total", "weather": "Clear",
     "pick": "MIA @ ATL Over 5.5 Runs", "pickType": "6+ Game Total (-333)", "confidence": "100%",
     "rationale": "Outlier Trend: Game Total hit 6+ runs in 6 of their last 6 games against each other (100%)."},
    {"away": "ATL", "home": "MIA",
     "f5awayML": "N/A", "f5homeML": "N/A", "firstInning": "N/A",
     "pitcherEdge": "MIA vs ATL Custom Total", "weather": "Clear",
     "pick": "MIA @ ATL Over 6.5 Runs", "pickType": "7+ Game Total (-203)", "confidence": "100%",
     "rationale": "Outlier Trend: Game Total hit 7+ runs in 6 of their last 6 games against each other (100%)."},
    {"away": "ATL", "home": "MIA",
     "f5awayML": "N/A", "f5homeML": "N/A", "firstInning": "N/A",
     "pitcherEdge": "MIA +2.5 Spread", "weather": "Clear",
     "pick": "MIA +2.5 Spread", "pickType": "MIA +2.5 Spread (-204)", "confidence": "100%",
     "rationale": "Outlier Trend: MIA +2.5 covered in 5 of their last 5 home games (100%)."},
]


def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def build_base_embed(g):
    is_lock = int(g["confidence"].replace("%", "")) >= 90
    color = COLORS["lock"] if is_lock else COLORS["base_props"]
    return {
        "title": f"⚾  {g['awayFull']}  @  {g['homeFull']}",
        "color": color,
        "fields": [
            {"name": f"**{g['away']}** (Streak: {g['awayStreak']})",
             "value": f"Spread: `{g['awaySpread']}`  |  ML: `{g['awayML']}`", "inline": True},
            {"name": f"**{g['home']}** (Streak: {g['homeStreak']})",
             "value": f"Spread: `{g['homeSpread']}`  |  ML: `{g['homeML']}`", "inline": True},
            {"name": "Game Total", "value": f"`{g['total']}`", "inline": False},
            {"name": "⚡ Trishula Edge Intelligence",
             "value": f"**HFA:** {g['hfAdv']}\n**H2H:** {g['h2h']}", "inline": False},
            {"name": f"{'🔒 LOCK' if is_lock else '🎯 THE PICK'} — {g['pick']}",
             "value": f"**Type:** `{g['pickType']}`\n**Confidence:** `{g['confidence']}`\n{g['rationale']}",
             "inline": False},
        ],
        "footer": {"text": f"Trishula Sovereign Swarm | Base Props | {SLATE_DATE}"}
    }


def build_alt_embed(g, idx):
    is_lock = int(g["confidence"].replace("%", "")) >= 90
    color = COLORS["lock"] if is_lock else COLORS["alt_props"]
    return {
        "title": f"⚡  {g['away']}  @  {g['home']}  —  F5 / 1st Inning",
        "color": color,
        "fields": [
            {"name": "F5 Moneylines",
             "value": f"`{g['away']}` {g['f5awayML']}  |  `{g['home']}` {g['f5homeML']}", "inline": True},
            {"name": "1st Inning (YRFI/NRFI)",
             "value": f"`{g['firstInning']}`", "inline": True},
            {"name": "🔬 Starter Edge", "value": g["pitcherEdge"], "inline": True},
            {"name": "🌤️ Weather / Park", "value": g["weather"], "inline": True},
            {"name": f"{'🔒 LOCK' if is_lock else '🎯 THE PICK'} — {g['pick']}",
             "value": f"**Type:** `{g['pickType']}`\n**Confidence:** `{g['confidence']}`\n{g['rationale']}",
             "inline": False},
        ],
        "footer": {"text": f"Trishula Sovereign Swarm | Alt Props | {SLATE_DATE}"}
    }


def post_embeds(embeds, content=""):
    for batch in chunk(embeds, 10):
        payload = {**SWARM_IDENTITY, "content": content, "embeds": batch}
        r = requests.post(WEBHOOK, json=payload)
        if r.status_code == 204:
            print(f"  [OK] Batch dispatched ({len(batch)} embeds)")
        else:
            print(f"  [ERR] {r.status_code}: {r.text}")
        time.sleep(2)
        content = ""   # only show content header on first batch


def dispatch():
    print("\n" + "="*55)
    print("  TRISHULA SWARM -- MLB DISPATCH")
    print(f"  {SLATE_DATE}")
    print("="*55 + "\n")

    # Try loading dynamic slate data from today's ODS dump
    global BASE_GAMES, ALT_GAMES
    import os, json
    RAW_DATE = date.today().strftime("%m_%d_%Y")
    JSON_PATH = fr"H:\Trishula_SBM\DataMine\MLB\Team Props\{RAW_DATE}\slate_{RAW_DATE}.json"
    if os.path.exists(JSON_PATH):
        try:
            with open(JSON_PATH, "r", encoding="utf-8") as f:
                dynamic_data = json.load(f)
                BASE_GAMES = dynamic_data.get("BASE_GAMES", BASE_GAMES)
                ALT_GAMES = dynamic_data.get("ALT_GAMES", ALT_GAMES)
                print(f"[OK] Dynamically loaded {len(BASE_GAMES)} Base Games and {len(ALT_GAMES)} Alt Games from {JSON_PATH}")
        except Exception as e:
            print(f"[WARN] Failed to load dynamic JSON slate: {e}")


    # --- BASE PROPS ---
    # print("Dispatching Base Team Props...")
    # base_embeds = [build_base_embed(g) for g in BASE_GAMES]
    # post_embeds(base_embeds, content=f"**BASE TEAM PROPS -- {SLATE_DATE.upper()}**\n14 Games | Trishula Edge Active")

    # time.sleep(3)

    # --- ALTERNATE PROPS ---
    # print("\nDispatching Alternate Props (F5 / 1st Inning)...")
    # alt_embeds = [build_alt_embed(g, i) for i, g in enumerate(ALT_GAMES)]
    # post_embeds(alt_embeds, content=f"**ALTERNATE PROPS (F5 / NRFI-YRFI) -- {SLATE_DATE.upper()}**\n14 Games | F5 Moneylines + 1st Inning Totals")

    # print("\n[DONE] Full slate dispatched successfully.\n")

    # Generate HTML automatically
    html_file = export_html()
    
    # Render and post the screenshot to Discord
    post_html_screenshot(html_file)


# ============================================================
# HTML Generation
# ============================================================
def export_html():
    import json
    file_path = fr"H:\Trishula_SBM\DataMine\MLB\Team Props\mlb_unified_props_{date.today().strftime('%m%d%Y')}.html"
    
    html_content = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>⚾ MLB Trishula Unified Props — {SLATE_DATE}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0d1117;color:#e6edf3;font-family:'Inter',sans-serif;padding:32px;min-height:100vh}}
h1{{font-size:2.2rem;font-weight:900;margin-bottom:8px;text-transform:uppercase;letter-spacing:1px;background:-webkit-linear-gradient(45deg, #58a6ff, #8a2be2);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.meta{{color:#8b949e;font-size:0.9rem;margin-bottom:24px;font-weight:600}}
.tabs{{display:flex;gap:12px;margin-bottom:24px;border-bottom:1px solid rgba(255,255,255,0.1);padding-bottom:12px}}
.tab{{background:rgba(255,255,255,0.05);color:#8b949e;padding:10px 20px;border-radius:8px;font-weight:700;cursor:pointer;transition:all 0.2s}}
.tab.active{{background:rgba(88,166,255,0.15);color:#58a6ff;border:1px solid rgba(88,166,255,0.3)}}

/* SPREADSHEET TABLE DESIGN */
table {{width: 100%; border-collapse: separate; border-spacing: 0 8px;}}
th {{text-align: left; padding: 12px 16px; color: #8b949e; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; font-weight: 700; border-bottom: 1px solid rgba(255,255,255,0.1);}}
td {{padding: 16px; background: rgba(22, 27, 34, 0.8); border-top: 1px solid rgba(255,255,255,0.05); border-bottom: 1px solid rgba(255,255,255,0.05); vertical-align: middle;}}
td:first-child {{border-left: 1px solid rgba(255,255,255,0.05); border-top-left-radius: 8px; border-bottom-left-radius: 8px; border-left: 4px solid rgba(255,255,255,0.1);}}
td:last-child {{border-right: 1px solid rgba(255,255,255,0.05); border-top-right-radius: 8px; border-bottom-right-radius: 8px;}}

/* ROW HIGHLIGHTS (LOCKS) */
tr.lock td {{background: rgba(240, 192, 64, 0.08); border-top-color: rgba(240, 192, 64, 0.2); border-bottom-color: rgba(240, 192, 64, 0.2);}}
tr.lock td:first-child {{border-left: 4px solid #f0c040;}}
tr.lock td:last-child {{border-right-color: rgba(240, 192, 64, 0.2);}}

/* DATA CELLS */
.player-name {{font-size: 1.1rem; font-weight: 900; color: #ffffff; margin-bottom: 2px; display: block;}}
.team-matchup {{font-size: 0.85rem; color: #8b949e; font-weight: 600; text-transform: uppercase;}}
.prop-type {{font-size: 0.85rem; color: #c9d1d9; font-weight: 700; display: block; margin-bottom: 4px;}}
.line-val {{font-size: 1.1rem; font-weight: 900; color: #ffffff;}}
.odds-badge {{padding: 4px 8px; border-radius: 4px; font-size: 0.85rem; font-weight: 800; display: inline-block; margin-left: 6px;}}
.odds-pos {{background: rgba(63,185,80,0.15); color: #3fb950; border: 1px solid rgba(63,185,80,0.3);}}
.odds-neg {{background: rgba(255,123,114,0.15); color: #ff7b72; border: 1px solid rgba(255,123,114,0.3);}}
.pick-text {{font-size: 1.0rem; font-weight: 900; color: #58a6ff;}}
tr.lock .pick-text {{color: #f0c040;}}
.conf-text {{font-size: 0.85rem; font-weight: 900; color: #3fb950; display: block; margin-top: 4px;}}
.rationale-text {{font-size: 0.75rem; color: #8b949e; font-style: italic; line-height: 1.4; max-width: 250px;}}

.hidden {{ display: none !important; }}
</style></head><body>

<h1>⚾ Trishula Intelligence Nexus — Unified MLB</h1>
<p class="meta">Premium Social Intelligence Spreadsheet · Base & Alternate Props · {SLATE_DATE}</p>

<div class="tabs">
  <div class="tab active" id="tab-base" onclick="switchTab('base')">BASE TEAM PROPS</div>
  <div class="tab" id="tab-alt" onclick="switchTab('alt')">ALTERNATE PROPS (F5 / 1ST INNING)</div>
</div>

<div id="games-base">
  <table>
    <thead><tr><th>Matchup</th><th>Edge / Odds</th><th>The Pick</th><th>Analysis</th></tr></thead>
    <tbody id="tbody-base"></tbody>
  </table>
</div>
<div id="games-alt" class="hidden">
  <table>
    <thead><tr><th>Matchup</th><th>Alt Lines</th><th>The Pick</th><th>Analysis</th></tr></thead>
    <tbody id="tbody-alt"></tbody>
  </table>
</div>

<script>
const BASE_GAMES = {json.dumps(BASE_GAMES)};
const ALT_GAMES = {json.dumps(ALT_GAMES)};

function getOddsClass(odds) {{
  if(!odds) return '';
  if(odds.includes('+')) return 'odds-pos';
  if(odds.includes('-')) return 'odds-neg';
  return '';
}}

function renderBase() {{
  const tbody = document.getElementById("tbody-base");
  BASE_GAMES.forEach((g)=>{{
    const confInt = parseInt(g.confidence.replace('%',''));
    const isLock = confInt >= 90;
    const lockClass = isLock ? 'lock' : '';

    tbody.innerHTML += `
    <tr class="${{lockClass}}">
      <td>
        <span class="player-name">${{g.away}} @ ${{g.home}}</span>
        <span class="team-matchup">${{g.awayFull}} @ ${{g.homeFull}}</span>
      </td>
      <td>
        <span class="prop-type">Spread: ${{g.away}} ${{g.awaySpread}} | ${{g.home}} ${{g.homeSpread}}</span>
        <span class="prop-type">ML: <span class="odds-badge ${{getOddsClass(g.awayML)}}">${{g.awayML}}</span> | <span class="odds-badge ${{getOddsClass(g.homeML)}}">${{g.homeML}}</span></span>
        <span class="prop-type" style="margin-top:6px; color:#f0c040">Total: ${{g.total}}</span>
      </td>
      <td>
        <span class="pick-text">${{g.pick}}</span><br>
        <span class="conf-text">${{g.pickType}}</span>
        <span class="conf-text">${{g.confidence}} Edge</span>
      </td>
      <td><div class="rationale-text">${{g.rationale}}</div></td>
    </tr>`;
  }});
}}

function renderAlt() {{
  const tbody = document.getElementById("tbody-alt");
  ALT_GAMES.forEach((g)=>{{
    const confInt = parseInt(g.confidence.replace('%',''));
    const isLock = confInt >= 90;
    const lockClass = isLock ? 'lock' : '';

    tbody.innerHTML += `
    <tr class="${{lockClass}}">
      <td>
        <span class="player-name">${{g.away}} @ ${{g.home}}</span>
      </td>
      <td>
        <span class="prop-type">F5 ML: ${{g.away}} <span class="odds-badge ${{getOddsClass(g.f5awayML)}}">${{g.f5awayML}}</span> | ${{g.home}} <span class="odds-badge ${{getOddsClass(g.f5homeML)}}">${{g.f5homeML}}</span></span>
        <span class="prop-type" style="margin-top:6px; color:#58a6ff">1st Inning: ${{g.firstInning}}</span>
      </td>
      <td>
        <span class="pick-text">${{g.pick}}</span><br>
        <span class="conf-text">${{g.pickType}}</span>
        <span class="conf-text">${{g.confidence}} Edge</span>
      </td>
      <td><div class="rationale-text">${{g.rationale}}</div></td>
    </tr>`;
  }});
}}

function switchTab(tabId) {{
  document.getElementById('tab-base').classList.remove('active');
  document.getElementById('tab-alt').classList.remove('active');
  document.getElementById('games-base').classList.add('hidden');
  document.getElementById('games-alt').classList.add('hidden');
  document.getElementById('tab-' + tabId).classList.add('active');
  document.getElementById('games-' + tabId).classList.remove('hidden');
}}

renderBase();
renderAlt();
</script></body></html>"""

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"  [OK] Generated HTML: {file_path}")
    
    return file_path

# ============================================================
# Playwright Screenshot & Discord Image Upload
# ============================================================
def post_html_screenshot(html_path):
    import time
    from playwright.sync_api import sync_playwright
    
    base_png_path = html_path.replace(".html", "_base.png")
    alt_png_path = html_path.replace(".html", "_alt.png")
    
    print("  [WAIT] Booting Headless Browser to screenshot HTML tabs...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 900, "height": 1000})
        page.goto(f"file:///{html_path.replace(chr(92), '/')}") 
        time.sleep(2)
        
        # Screenshot Base Props
        page.screenshot(path=base_png_path, full_page=True)
        print(f"  [OK] Saved Base PNG: {base_png_path}")
        
        # Switch to Alt Props Tab
        page.click("#tab-alt")
        time.sleep(1)
        
        # Screenshot Alt Props
        page.screenshot(path=alt_png_path, full_page=True)
        print(f"  [OK] Saved Alt PNG: {alt_png_path}")
        browser.close()
        
    print("  [WAIT] Uploading Images to Discord Webhook...")
    for png in [base_png_path, alt_png_path]:
        with open(png, "rb") as f:
            files = {"file": (png.split("\\")[-1], f, "image/png")}
            payload = {"content": f"**SOCIAL MEDIA ASSET READY**\nGenerated `{png.split(chr(92))[-1]}`"}
            r = requests.post(WEBHOOK, data=payload, files=files)
            
            if r.status_code in [200, 204]:
                print(f"  [OK] {png.split(chr(92))[-1]} uploaded to Discord successfully.")
            else:
                print(f"  [ERR] Failed to upload image: {r.status_code} {r.text}")


if __name__ == "__main__":
    dispatch()
