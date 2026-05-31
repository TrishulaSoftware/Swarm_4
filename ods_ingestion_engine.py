# -*- coding: utf-8 -*-
"""
TRISHULA SWARM -- SOVEREIGN ODS INGESTION & SCREENSHOT PARSING ENGINE
Description: Parses the four ODS files, extracts screenshots, uses Gemini Multimodal Vision API
             to parse full boards without curation, generates dynamic slates, and initializes ledgers.
Issued: 2026-05-20 | Author: Antigravity / War Machine
"""

import os
import re
import sys
import json
import base64
import zipfile
import requests
from datetime import datetime, date

# ============================================================
# Core Paths & Environment Ingestion
# ============================================================
SWARM_ROOT = r"H:\Trishula\Swarm_4_Integration"
SALVO_STAGING = os.path.join(SWARM_ROOT, "Salvo_Staging")
ENV_PATH = os.path.join(SWARM_ROOT, ".env")

# Default API Key fallback, but we read from .env primarily
GEMINI_API_KEY = None
if os.path.exists(ENV_PATH):
    with open(ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip().startswith("GEMINI_API_KEY="):
                GEMINI_API_KEY = line.split("=", 1)[1].strip()

if not GEMINI_API_KEY:
    print("[ERR] GEMINI_API_KEY not found in workspace .env file.")
    sys.exit(1)

# ============================================================
# ZIP ODS Image Extractor
# ============================================================
def extract_ods_images(ods_path, output_dir, file_prefix):
    """
    ODS files are ZIP containers. All embedded images are located under Pictures/
    """
    if not os.path.exists(ods_path):
        print(f"[WARN] ODS file not found: {ods_path}")
        return []

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    extracted_files = []
    try:
        with zipfile.ZipFile(ods_path, 'r') as zip_ref:
            for file_info in zip_ref.infolist():
                if file_info.filename.startswith("Pictures/") and not file_info.filename.endswith("/"):
                    # Read image binary data
                    img_data = zip_ref.read(file_info.filename)
                    ext = os.path.splitext(file_info.filename)[1] or ".png"
                    
                    # Create clean, unique file names
                    clean_name = f"{file_prefix}_{os.path.basename(file_info.filename)}"
                    dest_path = os.path.join(output_dir, clean_name)
                    
                    with open(dest_path, "wb") as f:
                        f.write(img_data)
                    extracted_files.append(dest_path)
        print(f"[OK] Extracted {len(extracted_files)} screenshots from {os.path.basename(ods_path)}")
    except Exception as e:
        print(f"[ERR] Failed to extract from {ods_path}: {e}")
    
    return sorted(extracted_files)

# ============================================================
# Multimodal Ingestion via Gemini REST API
# ============================================================
def parse_image_with_gemini(image_path, system_prompt, schema_description):
    """
    Sends local screenshot to Gemini Multimodal Vision REST API to parse structured JSON.
    """
    print(f"  [AI] Querying Gemini for screenshot: {os.path.basename(image_path)}...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    try:
        with open(image_path, "rb") as f:
            base64_image = base64.b64encode(f.read()).decode("utf-8")
            
        payload = {
            "contents": [{
                "parts": [
                    {"text": f"{system_prompt}\nFormat the output strictly according to this schema:\n{schema_description}"},
                    {
                        "inlineData": {
                            "mimeType": "image/png",
                            "data": base64_image
                        }
                    }
                ]
            }],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }
        
        headers = {"Content-Type": "application/json"}
        r = requests.post(url, headers=headers, json=payload, timeout=90)
        
        if r.status_code == 200:
            res_json = r.json()
            # Extract generated text block
            text_content = res_json["candidates"][0]["content"]["parts"][0]["text"]
            # Clean possible markdown wrap ```json
            cleaned_text = re.sub(r"^```json\s*|\s*```$", "", text_content.strip(), flags=re.MULTILINE)
            return json.loads(cleaned_text)
        else:
            print(f"  [ERR] Gemini API Error: {r.status_code} - {r.text}")
            return None
    except Exception as e:
        print(f"  [ERR] Exception during image parse: {e}")
        return None

# ============================================================
# Main Processing Core
# ============================================================
def run_ingestion(target_date_str=None):
    """
    Runs full pipeline for target date (format: MM_DD_YYYY).
    Defaults to current local date if not specified.
    """
    if not target_date_str:
        target_date_str = datetime.now().strftime("%m_%d_%Y")

    print("\n" + "="*60)
    print(f" TRISHULA AUTOMATED FULL-GAMUT INGESTION ENGINE")
    print(f" Active Date Target: {target_date_str}")
    print("="*60 + "\n")

    datemine_dir = fr"H:\Trishula_SBM\DataMine\MLB\Team Props\{target_date_str}"
    extracted_dir = os.path.join(datemine_dir, "extracted_images")

    if not os.path.exists(datemine_dir):
        os.makedirs(datemine_dir)

    # 1. Image Extraction from ODS Files
    team_main_ods = os.path.join(datemine_dir, "team main template.ods")
    player_bat_ods = os.path.join(datemine_dir, "player batting template.ods")
    player_alt_bat_ods = os.path.join(datemine_dir, "player alternate batting template.ods")
    player_pit_ods = os.path.join(datemine_dir, "player pitching template.ods")

    team_images = extract_ods_images(team_main_ods, extracted_dir, "team_main")
    bat_images = extract_ods_images(player_bat_ods, extracted_dir, "player_batting")
    alt_bat_images = extract_ods_images(player_alt_bat_ods, extracted_dir, "player_alt_batting")
    pit_images = extract_ods_images(player_pit_ods, extracted_dir, "player_pitching")

    # 2. Schema Definitions & Prompts
    team_schema = """
    {
      "BASE_GAMES": [
        {
          "away": "Away team 3-letter code (e.g. BAL)",
          "awayFull": "Away team full name (e.g. Baltimore Orioles)",
          "home": "Home team 3-letter code (e.g. TB)",
          "homeFull": "Home team full name (e.g. Tampa Bay Rays)",
          "awaySpread": "Away spread value (e.g. +1.5)",
          "awayML": "Away moneyline odds (e.g. +108)",
          "homeSpread": "Home spread value (e.g. -1.5)",
          "homeML": "Home moneyline odds (e.g. -120)",
          "total": "Total line description (e.g. o7.5 / u7.5)",
          "awayStreak": "Away team win/loss streak (e.g. W2)",
          "homeStreak": "Home team win/loss streak (e.g. L1)",
          "hfAdv": "Homefield advantage rating (e.g. TB +0.5 Runs)",
          "h2h": "H2H split details (e.g. TB 6-4 L10)",
          "pick": "Specific pick text (e.g. TB +0.5 F5 Spread)",
          "pickType": "Standardized Pick Type (e.g. F5 Run Line (+0.5))",
          "confidence": "Confidence percentage (e.g. 100%)",
          "rationale": "High-EV mathematical rationale"
        }
      ],
      "ALT_GAMES": [
        {
          "away": "BAL",
          "home": "TB",
          "f5awayML": "F5 Away ML odds (e.g. +108)",
          "f5homeML": "F5 Home ML odds (e.g. -160)",
          "firstInning": "1st Inning Line (e.g. o0.5 / u0.5)",
          "pitcherEdge": "Pitcher edge notes (e.g. TB F5 Dominance)",
          "weather": "Weather/dome notes (e.g. Dome or Clear)",
          "pick": "Specific pick selection text",
          "pickType": "Pick type name",
          "confidence": "Confidence percentage",
          "rationale": "Edge validation analysis"
        }
      ]
    }
    """
    
    player_schema = """
    {
      "BATTING_PROPS": [
        {
          "player": "Player Full Name",
          "team": "Team code (e.g. PHI)",
          "opp": "Opponent code (e.g. CIN)",
          "prop": "Prop type (e.g. Hits, Runs, H+R+RBI, Total Bases)",
          "line": "Line threshold (e.g. o0.5, o1.5)",
          "odds": "Line odds (e.g. -242)",
          "matchupEdge": "Matchup edge text (e.g. 9-game hit streak)",
          "streak": "Current active streak length (e.g. 9)",
          "pick": "Pick direction (e.g. OVER 0.5)",
          "confidence": "Confidence value (e.g. 95%)",
          "rationale": "Audit trend rationale"
        }
      ],
      "PITCHING_PROPS": [
        {
          "player": "Pitcher Name",
          "team": "Team code",
          "opp": "Opponent code",
          "prop": "Prop category (e.g. Strikeouts, Pitcher Outs, Earned Runs, Hits Allowed)",
          "line": "Line threshold (e.g. o5.5, o16.5)",
          "odds": "Odds value",
          "matchupEdge": "Streak matchup context",
          "streak": "Streak number",
          "pick": "Direction (e.g. OVER 16.5)",
          "confidence": "Confidence percentage",
          "rationale": "High-EV rationale description"
        }
      ],
      "ALT_BATTING_PROPS": [
        {
          "player": "Player Name",
          "team": "Team code",
          "opp": "Opponent code",
          "prop": "Alt prop category",
          "line": "Line",
          "odds": "Odds",
          "matchupEdge": "Alt streak edge details",
          "streak": "Streak count",
          "pick": "Direction",
          "confidence": "Confidence",
          "rationale": "Rationale details"
        }
      ]
    }
    """

    # 3. Parse Team Screenshots
    all_base_games = []
    all_alt_games = []
    
    if team_images:
        print("[PROCESS] Parsing Team Main Screenshots...")
        for img in team_images:
            parsed = parse_image_with_gemini(
                img, 
                "Extract all MLB game props, first inning lines, and F5 lines from this spreadsheet screenshot. Do not filter out any match-ups; extract everything visible.",
                team_schema
            )
            if parsed:
                all_base_games.extend(parsed.get("BASE_GAMES", []))
                all_alt_games.extend(parsed.get("ALT_GAMES", []))
                
        # Write slate output
        slate_file = os.path.join(datemine_dir, f"slate_{target_date_str}.json")
        with open(slate_file, "w", encoding="utf-8") as f:
            json.dump({"BASE_GAMES": all_base_games, "ALT_GAMES": all_alt_games}, f, indent=4)
        print(f"[OK] Saved dynamically parsed Team Slate: {slate_file} ({len(all_base_games)} Base, {len(all_alt_games)} Alt)")

    # 4. Parse Player Screenshots
    all_batting = []
    all_pitching = []
    all_alt_batting = []
    
    if bat_images or alt_bat_images or pit_images:
        print("[PROCESS] Parsing Player Props Screenshots...")
        
        # Standard Batting
        for img in bat_images:
            parsed = parse_image_with_gemini(
                img,
                "Extract EVERY single MLB player batting prop (Hits, Runs, H+R+RBI, Total Bases) row visible on this screenshot, without exception. Do NOT filter, skip, or select only high-probability, high-confidence, or active streak players. If a player name and prop row is visible on the image, extract it in full and include it in the output.",
                player_schema
            )
            if parsed:
                all_batting.extend(parsed.get("BATTING_PROPS", []))
                
        # Alternate Batting (Cheatsheet / Streaks)
        for img in alt_bat_images:
            parsed = parse_image_with_gemini(
                img,
                "Extract EVERY single MLB alternate batting streak cheatsheet player row visible on this screenshot, without exception. Do NOT filter, skip, or select only high-probability, high-confidence, or active streak players. If a player name and prop row is visible on the image, extract it in full and include it in the output.",
                player_schema
            )
            if parsed:
                all_alt_batting.extend(parsed.get("ALT_BATTING_PROPS", []))
                # Add to batting if they fit batting props
                for p in parsed.get("BATTING_PROPS", []):
                    if p not in all_batting:
                        all_batting.append(p)
                        
        # Pitching
        for img in pit_images:
            parsed = parse_image_with_gemini(
                img,
                "Extract EVERY single MLB pitcher prop (Strikeouts, Pitcher Outs, Earned Runs, Hits Allowed) row visible on this screenshot, without exception. Do NOT filter, skip, or select only high-probability, high-confidence, or active streak pitchers. If a pitcher name and prop row is visible on the image, extract it in full and include it in the output.",
                player_schema
            )
            if parsed:
                all_pitching.extend(parsed.get("PITCHING_PROPS", []))

        # Write player slate output
        player_slate_file = os.path.join(datemine_dir, f"player_slate_{target_date_str}.json")
        with open(player_slate_file, "w", encoding="utf-8") as f:
            json.dump({
                "BATTING_PROPS": all_batting, 
                "PITCHING_PROPS": all_pitching, 
                "ALT_BATTING_PROPS": all_alt_batting
            }, f, indent=4)
        print(f"[OK] Saved dynamically parsed Player Slate: {player_slate_file} ({len(all_batting)} Batting, {len(all_pitching)} Pitching, {len(all_alt_batting)} Alt Batting)")

    # 5. Initialize Daily Ledger
    print("[PROCESS] Initializing Master Ledger...")
    # Change working dir to Salvo_Staging to run import modules cleanly
    old_cwd = os.getcwd()
    try:
        os.chdir(SALVO_STAGING)
        sys.path.insert(0, SALVO_STAGING)
        
        # Import ledger creator dynamically to parse today's JSON slates
        import ledger_manager
        
        # Force RAW_DATE to today's active target so ledger matches target date
        ledger_manager.RAW_DATE = target_date_str
        ledger_manager.LEDGER_DIR = datemine_dir
        ledger_manager.LEDGER_FILE = os.path.join(datemine_dir, f"ledger_{target_date_str}.json")
        ledger_manager.SLATE_DATE = datetime.strptime(target_date_str, "%m_%d_%Y").strftime("%B %d, %Y")
        
        ledger_data = ledger_manager.create_ledger()
        ledger_manager.dispatch_ledger_embed(ledger_data)
        print(f"[OK] Master Ledger successfully initialized for {target_date_str}.")
        
    except Exception as e:
        print(f"[ERR] Failed to initialize daily ledger: {e}")
    finally:
        os.chdir(old_cwd)

    print("\n" + "="*60)
    print(" [COMPLETED] TRISHULA INGESTION & LEDGER SETUP COMPLETE")
    print("="*60 + "\n")

if __name__ == "__main__":
    # Check if target date passed via CLI args
    target_date = sys.argv[1] if len(sys.argv) > 1 else None
    run_ingestion(target_date)
