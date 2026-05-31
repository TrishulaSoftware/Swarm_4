# -*- coding: utf-8 -*-
"""
TRISHULA SWARM -- LEDGER RECONCILIATION ENGINE
Reads the daily ledger JSON, autonomously hunts MLB Stats API for final results,
grades every PENDING pick as WIN or LOSS, calculates ROI, and reports to Discord.

Usage: python ledger_reconciliation.py
       (Run AFTER games are complete for the slate date)
"""

import json
import os
import requests
import time
import argparse
from datetime import date, datetime
from config import WEBHOOKS, SWARM_IDENTITY, COLORS
from discord_dispatch import BASE_GAMES, ALT_GAMES

# ============================================================
# CONFIG
# ============================================================
parser = argparse.ArgumentParser()
parser.add_argument("--date", type=str, default=None, help="Slate date override in MM_DD_YYYY format e.g. 05_18_2026")
args, _ = parser.parse_known_args()

if args.date:
    RAW_DATE = args.date
    d = datetime.strptime(args.date, "%m_%d_%Y")
    SLATE_DATE_STR = d.strftime("%B %d, %Y")
    API_DATE = d.strftime("%Y-%m-%d")
else:
    RAW_DATE = date.today().strftime("%m_%d_%Y")
    SLATE_DATE_STR = date.today().strftime("%B %d, %Y")
    API_DATE = date.today().strftime("%Y-%m-%d")

LEDGER_DIR  = fr"H:\Trishula_SBM\DataMine\MLB\Team Props\{RAW_DATE}"
LEDGER_FILE = os.path.join(LEDGER_DIR, f"ledger_{RAW_DATE}.json")
RESULTS_FILE = os.path.join(LEDGER_DIR, f"ledger_{RAW_DATE}_FINAL.json")

WEBHOOK = WEBHOOKS["mlb_pick_ledger"]

MLB_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"
MLB_BOXSCORE_URL = "https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"
MLB_PLAYER_STATS_URL = "https://statsapi.mlb.com/api/v1/game/{game_pk}/boxscore"

# ============================================================
# MLB API HELPERS
# ============================================================

def fetch_todays_games():
    """Pull all completed game PKs for today's slate."""
    params = {
        "sportId": 1,
        "date": API_DATE,
        "hydrate": "team,linescore"
    }
    try:
        r = requests.get(MLB_SCHEDULE_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        games = []
        for date_entry in data.get("dates", []):
            for game in date_entry.get("games", []):
                status = game.get("status", {}).get("abstractGameState", "")
                games.append({
                    "game_pk": game["gamePk"],
                    "away": game["teams"]["away"]["team"]["abbreviation"],
                    "home": game["teams"]["home"]["team"]["abbreviation"],
                    "status": status,
                    "away_score": game["teams"]["away"].get("score", None),
                    "home_score": game["teams"]["home"].get("score", None),
                    "linescore": game.get("linescore", {})
                })
        print(f"  [API] Fetched {len(games)} games for {API_DATE}")
        return games
    except Exception as e:
        print(f"  [ERR] Failed to fetch schedule: {e}")
        return []

def fetch_boxscore(game_pk):
    """Pull the full boxscore for a single game."""
    try:
        url = MLB_BOXSCORE_URL.format(game_pk=game_pk)
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"  [ERR] Failed to fetch boxscore for game {game_pk}: {e}")
        return None

def extract_player_stats(boxscore):
    """
    From a boxscore, build a flat dict of:
    { player_last_name (upper): { "H": int, "R": int, "RBI": int, "TB": int,
                                   "SO": int, "IP": float, "outs": int } }
    """
    player_stats = {}
    for side in ["away", "home"]:
        batters = boxscore.get("teams", {}).get(side, {}).get("batters", [])
        pitchers = boxscore.get("teams", {}).get(side, {}).get("pitchers", [])
        players_dict = boxscore.get("teams", {}).get(side, {}).get("players", {})

        for pid in batters + pitchers:
            key = f"ID{pid}"
            player_data = players_dict.get(key, {})
            person = player_data.get("person", {})
            full_name = person.get("fullName", "").upper()
            last_name = full_name.split()[-1] if full_name else "UNKNOWN"
            
            stats = player_data.get("stats", {})
            batting  = stats.get("batting",  {}).get("summary", "")
            pitching = stats.get("pitching", {})
            bat_raw  = stats.get("batting", {})

            hits     = bat_raw.get("hits", 0)
            runs     = bat_raw.get("runs", 0)
            rbi      = bat_raw.get("rbi", 0)
            tb       = bat_raw.get("totalBases", 0)
            so_bat   = bat_raw.get("strikeOuts", 0)

            pit_raw  = stats.get("pitching", {})
            so_pit   = pit_raw.get("strikeOuts", 0)
            outs_pit = pit_raw.get("outs", 0)

            player_stats[full_name] = {
                "H": hits,
                "R": runs,
                "RBI": rbi,
                "TB": tb,
                "H+R+RBI": hits + runs + rbi,
                "SO_bat": so_bat,
                "SO_pit": so_pit,
                "outs": outs_pit,
                "last_name": last_name
            }
    return player_stats

