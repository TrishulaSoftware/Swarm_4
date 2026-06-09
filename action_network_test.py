"""
action_network_test.py  v2
===========================
Playwright scraper for actionnetwork.com/mlb/odds
- Single API call returns ALL three market periods
- Filters by period: event | firstfive | firstinning
- Shows: ML, Spread, O/U + Public Tickets % + Sharp Money %
- NO Discord relay - console output only

Run: python action_network_test.py
"""

import asyncio, json
from datetime import date
from playwright.async_api import async_playwright

TARGET_URL = "https://www.actionnetwork.com/mlb/odds"
DATE_STR   = date.today().strftime("%Y%m%d")

STEALTH_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",
]

# Known Action Network book IDs
BOOK_NAMES = {
    15:   "bet365",
    30:   "DraftKings",
    79:   "FanDuel",
    1368: "BetMGM",
    1963: "Caesars",
    1964: "PointsBet",
    1968: "Barstool",
    1969: "Unibet",
    2401: "WynnBET",
    2988: "ESPN Bet",
    4523: "Fanatics",
}

PERIODS = {
    "event":       "GAME    ",
    "firstfive":   "FIRST 5 ",
    "firstinning": "FIRST 1 ",
}

def fmt_odds(o):
    if o is None:
        return "  N/A"
    return f"{int(o):+d}" if o else "  N/A"

def fmt_pct(p):
    if p is None or p == 0:
        return " -- "
    return f"{int(p):>3}%"


def parse_game(g: dict) -> dict:
    """Extract team info, then parse markets by period.
    Structure: markets[book_id][period_name][market_type] = list of outcomes
    Periods: 'event' | 'firstfive' | 'firstinning'
    """
    teams_list = g.get("teams", [])
    away_id    = g.get("away_team_id")
    home_id    = g.get("home_team_id")

    teams_map  = {t["id"]: t for t in teams_list}
    away_abbr  = teams_map.get(away_id, {}).get("abbr") or f"ID:{away_id}"
    home_abbr  = teams_map.get(home_id, {}).get("abbr") or f"ID:{home_id}"
    start      = g.get("start_time", "")[:16].replace("T", " ")
    status     = g.get("status_display") or g.get("status") or ""

    raw_markets = g.get("markets", {})
    period_data = {p: {} for p in PERIODS}

    for book_id_str, periods_dict in raw_markets.items():
        if not isinstance(periods_dict, dict):
            continue
        book_id   = int(book_id_str)
        book_name = BOOK_NAMES.get(book_id, f"Book:{book_id}")

        # periods_dict = { "event": {...}, "firstfive": {...}, "firstinning": {...} }
        for period_key, market_types in periods_dict.items():
            if period_key not in period_data or not isinstance(market_types, dict):
                continue

            if book_id not in period_data[period_key]:
                period_data[period_key][book_id] = {
                    "book_name":       book_name,
                    "ml_away":         None, "ml_away_tickets": None, "ml_away_money": None,
                    "ml_home":         None, "ml_home_tickets": None, "ml_home_money": None,
                    "spread_away_val": None, "spread_away_odds": None,
                    "spread_home_val": None, "spread_home_odds": None,
                    "spread_tickets":  None, "spread_money":     None,
                    "total_val":       None,
                    "over_odds":       None, "over_tickets":    None, "over_money":  None,
                    "under_odds":      None, "under_tickets":   None, "under_money": None,
                }

            entry = period_data[period_key][book_id]

            for mkt_type, outcomes in market_types.items():
                if mkt_type not in ("moneyline", "spread", "total"):
                    continue
                if not isinstance(outcomes, list):
                    continue

                for o in outcomes:
                    if not isinstance(o, dict):
                        continue
                    side    = o.get("side")
                    odds    = o.get("odds")
                    value   = o.get("value")
                    tickets = (o.get("bet_info") or {}).get("tickets", {}).get("percent")
                    money   = (o.get("bet_info") or {}).get("money",   {}).get("percent")
                    is_live = o.get("is_live", False)

                    # Prefer pre-game lines; fall back to live if nothing else
                    if mkt_type == "moneyline":
                        if side == "away" and (not is_live or entry["ml_away"] is None):
                            entry["ml_away"]         = odds
                            entry["ml_away_tickets"] = tickets
                            entry["ml_away_money"]   = money
                        elif side == "home" and (not is_live or entry["ml_home"] is None):
                            entry["ml_home"]         = odds
                            entry["ml_home_tickets"] = tickets
                            entry["ml_home_money"]   = money

                    elif mkt_type == "spread":
                        if side == "away" and (not is_live or entry["spread_away_val"] is None):
                            entry["spread_away_val"]  = value
                            entry["spread_away_odds"] = odds
                            entry["spread_tickets"]   = tickets
                        elif side == "home" and (not is_live or entry["spread_home_val"] is None):
                            entry["spread_home_val"]  = value
                            entry["spread_home_odds"] = odds

                    elif mkt_type == "total":
                        entry["total_val"] = value
                        if side == "over" and (not is_live or entry["over_odds"] is None):
                            entry["over_odds"]    = odds
                            entry["over_tickets"] = tickets
                            entry["over_money"]   = money
                        elif side == "under" and (not is_live or entry["under_odds"] is None):
                            entry["under_odds"]    = odds
                            entry["under_tickets"] = tickets
                            entry["under_money"]   = money

    return {
        "away":        away_abbr,
        "home":        home_abbr,
        "start":       start,
        "status":      status,
        "period_data": period_data,
    }


