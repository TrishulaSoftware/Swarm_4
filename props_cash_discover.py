"""
props_cash_discover.py
======================
Monitors and logs API requests on props.cash to find how player props are loaded.

Usage:
  python props_cash_discover.py
"""

import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright

TARGET_URL = "https://www.props.cash/"
SESSION_FILE = Path("props_session.json")

STEALTH_ARGS = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-blink-features=AutomationControlled",
]

async def run():
    if not SESSION_FILE.exists():
        print(f"[ERR] Session file not found: {SESSION_FILE} - Run props_cash_setup.py first!")
        return

    print("\n=== props.cash API Discovery Mode ===")
    print("Launching headless browser with saved session...")
    
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=STEALTH_ARGS)
        ctx = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            storage_state=str(SESSION_FILE),
        )
        await ctx.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
        )
        page = await ctx.new_page()

        # Intercept response
        async def handle_response(response):
            url = response.url
            # We are interested in fetch/XHR JSON responses
            if response.status == 200 and ("json" in response.headers.get("content-type", "").lower() or "/api/" in url or "api." in url):
                try:
                    data = await response.json()
                    print(f"\n[API INTERCEPTED] URL: {url}")
                    # Save a sample to inspect
                    sample_name = f"sample_{url.split('/')[-1].split('?')[0] or 'data'}.json"
                    # clean any invalid chars from filename
                    sample_name = "".join([c for c in sample_name if c.isalpha() or c.isdigit() or c in (".", "_", "-")])
                    with open(sample_name, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                    print(f"  -> Sample saved to: {sample_name}")
                except Exception as e:
                    # Not JSON or failed to read
                    pass

        page.on("response", handle_response)

        print(f"Navigating to {TARGET_URL}...")
        await page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=45000)
        
        print("Waiting 15 seconds to let the application load and fetch player prop slates...")
        await page.wait_for_timeout(15000)
        
        # Take a screenshot to verify what we are looking at
        await page.screenshot(path="props_discovery_page.png")
        print("[SCREENSHOT] Saved props_discovery_page.png")
        
        await browser.close()
        print("\n=== Discovery run completed. ===")

if __name__ == "__main__":
    asyncio.run(run())