# ============================================================
# PICK GRADER
# ============================================================

def grade_team_pick(entry, games):
    """
    Grade a team base or alt pick. Entry game format: 'AWAY @ HOME'
    Uses the base or alt game original pick to determine direction and criteria perfectly.
    Returns 'WIN', 'LOSS', 'PUSH', or 'PENDING'
    """
    try:
        parts = entry["game"].split(" @ ")
        away_abbr = parts[0].strip().upper()
        home_abbr = parts[1].strip().upper()
        
        # Normalize abbreviations (e.g. ARI to AZ) for Stats API
        away_norm = "AZ" if away_abbr == "ARI" else away_abbr
        home_norm = "AZ" if home_abbr == "ARI" else home_abbr
        
        matched_game = None
        for g in games:
            g_away = g["away"].upper()
            g_home = g["home"].upper()
            g_away_norm = "AZ" if g_away == "ARI" else g_away
            g_home_norm = "AZ" if g_home == "ARI" else g_home
            
            if (g_away_norm == away_norm and g_home_norm == home_norm) or \
               (g_away_norm == home_norm and g_home_norm == away_norm):
                matched_game = g
                break
        
        if not matched_game:
            return "PENDING", "Game not found or not yet started"
        
        if matched_game["status"] != "Final":
            return "PENDING", f"Game status: {matched_game['status']}"

        # Retrieve the original pick info using the entry ID index
        # entry["id"] has format TEAM_BASE_{idx} or TEAM_ALT_{idx}
        id_parts = entry["id"].split("_")
        idx = int(id_parts[-1])
        
        if "BASE" in entry["id"]:
            original_game = BASE_GAMES[idx]
        else:
            original_game = ALT_GAMES[idx]
            
        pick_str = original_game["pick"].upper() # e.g. "BOS ML", "TB +0.5 F5 SPREAD", "MIA @ ATL OVER 5.5 RUNS"
        pick_type = original_game.get("pickType", "").upper()
        
        away_score = matched_game.get("away_score", 0) or 0
        home_score = matched_game.get("home_score", 0) or 0
        
        # 1. 1ST INNING / NRFI / YRFI
        if "1ST INNING" in pick_type or "NRFI" in pick_str or "YRFI" in pick_str:
            innings = matched_game.get("linescore", {}).get("innings", [])
            if innings:
                first = innings[0]
                runs_in_1st = (first.get("away", {}).get("runs", 0) or 0) + (first.get("home", {}).get("runs", 0) or 0)
                if "U0.5" in pick_str or "NRFI" in pick_str:
                    return ("WIN" if runs_in_1st == 0 else "LOSS"), f"1st inning runs: {runs_in_1st}"
                elif "O0.5" in pick_str or "YRFI" in pick_str:
                    return ("WIN" if runs_in_1st > 0 else "LOSS"), f"1st inning runs: {runs_in_1st}"
            return "PENDING", "1st inning data not available"
            
        # 2. RUN SPREADS (e.g. Run Line / F5 Run Line)
        if "SPREAD" in pick_type or "RUN LINE" in pick_type or "SPREAD" in pick_str or "RUN LINE" in pick_str:
            # Determine if F5 or Full Game
            is_f5 = "F5" in pick_type or "F5" in pick_str
            
            # Determine scores
            if is_f5:
                innings = matched_game.get("linescore", {}).get("innings", [])
                a_score = sum((inn.get("away", {}).get("runs", 0) or 0) for inn in innings[:5])
                h_score = sum((inn.get("home", {}).get("runs", 0) or 0) for inn in innings[:5])
                score_desc = f"F5: {away_abbr} {a_score} - {home_abbr} {h_score}"
            else:
                a_score = away_score
                h_score = home_score
                score_desc = f"Final: {away_abbr} {a_score} - {home_abbr} {h_score}"
                
            # Parse spread value
            import re
            spread_match = re.search(r'([+-]\d+\.?\d*)', pick_str)
            if not spread_match:
                # Try pickType if not in pick
                spread_match = re.search(r'([+-]\d+\.?\d*)', pick_type)
            if not spread_match:
                return "PENDING", f"Could not parse spread value from {pick_str} or {pick_type}"
                
            spread_val = float(spread_match.group(1))
            
            # Figure out which team was selected
            if away_abbr in pick_str:
                selected_team = "AWAY"
            elif home_abbr in pick_str:
                selected_team = "HOME"
            elif "MIA" in pick_str:
                selected_team = "AWAY" if away_abbr == "MIA" else "HOME"
            elif "ATL" in pick_str:
                selected_team = "AWAY" if away_abbr == "ATL" else "HOME"
            elif away_abbr in pick_type:
                selected_team = "AWAY"
            elif home_abbr in pick_type:
                selected_team = "HOME"
            else:
                # Default to pickType name check
                if "AWAY" in pick_type:
                    selected_team = "AWAY"
                else:
                    selected_team = "HOME"
                    
            if selected_team == "AWAY":
                diff = a_score + spread_val - h_score
                if diff > 0:
                    return "WIN", f"{score_desc} | Away Covered {spread_val}"
                elif diff == 0:
                    return "PUSH", f"{score_desc} | Spread Push {spread_val}"
                else:
                    return "LOSS", f"{score_desc} | Away Failed Cover {spread_val}"
            else:
                diff = h_score + spread_val - a_score
                if diff > 0:
                    return "WIN", f"{score_desc} | Home Covered {spread_val}"
                elif diff == 0:
                    return "PUSH", f"{score_desc} | Spread Push {spread_val}"
                else:
                    return "LOSS", f"{score_desc} | Home Failed Cover {spread_val}"
                    
        # 3. GAME TOTALS (e.g. Over/Under)
        if "TOTAL" in pick_type or "OVER" in pick_str or "UNDER" in pick_str or "GAME TOTAL" in pick_type:
            is_f5 = "F5" in pick_type or "F5" in pick_str
            
            # Determine total runs
            if is_f5:
                innings = matched_game.get("linescore", {}).get("innings", [])
                total_runs_actual = sum((inn.get("away", {}).get("runs", 0) or 0) + (inn.get("home", {}).get("runs", 0) or 0) for inn in innings[:5])
                score_desc = f"F5 Total: {total_runs_actual}"
            else:
                total_runs_actual = away_score + home_score
                score_desc = f"Final Total: {total_runs_actual}"
                
            # Parse line value
            import re
            line_match = re.search(r'(\d+\.?\d*)', pick_str)
            if not line_match:
                line_match = re.search(r'(\d+\.?\d*)', pick_type)
            if not line_match:
                return "PENDING", f"Could not parse total line from {pick_str} or {pick_type}"
                
            line_val = float(line_match.group(1))
            
            # Determine direction (Over/Under)
            if "UNDER" in pick_str or "UNDER" in pick_type or "U" + str(line_val) in pick_str:
                is_over = False
            else:
                is_over = True
                
            if is_over:
                return ("WIN" if total_runs_actual > line_val else "LOSS"), f"{score_desc} (vs line {line_val})"
            else:
                return ("WIN" if total_runs_actual < line_val else "LOSS"), f"{score_desc} (vs line {line_val})"
                
        # 4. MONEYLINE
        if "ML" in pick_str or "MONEYLINE" in pick_type or "MONEYLINE" in pick_str:
            # Determine which team was selected
            if away_abbr in pick_str:
                selected_team = "AWAY"
            elif home_abbr in pick_str:
                selected_team = "HOME"
            elif away_abbr in pick_type:
                selected_team = "AWAY"
            elif home_abbr in pick_type:
                selected_team = "HOME"
            else:
                return "PENDING", f"Could not determine Moneyline team selection from {pick_str}"
                
            score_desc = f"Final: {away_abbr} {away_score} - {home_abbr} {home_score}"
            if selected_team == "AWAY":
                return ("WIN" if away_score > home_score else "LOSS"), f"{score_desc} | Selected {away_abbr}"
            else:
                return ("WIN" if home_score > away_score else "LOSS"), f"{score_desc} | Selected {home_abbr}"
                
        return "PENDING", f"Unrecognized pick format: {pick_str} / {pick_type}"
        
    except Exception as e:
        return "PENDING", f"Grade error: {e}"



