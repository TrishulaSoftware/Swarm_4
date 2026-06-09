import json, asyncio
from pathlib import Path
from playwright.async_api import async_playwright

SAMESITE_MAP = {'no_restriction': 'None', 'lax': 'Lax', 'strict': 'Strict', None: 'None'}

raw = json.loads(Path('tv_cookies_raw.json').read_text())
cookies = []
for c in raw:
    cookies.append({
        'name':     c['name'],
        'value':    c['value'],
        'domain':   c['domain'],
        'path':     c.get('path', '/'),
        'expires':  int(c['expirationDate']) if c.get('expirationDate') else -1,
        'httpOnly': c.get('httpOnly', False),
        'secure':   c.get('secure', False),
        'sameSite': SAMESITE_MAP.get(c.get('sameSite'), 'None'),
    })

storage = {'cookies': cookies, 'origins': []}
Path('tv_session.json').write_text(json.dumps(storage, indent=2))
print(f'Converted {len(cookies)} cookies -> tv_session.json')

async def test():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=['--no-sandbox'])
        ctx = await browser.new_context(
            viewport={'width': 1440, 'height': 900},
            storage_state='tv_session.json'
        )
        page = await ctx.new_page()
        print('Loading chart with session cookies...')
        await page.goto(
            'https://www.tradingview.com/chart/NR3yo9nj/?symbol=AMEX%3ASPY',
            wait_until='domcontentloaded',
            timeout=45000
        )
        await page.wait_for_timeout(10000)
        b = await page.screenshot(type='png')
        Path('tv_session_test.png').write_bytes(b)
        print(f'Done: {len(b):,} bytes -> tv_session_test.png')
        await browser.close()

asyncio.run(test())
