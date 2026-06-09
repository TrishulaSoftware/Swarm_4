#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trishula Swarm — Full Pipeline Runner
Paste odds text → parse → generate boards → (optionally) post to Discord.

Usage:
    # From clipboard
    python run_swarm_boards.py --clip

    # From file
    python run_swarm_boards.py --file odds.txt

    # From stdin (pipe)
    cat odds.txt | python run_swarm_boards.py

    # Generate + post to Discord
    python run_swarm_boards.py --clip --discord
"""

import sys, os, json, asyncio, argparse
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
import parse_odds

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

OUTPUT_DIR = Path(r"H:\Trishula\Swarm_4_Integration\Salvo_Staging\swarm_boards")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DATE_STR = datetime.now().strftime('%b %-d, %Y') if sys.platform != 'win32' else datetime.now().strftime('%b %#d, %Y')

# ─── HTML BUILDER ─────────────────────────────────────────────────────────────
def fmt_odds(v):
    if v is None: return '—'
    return f'+{v}' if v > 0 else str(v)

def odds_cls(v):
    if v is None: return 'neg'
    return 'pos' if v > 0 else 'neg'

def market_col_html(mkt, col_label, away, home):
    if mkt is None:
        return f'''
        <div class="col-block">
            <div class="col-header">{col_label}</div>
            <div class="no-lines">— no lines —</div>
        </div>'''

    def row(team, spread, odds, book):
        oc  = odds_cls(odds)
        dot = ' <span class="dot">&#9679;</span>' if (odds is not None and odds > 0) else ''
        return f'''<div class="data-row">
            <span class="team">{team[:4]}</span>
            <span class="spread">{spread}</span>
            <span class="odds {oc}">{fmt_odds(odds)}{dot}</span>
            <span class="book">{book}</span>
        </div>'''

    over_l  = mkt.get('over_line', 0)
    under_l = mkt.get('under_line', 0)
    # Format line display
    ol  = str(int(over_l))  if over_l  == int(over_l or 0)  else str(over_l)
    ul  = str(int(under_l)) if under_l == int(under_l or 0) else str(under_l)

    rows = [
        row(away,  mkt.get('away_rl','?'),   mkt.get('away_rl_odds'), mkt.get('away_rl_book','?')),
        row(home,  mkt.get('home_rl','?'),   mkt.get('home_rl_odds'), mkt.get('home_rl_book','?')),
        row('Over', f"o{ol}",                mkt.get('over_odds'),    mkt.get('over_book','?')),
        row('Undr', f"u{ul}",                mkt.get('under_odds'),   mkt.get('under_book','?')),
        row(away,  'ML',                     mkt.get('ml_away'),      mkt.get('ml_away_book','?')),
        row(home,  'ML',                     mkt.get('ml_home'),      mkt.get('ml_home_book','?')),
    ]
    return f'''
    <div class="col-block">
        <div class="col-header">{col_label}</div>
        {''.join(rows)}
    </div>'''

def game_card_html(game):
    away = game['away']
    home = game['home']
    time = game.get('time', '')
    return f'''
    <div class="game-card">
        <div class="game-header">
            <span class="matchup">{away} @ {home}</span>
            <span class="game-time">{time}</span>
        </div>
        <div class="cols-wrap">
            {market_col_html(game.get('full'), 'FULL GAME', away, home)}
            <div class="col-divider"></div>
            {market_col_html(game.get('f1i'),  'FIRST INNING', away, home)}
            <div class="col-divider"></div>
            {market_col_html(game.get('f5i'),  'FIRST 5 INN', away, home)}
        </div>
    </div>'''

CSS = '''
  @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=Barlow:wght@400;600;700;800;900&display=swap');
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: #0a0a0a;
    font-family: 'Share Tech Mono', 'Courier New', monospace;
    color: #f0f0f0;
    width: 1024px;
    padding: 0;
  }
  .wrapper { background: #0a0a0a; padding: 28px 22px 20px 22px; min-width: 1024px; }
  .board-title {
    font-family: 'Barlow', sans-serif; font-size: 42px; font-weight: 900;
    color: #ffffff; text-align: center; letter-spacing: -0.5px; line-height: 1.1;
    text-shadow: 0 2px 20px rgba(0,0,0,0.8);
  }
  .board-subtitle {
    font-family: 'Barlow', sans-serif; font-size: 19px; font-weight: 600;
    color: #999; text-align: center; margin-top: 4px;
  }
  .legend-line {
    display: flex; align-items: center; justify-content: center;
    gap: 14px; margin: 10px 0 14px 0;
  }
  .legend-badge {
    background: #111; border: 1px solid #333; border-radius: 20px;
    padding: 4px 14px; display: flex; align-items: center; gap: 6px;
    font-size: 13px; font-weight: 700; color: #f0f0f0;
  }
  .legend-badge .dot { color: #00e676; font-size: 16px; }
  .legend-note { color: #aaa; font-size: 13px; }
  .legend-yellow { color: #ffd700; font-size: 13px; }
  .divider-line {
    height: 2px;
    background: linear-gradient(90deg, transparent, #ff6600 20%, #ff6600 80%, transparent);
    margin: 0 0 16px 0; opacity: 0.7;
  }
  .game-card {
    background: #161616; border: 1px solid #2a2a2a;
    border-radius: 10px; margin-bottom: 12px; overflow: hidden;
  }
  .game-header {
    display: flex; justify-content: space-between; align-items: center;
    padding: 9px 16px; background: #1c1c1c; border-bottom: 1px solid #2e2e2e;
  }
  .matchup {
    font-family: 'Barlow', sans-serif; font-size: 22px; font-weight: 800;
    color: #ffffff; letter-spacing: 0.3px;
  }
  .game-time {
    font-family: 'Barlow', sans-serif; font-size: 15px;
    font-weight: 600; color: #ff6600;
  }
  .cols-wrap {
    display: grid; grid-template-columns: 1fr 2px 1fr 2px 1fr; min-height: 170px;
  }
  .col-divider { background: #2a2a2a; width: 2px; }
  .col-block { padding: 8px 12px 8px 12px; }
  .col-header {
    font-family: 'Barlow', sans-serif; font-size: 12px; font-weight: 700;
    color: #ff6600; letter-spacing: 1.5px; text-transform: uppercase;
    border-bottom: 1px solid #2a2a2a; padding-bottom: 5px; margin-bottom: 6px;
  }
  .no-lines {
    display: flex; align-items: center; justify-content: center;
    height: 120px; color: #444; font-style: italic; font-size: 13px;
  }
  .data-row {
    display: grid; grid-template-columns: 42px 46px 1fr 40px;
    align-items: center; height: 25px; border-bottom: 1px solid #1e1e1e;
  }
  .data-row:last-child { border-bottom: none; }
  .team { font-size: 12.5px; color: #aaaaaa; font-weight: 600; }
  .spread { font-size: 12.5px; color: #e0e0e0; }
  .odds { font-size: 14px; font-weight: 700; letter-spacing: 0.3px; }
  .odds.pos { color: #00e676; }
  .odds.neg { color: #f0f0f0; }
  .dot { color: #00e676; font-size: 11px; vertical-align: middle; }
  .book { font-size: 11px; color: #ffd700; text-align: right; font-weight: 700; }
  .footer { text-align: center; margin-top: 8px; color: #444; font-size: 12px; }
  .footer-books { color: #383838; font-size: 11px; margin-top: 3px; }
'''

def build_html(block_key, block_data):
    label      = block_data['label']
    games_html = '\n'.join(game_card_html(g) for g in block_data['games'])
    return f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"/>
<style>{CSS}</style>
</head><body>
<div class="wrapper">
  <div class="board-title">&#9918; MLB BETTING BOARD &mdash; {label}</div>
  <div class="board-subtitle">Full Game &middot; First Inning &middot; First 5 Inn | {DATE_STR}</div>
  <div class="legend-line">
    <div class="legend-badge"><span class="dot">&#9679;</span> TRISHULA VALUE PICK</div>
    <span class="legend-note">white=line</span>
    <span class="legend-yellow">yellow=book source</span>
  </div>
  <div class="divider-line"></div>
  {games_html}
  <div class="footer">Compiled By Trishula Software's 'The Swarm' Agentic AI</div>
  <div class="footer-books">DK &middot; MGM &middot; FD &middot; CZR &middot; 365 &middot; RIV &middot; FAN &middot; KAL &middot; POLY</div>
</div></body></html>'''

# ─── PLAYWRIGHT SCREENSHOT ─────────────────────────────────────────────────────
async def screenshot_block(block_key, block_data, output_dir):
    from playwright.async_api import async_playwright
    html      = build_html(block_key, block_data)
    label_safe = block_data['label'].replace(':', '').replace(' ', '_').replace('–', '_').replace('—', '_')
    fname     = output_dir / f'swarm_{block_key.lower()}_{label_safe}.png'
    html_file = output_dir / f'_tmp_{block_key}.html'
    html_file.write_text(html, encoding='utf-8')

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page    = await browser.new_page()
        await page.set_viewport_size({'width': 1024, 'height': 800})
        await page.goto(f'file:///{html_file}')
        await page.wait_for_timeout(1500)
        await page.screenshot(path=str(fname), full_page=True)
        await browser.close()

    html_file.unlink(missing_ok=True)
    print(f'  [BOARD] {fname.name}')
    return str(fname)

# ─── DISCORD POSTER ───────────────────────────────────────────────────────────
def post_to_discord(image_paths: list, block_label: str):
    """Post board images to Discord webhook."""
    try:
        import requests
        from pathlib import Path as P

        # Load webhook from scanner config
        cfg_path = P(r'H:\Trishula\Swarm_4_Integration\Salvo_Staging\sovereign_options_scanner.py')
        webhook  = None
        if cfg_path.exists():
            for line in cfg_path.read_text(encoding='utf-8', errors='ignore').splitlines():
                if 'DISCORD_WEBHOOK' in line and 'http' in line:
                    m = __import__('re').search(r'https?://[^\s\'"]+', line)
                    if m:
                        webhook = m.group(0).rstrip('",\'')
                        break

        if not webhook:
            print('  [DISCORD] No webhook found — skipping post')
            return

        for img_path in image_paths:
            img = P(img_path)
            if not img.exists():
                continue
            with open(img, 'rb') as f:
                r = requests.post(webhook, files={'file': (img.name, f, 'image/png')},
                                  data={'content': f'⚾ **MLB Board — {block_label}**'},
                                  timeout=30)
            if r.status_code in (200, 204):
                print(f'  [DISCORD] Posted {img.name}')
            else:
                print(f'  [DISCORD] Failed {r.status_code}: {r.text[:80]}')
    except Exception as e:
        print(f'  [DISCORD] Error: {e}')

# ─── MAIN ─────────────────────────────────────────────────────────────────────
async def main(text: str, post_discord: bool = False):
    print(f'\nTrishula Swarm Board Pipeline')
    print(f'Date   : {DATE_STR}')
    print(f'Output : {OUTPUT_DIR}')
    print('─' * 55)

    print('[1/3] Parsing odds...')
    blocks = parse_odds.parse(text, verbose=True)
    print(f'      Found {len(blocks)} time blocks, {sum(len(v["games"]) for v in blocks.values())} games total')

    print('[2/3] Generating boards...')
    saved = []
    for bkey, bdata in blocks.items():
        path = await screenshot_block(bkey, bdata, OUTPUT_DIR)
        saved.append((bdata['label'], path))

    print(f'[3/3] {"Posting to Discord..." if post_discord else "Discord post skipped (use --discord to enable)"}')
    if post_discord:
        for label, path in saved:
            post_to_discord([path], label)

    print('─' * 55)
    print(f'Done. {len(saved)} boards saved to {OUTPUT_DIR}')
    return saved

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Trishula Swarm Board Pipeline')
    ap.add_argument('--file',    '-f', help='Input file with pasted odds text')
    ap.add_argument('--clip',    '-c', action='store_true', help='Read from clipboard')
    ap.add_argument('--discord', '-d', action='store_true', help='Post to Discord after generating')
    args = ap.parse_args()

    if args.clip:
        try:
            import pyperclip
            text = pyperclip.paste()
            print(f'[INPUT] Read {len(text)} chars from clipboard')
        except ImportError:
            print('Install pyperclip: pip install pyperclip')
            sys.exit(1)
    elif args.file:
        text = Path(args.file).read_text(encoding='utf-8', errors='replace')
        print(f'[INPUT] Read {len(text)} chars from {args.file}')
    else:
        print('[INPUT] Reading from stdin (paste and press Ctrl+Z then Enter on Windows)...')
        text = sys.stdin.read()
        print(f'[INPUT] Got {len(text)} chars')

    asyncio.run(main(text, post_discord=args.discord))