def grade_player_pick(entry, all_player_stats, games):
    """
    Grade a player prop. Entry pick format: 'Prop o/u Line (odds)'
    e.g. 'Hits o0.5 (-250)'
    """
    try:
        game_str = entry["game"]  # e.g. "Elly De La Cruz (CIN) vs PHI"
        player_name = game_str.split("(")[0].strip().upper()
        pick_str = entry["pick"].upper()  # e.g. "HITS O0.5 (-250)"

        # Determine direction and line
        direction = "OVER" if "O0." in pick_str or "OVER" in pick_str or " O" in pick_str else "UNDER"
        
        # Extract the numeric line
        import re
        line_match = re.search(r'[OU](\d+\.?\d*)', pick_str)
        if not line_match:
            # Try finding any decimal number
            line_match = re.search(r'(\d+\.\d+)', pick_str)
        if not line_match:
            return "PENDING", "Could not parse line from pick"
        line = float(line_match.group(1))

        # Find the player in the stats dict — fuzzy match on any part of name
        matched_stats = None
        player_parts = player_name.split()
        for name, stats in all_player_stats.items():
            # Match on full name or any significant name part (last name priority)
            if player_name in name:
                matched_stats = stats
                break
            # Try last name match
            if player_parts and player_parts[-1] in name:
                matched_stats = stats
                break
            # Try first + last
            if len(player_parts) >= 2 and player_parts[0] in name and player_parts[-1] in name:
                matched_stats = stats
                break

        if not matched_stats:
            # Check if the player's team's game is finished (Final)
            # Find the team abbreviation from entry or game string e.g. "Yandy Diaz (TB) vs BAL"
            player_team = ""
            import re
            team_match = re.search(r'\(([A-Z]+)\)', game_str)
            if team_match:
                player_team = team_match.group(1).upper()
            
            team_game_final = False
            for g in games:
                g_away = g["away"].upper()
                g_home = g["home"].upper()
                if g_away == player_team or g_home == player_team or \
                   (player_team == "TB" and (g_away == "TB" or g_home == "TB")) or \
                   (player_team == "CLE" and (g_away == "CLE" or g_home == "CLE")):
                    if g["status"] == "Final":
                        team_game_final = True
                        break
            
            if team_game_final:
                return "VOID", f"Player '{player_name}' did not play (DNP) / VOID"
            else:
                return "PENDING", f"Player '{player_name}' not in completed boxscores yet"

        # Determine the stat category
        stat_key = None
        if "H+R+RBI" in pick_str:
            stat_key = "H+R+RBI"
        elif "TOTAL BASES" in pick_str:
            stat_key = "TB"
        elif "HITS" in pick_str or "HIT" in pick_str:
            stat_key = "H"
        elif "RUNS" in pick_str and "RBI" not in pick_str:
            stat_key = "R"
        elif "RBI" in pick_str:
            stat_key = "RBI"
        elif "PITCHER OUTS" in pick_str:
            stat_key = "outs"
        elif "STRIKEOUTS" in pick_str:
            stat_key = "SO_pit"
        else:
            return "PENDING", f"Unknown prop type: {pick_str}"

        actual = matched_stats.get(stat_key, 0)
        
        if direction == "OVER":
            result = "WIN" if actual > line else "LOSS"
        else:
            result = "WIN" if actual < line else "LOSS"

        return result, f"Actual {stat_key}: {actual} (vs line {line})"

    except Exception as e:
        return "PENDING", f"Grade error: {e}"

