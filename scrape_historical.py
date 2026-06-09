"""
scrape_historical.py  v3
========================
Exact Action Network flow:
  1. Load page
  2. Click "Odds Settings" -> set state to New Jersey
  3. Select "All Markets" in the bet-type dropdown
  4. Scrape Game (event) period
  5. Click F5 period selector -> scrape firstfive
  6. Click First Inning period selector -> scrape firstinning
  7. Merge all 3 -> render boards

Usage: python scrape_historical.py [YYYYMMDD]
"""

import asyncio, json, sys, subprocess
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

STEALTH_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",
]

BOOK_NAMES = {
    15:"bet365",   30:"DraftKings", 79:"FanDuel",   1368:"BetMGM",
    1963:"Caesars", 1964:"PBT",       1968:"Barstool", 1969:"Unibet",
    2401:"WynnBET", 2988:"ESPN Bet",  4523:"Fanatics",
    # NJ / state-specific books
    68:"BetRivers", 75:"PointsBet",  69:"Unibet",    71:"FoxBet",
    123:"Kindred",  1799:"SuperDraft",4727:"HardRock", 3:"Pinnacle",
    1000:"BetUS",   1865:"BetOnline", 2:"Betway",     100:"Bovada",
}
PERIODS = {"event":"GAME", "firstfive":"FIRST 5", "firstinning":"FIRST INN"}

# ── Parser ─────────────────────────────────────────────────────────────────────

def parse_game(g):
    teams  = {t["id"]: t for t in g.get("teams", [])}
    away   = teams.get(g["away_team_id"], {}).get("abbr", "?")
    home   = teams.get(g["home_team_id"], {}).get("abbr", "?")
    start  = g.get("start_time", "")[:16].replace("T", " ")
    status = g.get("status_display") or g.get("status") or ""
    period_data = {p: {} for p in PERIODS}

    for book_id_str, periods_dict in g.get("markets", {}).items():
        if not isinstance(periods_dict, dict): continue
        book_id   = int(book_id_str)
        book_name = BOOK_NAMES.get(book_id, f"Book:{book_id}")
        for period_key, market_types in periods_dict.items():
            if period_key not in period_data or not isinstance(market_types, dict): continue
            if book_id not in period_data[period_key]:
                period_data[period_key][book_id] = {
                    "book_name": book_name,
                    "ml_away": None, "ml_home": None,
                    "spread_away_val": None, "spread_away_odds": None,
                    "spread_home_val": None, "spread_home_odds": None,
                    "total_val": None,
                    "over_odds": None, "over_tickets": None, "over_money": None,
                    "under_odds": None, "under_tickets": None, "under_money": None,
                    "ml_away_tickets": None, "ml_away_money": None,
                    "ml_home_tickets": None, "ml_home_money": None,
                }
            e = period_data[period_key][book_id]
            for mkt_type, outcomes in market_types.items():
                if mkt_type not in ("moneyline","spread","total"): continue
                if not isinstance(outcomes, list): continue
                for o in outcomes:
                    if not isinstance(o, dict): continue
                    side    = o.get("side"); odds = o.get("odds"); value = o.get("value")
                    tickets = (o.get("bet_info") or {}).get("tickets", {}).get("percent")
                    money   = (o.get("bet_info") or {}).get("money",   {}).get("percent")
                    is_live = o.get("is_live", False)
                    if mkt_type == "moneyline":
                        if side == "away" and (not is_live or e["ml_away"] is None):
                            e["ml_away"] = odds; e["ml_away_tickets"] = tickets; e["ml_away_money"] = money
                        elif side == "home" and (not is_live or e["ml_home"] is None):
                            e["ml_home"] = odds; e["ml_home_tickets"] = tickets; e["ml_home_money"] = money
                    elif mkt_type == "spread":
                        if side == "away" and (not is_live or e["spread_away_val"] is None):
                            e["spread_away_val"] = value; e["spread_away_odds"] = odds
                        elif side == "home" and (not is_live or e["spread_home_val"] is None):
                            e["spread_home_val"] = value; e["spread_home_odds"] = odds
                    elif mkt_type == "total":
                        e["total_val"] = value
                        if side == "over" and (not is_live or e["over_odds"] is None):
                            e["over_odds"] = odds; e["over_tickets"] = tickets; e["over_money"] = money
                        elif side == "under" and (not is_live or e["under_odds"] is None):
                            e["under_odds"] = odds; e["under_tickets"] = tickets; e["under_money"] = money
    return {"away": away, "home": home, "start": start, "status": status, "period_data": period_data}

# ── Merge helper ───────────────────────────────────────────────────────────────

def merge_response(game_index, resp_data, force_period=None):
    """Merge an API response into game_index, optionally forcing a period key."""
    for g in resp_data.get("games", []):
        gid = g["id"]
        if gid not in game_index: continue
        base_mkts = game_index[gid].setdefault("markets", {})
        for bid, periods in g.get("markets", {}).items():
            base_mkts.setdefault(bid, {})
            if isinstance(periods, dict):
                for period, mkt in periods.items():
                    store_key = force_period if force_period else period
                    if store_key not in base_mkts[bid]:
                        base_mkts[bid][store_key] = mkt
        game_index[gid]["markets"] = base_mkts

