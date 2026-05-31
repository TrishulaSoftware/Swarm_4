import json
import os
import requests
from datetime import date
from config import WEBHOOKS, SWARM_IDENTITY, COLORS
from discord_dispatch import BASE_GAMES, ALT_GAMES
from player_props_dispatch import BATTING_PROPS, PITCHING_PROPS, ALT_BATTING_PROPS

SLATE_DATE = date.today().strftime("%B %d, %Y")
RAW_DATE = date.today().strftime("%m_%d_%Y")
WEBHOOK = WEBHOOKS["mlb_pick_ledger"]
LEDGER_DIR = fr"H:\Trishula_SBM\DataMine\MLB\Team Props\{RAW_DATE}"
LEDGER_FILE = os.path.join(LEDGER_DIR, f"ledger_{RAW_DATE}.json")

def create_ledger():
    if not os.path.exists(LEDGER_DIR):
        os.makedirs(LEDGER_DIR)

    # Dynamically load from today's active ODS dumps if present
    local_base_games = BASE_GAMES
    local_alt_games = ALT_GAMES
    local_batting_props = BATTING_PROPS
    local_pitching_props = PITCHING_PROPS
    local_alt_batting_props = ALT_BATTING_PROPS

    team_json = os.path.join(LEDGER_DIR, f"slate_{RAW_DATE}.json")
    if os.path.exists(team_json):
        try:
            with open(team_json, "r", encoding="utf-8") as f:
                d = json.load(f)
                local_base_games = d.get("BASE_GAMES", local_base_games)
                local_alt_games = d.get("ALT_GAMES", local_alt_games)
                print(f"[OK] Ledger loaded {len(local_base_games)} Base Games, {len(local_alt_games)} Alt Games from {team_json}")
        except Exception as e:
            print(f"[WARN] Failed to load ledger team JSON: {e}")

    player_json = os.path.join(LEDGER_DIR, f"player_slate_{RAW_DATE}.json")
    if os.path.exists(player_json):
        try:
            with open(player_json, "r", encoding="utf-8") as f:
                d = json.load(f)
                local_batting_props = d.get("BATTING_PROPS", local_batting_props)
                local_pitching_props = d.get("PITCHING_PROPS", local_pitching_props)
                local_alt_batting_props = d.get("ALT_BATTING_PROPS", local_alt_batting_props)
                print(f"[OK] Ledger loaded {len(local_batting_props)} Batting, {len(local_pitching_props)} Pitching, {len(local_alt_batting_props)} Alt Batting from {player_json}")
        except Exception as e:
            print(f"[WARN] Failed to load ledger player JSON: {e}")

    ledger_entries = []

    # 1. Team Props
    for idx, game in enumerate(local_base_games):
        ledger_entries.append({
            "id": f"TEAM_BASE_{idx}",
            "type": "Team Base Prop",
            "game": f"{game['away']} @ {game['home']}",
            "pick": game["pickType"],
            "confidence": game["confidence"],
            "status": "PENDING",
            "result": None,
            "profit_loss": 0.0
        })

    for idx, game in enumerate(local_alt_games):
        ledger_entries.append({
            "id": f"TEAM_ALT_{idx}",
            "type": "Team Alt Prop (F5 / 1st Inning)",
            "game": f"{game['away']} @ {game['home']}",
            "pick": game["pickType"],
            "confidence": game["confidence"],
            "status": "PENDING",
            "result": None,
            "profit_loss": 0.0
        })

    # 2. Player Props
    for idx, p in enumerate(local_batting_props):
        ledger_entries.append({
            "id": f"PLAYER_BAT_{idx}",
            "type": "Batting Prop",
            "game": f"{p['player']} ({p['team']}) vs {p['opp']}",
            "pick": f"{p['prop']} {p['line']} ({p['odds']})",
            "confidence": p["confidence"],
            "status": "PENDING",
            "result": None,
            "profit_loss": 0.0
        })

    for idx, p in enumerate(local_pitching_props):
        ledger_entries.append({
            "id": f"PLAYER_PIT_{idx}",
            "type": "Pitching Prop",
            "game": f"{p['player']} ({p['team']}) vs {p['opp']}",
            "pick": f"{p['prop']} {p['line']} ({p['odds']})",
            "confidence": p["confidence"],
            "status": "PENDING",
            "result": None,
            "profit_loss": 0.0
        })

    for idx, p in enumerate(local_alt_batting_props):
        ledger_entries.append({
            "id": f"PLAYER_ALT_{idx}",
            "type": "Alternate Batting Prop",
            "game": f"{p['player']} ({p['team']}) vs {p['opp']}",
            "pick": f"{p['prop']} {p['line']} ({p['odds']})",
            "confidence": p["confidence"],
            "status": "PENDING",
            "result": None,
            "profit_loss": 0.0
        })

    ledger_data = {
        "date": SLATE_DATE,
        "total_picks": len(ledger_entries),
        "status": "PENDING",
        "entries": ledger_entries
    }

    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(ledger_data, f, indent=4)
        
    print(f"[OK] Ledger saved locally to {LEDGER_FILE} with {len(ledger_entries)} picks.")
    return ledger_data

def dispatch_ledger_embed(ledger_data):
    locks_count = len([e for e in ledger_data["entries"] if int(e["confidence"].replace("%", "")) >= 90])
    
    embed = {
        "title": f"📋 TRISHULA MASTER LEDGER INITIATED",
        "description": f"**Date:** {SLATE_DATE}\n**Status:** 🟡 AWAITING RESULTS\n\nThe ledger has been mathematically sealed. No picks can be altered or removed. Tomorrow night, the Autonomous Ledger Reconciliation engine will check the MLB data feeds, resolve the W/L column, and calculate absolute ROI.",
        "color": COLORS["ledger"],
        "fields": [
            {"name": "Total Action Tracked", "value": f"`{ledger_data['total_picks']} Picks`", "inline": True},
            {"name": "Trishula Locks Tracked", "value": f"`{locks_count} Locks`", "inline": True},
            {"name": "Local Storage Volume", "value": f"`{LEDGER_FILE.split(chr(92))[-1]}`", "inline": False},
        ],
        "footer": {"text": f"Trishula Swarm | Ledger Operations | {SLATE_DATE}"}
    }

    payload = {
        **SWARM_IDENTITY,
        "content": "**[LEDGER ENGAGED]** System actively tracking all sovereign intelligence picks.",
        "embeds": [embed]
    }

    r = requests.post(WEBHOOK, json=payload)
    if r.status_code in [200, 204]:
        print("[OK] Ledger confirmation dispatched to Discord successfully.")
    else:
        print(f"[ERR] Failed to dispatch ledger confirmation: {r.status_code} {r.text}")

if __name__ == "__main__":
    print("=======================================================")
    print("  TRISHULA SWARM -- LEDGER INITIALIZATION")
    print(f"  {SLATE_DATE}")
    print("=======================================================")
    data = create_ledger()
    dispatch_ledger_embed(data)