# ============================================================
# MAIN RECONCILIATION ENGINE
# ============================================================

def reconcile():
    print("\n" + "="*55)
    print("  TRISHULA SWARM -- LEDGER RECONCILIATION ENGINE")
    print(f"  {SLATE_DATE_STR}")
    print("="*55 + "\n")

    # 1. Load the ledger
    if not os.path.exists(LEDGER_FILE):
        print(f"  [ERR] Ledger file not found: {LEDGER_FILE}")
        return
    
    with open(LEDGER_FILE, "r", encoding="utf-8") as f:
        ledger = json.load(f)

    print(f"  [OK] Loaded ledger: {ledger['total_picks']} picks")

    # 2. Fetch all game results from MLB Stats API
    print(f"\n  [API] Fetching game results for {API_DATE}...")
    games = fetch_todays_games()
    
    # 3. Build a master player stats map from all completed boxscores
    print(f"\n  [API] Building player stats map from boxscores...")
    all_player_stats = {}
    for game in games:
        if game["status"] == "Final":
            bs = fetch_boxscore(game["game_pk"])
            if bs:
                stats = extract_player_stats(bs)
                all_player_stats.update(stats)
                print(f"    [OK] Processed boxscore: {game['away']} @ {game['home']}")
            time.sleep(0.3)  # Respect MLB API rate limits

    print(f"\n  [OK] Player stats loaded for {len(all_player_stats)} players")

    # 4. Grade every entry
    wins = 0
    losses = 0
    voids = 0
    pending = 0

    for entry in ledger["entries"]:
        if entry["status"] != "PENDING" and entry["status"] not in ["WIN", "LOSS", "VOID", "PUSH"]:
            continue

        entry_type = entry["type"]

        if "Team" in entry_type:
            result, detail = grade_team_pick(entry, games)
        else:
            result, detail = grade_player_pick(entry, all_player_stats, games)

        entry["status"]  = result
        entry["result"]  = detail

        if result == "WIN":
            wins += 1
        elif result == "LOSS":
            losses += 1
        elif result in ["VOID", "PUSH"]:
            voids += 1
        else:
            pending += 1

        icon = f"[{result}]"
        print(f"    {icon} {entry['id']}: {entry['game']} | {detail}")

    # 5. Calculate strike rate
    graded = wins + losses
    strike_rate = round((wins / graded * 100), 1) if graded > 0 else 0.0
    ledger["status"] = "FINAL"
    ledger["wins"] = wins
    ledger["losses"] = losses
    ledger["voids"] = voids
    ledger["pending"] = pending
    ledger["strike_rate"] = f"{strike_rate}%"

    # 6. Save the final ledger
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=4)
    print(f"\n  [OK] Final ledger saved: {RESULTS_FILE}")

    # 7. Dispatch results to Discord
    dispatch_results(ledger, wins, losses, voids, pending, strike_rate)


