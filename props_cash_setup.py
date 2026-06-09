"""
props_cash_setup.py
===================
One-time props.cash login helper.

Run this ONCE in a visible browser, log in manually to props.cash,
then the session is saved to props_session.json for all future headless runs.

Usage:
  python props_cash_setup.py
"""

import asyncio, json, os
from pathlib import Path
from playwright.async_api import async_playwright

PROPS_CASH_URL = "https://www.props.cash/"
SESSION_FILE  = Path("props_session.json")
# Your real Chrome profile — already has Google signed in
CHROME_USER_DATA = Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data"

async def setup():
    print("\n=== props.cash Session Setup ===")
    print(f"Using Chrome profile: {CHROME_USER_DATA}")
    print("A browser window will open using your real Chrome.")
    print("Log into your props.cash account, then press Enter here.\n")

    async with async_playwright() as pw:
        # Use persistent context with your real Chrome profile
        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=str(CHROME_USER_DATA),
            headless=False,
            channel="chrome",          # use installed Chrome
            args=["--no-sandbox", "--start-maximized"],
            viewport={"width": 1440, "height": 900},
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        # Go directly to props.cash
        await page.goto(PROPS_CASH_URL, timeout=30000)
        print("Navigate to the app / log in. Press Enter here when you are logged in and the app dashboard is visible.")
        input()

        # Save session state
        storage = await ctx.storage_state()
        SESSION_FILE.write_text(json.dumps(storage, indent=2))
        print(f"\nSession saved -> {SESSION_FILE}")

        # Take a test screenshot
        print("Taking test screenshot...")
        await page.wait_for_timeout(3000)
        screenshot = await page.screenshot(type="png")
        Path("props_session_test.png").write_bytes(screenshot)
        print(f"Test screenshot saved -> props_session_test.png")
        print("\nSetup complete. You can now run the discover/scraper scripts.")

        await ctx.close()

if __name__ == "__main__":
    asyncio.run(setup())