def print_game_summary(parsed: dict):
    away   = parsed["away"]
    home   = parsed["home"]
    start  = parsed["start"]
    status = parsed["status"]

    print(f"\n  {'='*68}")
    print(f"  {away} @ {home}  |  {start}  |  {status}")
    print(f"  {'='*68}")

    for period_key, period_label in PERIODS.items():
        books = parsed["period_data"].get(period_key, {})
        if not books:
            continue

        print(f"\n  -- [{period_label}] --")
        print(f"  {'BOOK':<14}  {'ML AWAY':>8}  {'ML HOME':>8}  "
              f"{'SPREAD':>7}  {'SPD ODDS':>8}  "
              f"{'TOTAL':>6}  {'OVER':>6}  {'UNDER':>6}  "
              f"{'TKT%':>5}  {'MNY%':>5}")
        print(f"  {'-'*100}")

        for book_id, b in books.items():
            spread_str = (f"{b['spread_away_val']:+.1f}" if b["spread_away_val"] is not None else "  ---")
            total_str  = (f"{b['total_val']:.1f}"         if b["total_val"]       is not None else " ---")

            # Public consensus (away ML direction)
            tkt = fmt_pct(b["ml_away_tickets"])
            mny = fmt_pct(b["ml_away_money"])

            print(f"  {b['book_name']:<14}  "
                  f"{fmt_odds(b['ml_away']):>8}  {fmt_odds(b['ml_home']):>8}  "
                  f"{spread_str:>7}  {fmt_odds(b['spread_away_odds']):>8}  "
                  f"{total_str:>6}  {fmt_odds(b['over_odds']):>6}  {fmt_odds(b['under_odds']):>6}  "
                  f"{tkt:>5}  {mny:>5}")