def dispatch_results(ledger, wins, losses, voids, pending, strike_rate):
    target = 70.0
    on_target = strike_rate >= target
    color = COLORS["lock"] if on_target else COLORS.get("alert", 0xFF0000)

    status_icon = "🟢 ON TARGET" if on_target else "🔴 BELOW TARGET"
    
    embed = {
        "title": "📊 TRISHULA LEDGER — FINAL RECONCILIATION",
        "description": (
            f"**Slate Date:** {SLATE_DATE_STR}\n"
            f"**Strike Rate:** `{strike_rate}%` — {status_icon}\n"
            f"**Target Accuracy:** `70–75%`\n\n"
            f"The Autonomous Reconciliation Engine has processed all final MLB results "
            f"and resolved the PENDING ledger."
        ),
        "color": color,
        "fields": [
            {"name": "WINS",    "value": f"`{wins}`",    "inline": True},
            {"name": "LOSSES",  "value": f"`{losses}`",  "inline": True},
            {"name": "VOIDS",   "value": f"`{voids}`",   "inline": True},
            {"name": "PENDING", "value": f"`{pending}`", "inline": True},
            {"name": "Strike Rate",   "value": f"`{strike_rate}%`",          "inline": True},
            {"name": "Picks Graded",  "value": f"`{wins + losses}` / `{ledger['total_picks']}`", "inline": True},
        ],
        "footer": {"text": f"Trishula Sovereign Swarm | Ledger Ops | {SLATE_DATE_STR}"}
    }

    # Append top wins and losses
    win_entries  = [e for e in ledger["entries"] if e["status"] == "WIN"][:5]
    loss_entries = [e for e in ledger["entries"] if e["status"] == "LOSS"][:5]

    if win_entries:
        embed["fields"].append({
            "name": "[TOP WINS]",
            "value": "\n".join([f"`{e['id']}` -- {e['game']}: {e['result']}" for e in win_entries]),
            "inline": False
        })
    if loss_entries:
        embed["fields"].append({
            "name": "[LOSSES]",
            "value": "\n".join([f"`{e['id']}` -- {e['game']}: {e['result']}" for e in loss_entries]),
            "inline": False
        })

    payload = {
        **SWARM_IDENTITY,
        "content": f"**[LEDGER RECONCILIATION COMPLETE]** — {SLATE_DATE_STR}",
        "embeds": [embed]
    }

    r = requests.post(WEBHOOKS["mlb_pick_ledger"], json=payload)
    if r.status_code in [200, 204]:
        print("  [OK] Reconciliation results dispatched to Discord ledger channel.")
    else:
        print(f"  [ERR] Discord dispatch failed: {r.status_code} {r.text}")


if __name__ == "__main__":
    reconcile()
