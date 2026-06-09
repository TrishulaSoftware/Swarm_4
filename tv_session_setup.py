"""
tv_session_setup.py
===================
One-time TradingView login helper.

Run this ONCE in a visible browser, log in manually (including 2FA),
then the session is saved to tv_session.json for all future headless runs.

Usage:
  python tv_session_setup.py
"""

import asyncio, json, os
from pathlib import Path
from playwright.async_api import async_playwright

TV_CHART_URL  = "https://www.tradingview.com/chart/NR3yo9nj/?symbol=AMEX%3ASPY"
SESSION_FILE  = Path("tv_session.json")
# Your real Chrome profile — already has Google signed in
CHROME_USER_DATA = Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data"

async def setup():
    print("\n=== TradingView Session Setup ===")
    print(f"Using Chrome profile: {CHROME_USER_DATA}")
    print("A browser window will open using your real Chrome.")
    print("Navigate to TradingView if needed, then come back and press Enter.\n")

    async with async_playwright() as pw:
        # Use persistent context with your real Chrome profile
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=str(CHROME_USER_DATA),
            headless=False,
            channel="chrome",          # use installed Chrome, not test browser
            args=["--no-sandbox", "--start-maximized"],
            viewport={"width": 1440, "height": 900},
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        # Go directly to the chart
        await page.goto(TV_CHART_URL, timeout=30000)
        print("Chart loading... Log in if prompted, then press Enter here when chart is visible.")
        input()

        # Save session state
        storage = await ctx.storage_state()
        SESSION_FILE.write_text(json.dumps(storage, indent=2))
        print(f"\nSession saved -> {SESSION_FILE}")

        # Test screenshot
        print("Taking test screenshot...")
        await page.wait_for_timeout(3000)
        screenshot = await page.screenshot(type="png")
        Path("tv_session_test.png").write_bytes(screenshot)
        print(f"Test screenshot -> tv_session_test.png")
        print("\nSetup complete. Run: python starfall_relay.py --test")

        await ctx.close()

if __name__ == "__main__":
    asyncio.run(setup())