# ── Scrape ─────────────────────────────────────────────────────────────────────

async def scrape(date_str):
    dt  = datetime.strptime(date_str, "%Y%m%d")
    url = f"https://www.actionnetwork.com/mlb/odds?date={dt.strftime('%Y-%m-%d')}"
    print(f"\n  URL: {url}")

    # We'll do 3 separate captures with explicit period labels
    responses = {"event": None, "firstfive": None, "firstinning": None}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=STEALTH_ARGS)
        ctx = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
            locale="en-US",
        )
        await ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
        )
        page = await ctx.new_page()

        # ── Step 1: Load page ─────────────────────────────────────────────────
        print(f"\n  [1] Loading page...")
        
        # Capture the first API response
        async def capture_one(route):
            r = await route.fetch()
            if "scoreboard/mlb" in route.request.url and r.status == 200:
                try:
                    body = await r.json()
                    if responses["event"] is None:
                        responses["event"] = body
                        print(f"  [EVENT] Captured  {route.request.url[50:90]}")
                except: pass
            await route.fulfill(response=r)

        await ctx.route("**/scoreboard/mlb**", capture_one)
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(6000)
        await ctx.unroute("**/scoreboard/mlb**")

        # Save initial screenshot
        await page.screenshot(path="an_debug_1_initial.png")
        print(f"  [DEBUG] an_debug_1_initial.png")

        # ── Step 2: Click "Odds Settings" -> set New Jersey ───────────────────
        print(f"\n  [2] Setting Odds Settings -> New Jersey...")
        try:
            odds_btn = page.get_by_text("Odds Settings", exact=False)
            if await odds_btn.count() > 0:
                await odds_btn.first.click(timeout=3000)
                await page.wait_for_timeout(1500)
                print(f"    Clicked 'Odds Settings'")
                await page.screenshot(path="an_debug_2_odds_settings.png")
                print(f"    [DEBUG] an_debug_2_odds_settings.png")

                # Find state selector inside the settings panel
                nj_found = False
                # Try select element first
                for sel in await page.query_selector_all("select"):
                    opts = await sel.query_selector_all("option")
                    for opt in opts:
                        txt = (await opt.inner_text()).strip().lower()
                        if "new jersey" in txt or "nj" == txt:
                            await sel.select_option(value=await opt.get_attribute("value"))
                            print(f"    Set state to New Jersey via <select>")
                            nj_found = True
                            break
                    if nj_found: break

                if not nj_found:
                    nj_el = page.get_by_text("New Jersey", exact=False)
                    if await nj_el.count() > 0:
                        await nj_el.first.click(timeout=2000)
                        print(f"    Set state to New Jersey via click")
                        nj_found = True

                if nj_found:
                    await page.wait_for_timeout(2000)
                    # Close settings if there's a close/apply button
                    for close_text in ["Apply", "Save", "Done", "Close", "×"]:
                        try:
                            el = page.get_by_text(close_text, exact=True)
                            if await el.count() > 0:
                                await el.first.click(timeout=1500)
                                break
                        except: pass
                    await page.wait_for_timeout(2000)
            else:
                print(f"    'Odds Settings' button not found")
        except Exception as e:
            print(f"    Odds Settings error: {e}")

        # ── Step 3: Select "All Markets" in the bet-type dropdown ─────────────
        print(f"\n  [3] Selecting 'All Markets'...")
        all_mkts_found = False
        try:
            for sel in await page.query_selector_all("select"):
                opts = await sel.query_selector_all("option")
                for opt in opts:
                    txt = (await opt.inner_text()).strip().lower()
                    if "all markets" in txt or "all" == txt:
                        await sel.select_option(value=await opt.get_attribute("value"))
                        print(f"    Selected 'All Markets' via <select>")
                        all_mkts_found = True
                        break
                if all_mkts_found: break
        except: pass

        if not all_mkts_found:
            try:
                el = page.get_by_text("All Markets", exact=False)
                if await el.count() > 0:
                    await el.first.click(timeout=2000)
                    print(f"    Clicked 'All Markets'")
                    all_mkts_found = True
            except: pass

        await page.wait_for_timeout(4000)
        await page.screenshot(path="an_debug_3_all_markets.png")
        print(f"  [DEBUG] an_debug_3_all_markets.png")

        # Print all select options on page for debugging
        print(f"\n  [DEBUG] All <select> elements on page:")
        try:
            for i, sel in enumerate(await page.query_selector_all("select")):
                opts = await sel.query_selector_all("option")
                opt_texts = [(await o.inner_text()).strip() for o in opts]
                sel_val = await sel.evaluate("el => el.value")
                print(f"    Select #{i}: value='{sel_val}' options={opt_texts[:8]}")
        except Exception as e:
            print(f"    Error reading selects: {e}")

        # ── Step 4: Capture F5 by selecting it in period dropdown ─────────────
        print(f"\n  [4] Selecting F5 period...")

        async def capture_f5(route):
            r = await route.fetch()
            if "scoreboard/mlb" in route.request.url and r.status == 200:
                try:
                    body = await r.json()
                    if responses["firstfive"] is None:
                        responses["firstfive"] = body
                        print(f"  [F5] Captured  {route.request.url[50:90]}")
                except: pass
            await route.fulfill(response=r)

        await ctx.route("**/scoreboard/mlb**", capture_f5)

        f5_found = False
        # Try selecting F5 from any select
        try:
            for sel in await page.query_selector_all("select"):
                opts = await sel.query_selector_all("option")
                for opt in opts:
                    txt = (await opt.inner_text()).strip().lower()
                    if any(t in txt for t in ["f5", "first 5", "first five", "5 inn"]):
                        await sel.select_option(value=await opt.get_attribute("value"))
                        print(f"    Selected F5 via <select>: '{txt}'")
                        f5_found = True
                        break
                if f5_found: break
        except: pass

        if not f5_found:
            for term in ["F5", "First 5", "First Five", "5 Innings", "First 5 Innings"]:
                try:
                    el = page.get_by_text(term, exact=False)
                    if await el.count() > 0:
                        await el.first.click(timeout=2000)
                        print(f"    Clicked F5: '{term}'")
                        f5_found = True
                        break
                except: pass

        await page.wait_for_timeout(6000)
        await ctx.unroute("**/scoreboard/mlb**")
        await page.screenshot(path="an_debug_4_f5.png")
        print(f"  [DEBUG] an_debug_4_f5.png  |  f5_found={f5_found}")

        # ── Step 5: Capture First Inning ──────────────────────────────────────
        print(f"\n  [5] Selecting First Inning period...")

        async def capture_f1(route):
            r = await route.fetch()
            if "scoreboard/mlb" in route.request.url and r.status == 200:
                try:
                    body = await r.json()
                    if responses["firstinning"] is None:
                        responses["firstinning"] = body
                        print(f"  [F1] Captured  {route.request.url[50:90]}")
                except: pass
            await route.fulfill(response=r)

        await ctx.route("**/scoreboard/mlb**", capture_f1)

        f1_found = False
        try:
            for sel in await page.query_selector_all("select"):
                opts = await sel.query_selector_all("option")
                for opt in opts:
                    txt = (await opt.inner_text()).strip().lower()
                    if any(t in txt for t in ["1st inn", "first inn", "first inning", "nrfi", "f1"]):
                        await sel.select_option(value=await opt.get_attribute("value"))
                        print(f"    Selected F1 via <select>: '{txt}'")
                        f1_found = True
                        break
                if f1_found: break
        except: pass

        if not f1_found:
            for term in ["1st Inn", "First Inning", "First Inn", "NRFI", "F1"]:
                try:
                    el = page.get_by_text(term, exact=False)
                    if await el.count() > 0:
                        await el.first.click(timeout=2000)
                        print(f"    Clicked F1: '{term}'")
                        f1_found = True
                        break
                except: pass

        await page.wait_for_timeout(6000)
        await ctx.unroute("**/scoreboard/mlb**")
        await page.screenshot(path="an_debug_5_f1.png")
        print(f"  [DEBUG] an_debug_5_f1.png  |  f1_found={f1_found}")

        await browser.close()

    # ── Build & merge ──────────────────────────────────────────────────────────
    print(f"\n  Responses: event={'YES' if responses['event'] else 'NO'}  "
          f"f5={'YES' if responses['firstfive'] else 'NO'}  "
          f"f1={'YES' if responses['firstinning'] else 'NO'}")

    if not responses["event"]:
        print("  [ERROR] No event data captured."); return None

    base_data  = responses["event"]
    game_index = {g["id"]: g for g in base_data.get("games", [])}

    if responses["firstfive"]:
        merge_response(game_index, responses["firstfive"], force_period="firstfive")
    if responses["firstinning"]:
        merge_response(game_index, responses["firstinning"], force_period="firstinning")

    merged = list(game_index.values())
    parsed = [parse_game(g) for g in merged]
    counts = {p: sum(1 for pg in parsed if pg["period_data"].get(p)) for p in PERIODS}
    print(f"  Period coverage: {counts}")

    out_file = f"action_network_{date_str}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"raw": base_data, "parsed": parsed}, f, indent=2, default=str)
    print(f"  [SAVED] {out_file}  ({len(parsed)} games)")
    return out_file, date_str

# ── Main ───────────────────────────────────────────────────────────────────────

async def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else "20260605"
    result = await scrape(date_str)
    if result:
        _, ds = result
        print(f"\n  Generating boards...")
        subprocess.run(["python", "generate_mlb_odds_board.py", ds], check=True)

if __name__ == "__main__":
    asyncio.run(main())