async def run():
    print(f"\n{'='*72}")
    print(f"  ACTION NETWORK MLB ODDS  |  {date.today().strftime('%A %B %d, %Y')}")
    print(f"  Markets: GAME  |  FIRST 5 INNINGS  |  FIRST INNING")
    print(f"{'='*72}\n")

    all_api_responses = []
    captured_api_url  = {}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=STEALTH_ARGS)
        ctx = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        await ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        page = await ctx.new_page()

        # ── Persistent route interceptor — captures ALL market API calls ──────
        async def intercept_route(route):
            url = route.request.url
            response = await route.fetch()
            if "scoreboard/mlb" in url and response.status == 200:
                try:
                    body = await response.json()
                    all_api_responses.append({"url": url, "data": body})
                    captured_api_url["url"] = url
                    print(f"  [INTERCEPTED] {url[:88]}")
                except Exception as e:
                    print(f"  [INTERCEPT ERR] {e}")
            await route.fulfill(response=response)

        await ctx.route("**/scoreboard/mlb**", intercept_route)

        # ── STEP 1: Load page — captures GAME (event) data ───────────────────
        print(f"  Loading page (Game market)...")
        await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(8000)

        # ── STEP 2: Take screenshot to inspect dropdown structure ─────────────
        await page.screenshot(path="action_network_page.png", full_page=False)
        print(f"  [SCREENSHOT] action_network_page.png saved")

        # ── STEP 3: Find All Markets dropdown and click each market ──────────
        market_targets = [
            {"label": "First 5 Innings", "terms": ["first 5", "first five", "5 innings", "first 5 innings"]},
            {"label": "First Inning",    "terms": ["first inning", "1st inning", "first inn"]},
        ]

        for mkt in market_targets:
            print(f"\n  Selecting: {mkt['label']}...")
            clicked = False

            # First open the dropdown — find "All Markets" button and click it
            try:
                dropdown_triggers = [
                    "All Markets", "Markets", "Game Odds", "Select Market"
                ]
                for trigger in dropdown_triggers:
                    try:
                        el = page.get_by_text(trigger, exact=False)
                        if await el.count() > 0:
                            await el.first.click(timeout=2000)
                            await page.wait_for_timeout(800)
                            print(f"    Opened dropdown via: '{trigger}'")
                            break
                    except Exception:
                        pass
            except Exception:
                pass

            # Now find and click the specific market option
            for term in mkt["terms"]:
                try:
                    el = page.get_by_text(term, exact=False)
                    if await el.count() > 0:
                        await el.first.click(timeout=3000)
                        clicked = True
                        print(f"    Clicked market: '{term}'")
                        break
                except Exception:
                    pass

            if not clicked:
                # Brute force — check all interactive elements
                try:
                    els = await page.query_selector_all(
                        "button, [role='option'], [role='menuitem'], [role='tab'], li, span, div"
                    )
                    for el in els:
                        try:
                            txt = (await el.inner_text()).strip().lower()
                            if any(t in txt for t in mkt["terms"]) and len(txt) < 30:
                                await el.scroll_into_view_if_needed()
                                await el.click(timeout=2000)
                                clicked = True
                                print(f"    Clicked via brute force: '{txt}'")
                                break
                        except Exception:
                            continue
                except Exception as e:
                    print(f"    Brute force failed: {e}")

            if not clicked:
                print(f"    [INFO] '{mkt['label']}' not found — likely opens closer to game time")

            await page.wait_for_timeout(5000)   # wait for API response

        await ctx.unroute("**/scoreboard/mlb**")
        await browser.close()

    # ── Merge all captured API responses ─────────────────────────────────────
    print(f"\n  Total API responses captured: {len(all_api_responses)}")

    if not all_api_responses:
        print("  [ERROR] No scoreboard API data captured.")
        return

    base_data  = all_api_responses[0]["data"]
    games_raw  = base_data.get("games", [])
    game_index = {g["id"]: g for g in games_raw}

    for resp in all_api_responses[1:]:
        for g in resp["data"].get("games", []):
            gid = g["id"]
            if gid not in game_index:
                continue
            base_mkts = game_index[gid].get("markets", {})
            for book_id, periods in g.get("markets", {}).items():
                if book_id not in base_mkts:
                    base_mkts[book_id] = {}
                if isinstance(periods, dict):
                    for period, mkt_data in periods.items():
                        if period not in base_mkts[book_id]:
                            base_mkts[book_id][period] = mkt_data
            game_index[gid]["markets"] = base_mkts

    merged_games  = list(game_index.values())
    parsed_games  = [parse_game(g) for g in merged_games]

    for pg in parsed_games:
        print_game_summary(pg)

    out = f"action_network_{DATE_STR}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"raw": base_data, "parsed": parsed_games}, f, indent=2, default=str)
    print(f"\n\n  [SAVED] -> {out}")
    print(f"\n{'='*72}")
    print(f"  TEST COMPLETE")
    print(f"{'='*72}\n")


if __name__ == "__main__":
    asyncio.run(run())
