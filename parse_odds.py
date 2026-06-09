#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trishula Swarm — Action Network Odds Parser
Parses raw copy/paste text from Action Network into structured game data.
Handles: Full Game, First Inning, First 5 Innings across all books.

Usage:
    python parse_odds.py < pasted_odds.txt
    python parse_odds.py --file pasted_odds.txt
    python parse_odds.py --clip   (read from clipboard)
"""

import re, sys, json, argparse
from pathlib import Path

# ─── BOOK LOGO → SHORT CODE ───────────────────────────────────────────────────
BOOK_MAP = {
    'kalshi':       'KAL',
    'dk nj':        'DK',
    'draftkings':   'DK',
    'fanduel nj':   'FD',
    'fanduel':      'FD',
    'fanatics nj':  'FAN',
    'fanatics':     'FAN',
    'betmgm nj':    'MGM',
    'betmgm':       'MGM',
    'caesars nj':   'CZR',
    'caesars':      'CZR',
    'betrivers nj': 'RIV',
    'betrivers':    'RIV',
    'bet365 md':    '365MD',
    'bet365 nj':    '365',
    'bet365':       '365MD',
    'polymarket':   'POLY',
}

# Column order for the 10 books (after Open + Best in Action Network)
BOOK_ORDER = ['365MD', 'KAL', 'POLY', '365', 'FAN', 'FD', 'DK', 'MGM', 'CZR', 'RIV']

def logo_to_book(line: str) -> str:
    """Convert a logo label line to a short book code."""
    low = line.lower().replace(' logo', '').strip()
    for k, v in BOOK_MAP.items():
        if k in low:
            return v
    return 'UNK'

# ─── TOKEN CLASSIFIERS ────────────────────────────────────────────────────────
def is_spread(s):   return bool(re.match(r'^[+-]\d+(\.\d+)?$', s)) and '.' in s
def is_odds(s):     return bool(re.match(r'^[+-]\d+$', s))
def is_over(s):     return bool(re.match(r'^o\d+(\.\d+)?$', s, re.I))
def is_under(s):    return bool(re.match(r'^u\d+(\.\d+)?$', s, re.I))
def is_na(s):       return s.strip().upper() == 'N/A'
def is_logo(s):     return 'logo' in s.lower()
def is_time(s):     return bool(re.match(r'^\d{1,2}:\d{2}\s*[AP]M$', s.strip()))
def is_game_id(s):  return bool(re.match(r'^\d{3,4}$', s.strip()))
def is_team_icon(s):return 'team icon' in s.lower()

# ─── PRE-PROCESS TEXT ─────────────────────────────────────────────────────────
def tokenize(text: str) -> list:
    """Clean and tokenize the raw pasted text."""
    tokens = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Skip noise lines
        if any(x in line.lower() for x in [
            'game', 'scheduled', 'open', 'best odds', 'offers',
            'california', 'promotion', 'promo code', 'claim', 'action',
            'age, location', 'play responsibly', 'see more', 'see all',
            'mlb teams', 'all teams', 'new york yankees', 'los angeles dodgers',
            'philadelphia phillies', 'novig', 'draftkings pick6',
            "julio rodriguez", "jj bleday", "next", "stay",
            'try this first',
        ]):
            continue
        tokens.append(line)
    return tokens

# ─── PARSE ONE MARKET BLOCK ───────────────────────────────────────────────────
def parse_market_block(tokens: list, idx: int, mtype: str) -> tuple:
    """
    Parse a spread, total, or ML market block starting at idx.
    Returns (market_dict, new_idx).
    mtype: 'spread' | 'total' | 'ml'
    """
    # We read:
    result = {}
    i = idx

    def consume(check_fn=None):
        nonlocal i
        while i < len(tokens):
            t = tokens[i]
            if is_na(t):
                i += 1
                return 'N/A'
            if check_fn is None or check_fn(t):
                i += 1
                return t
            i += 1
            return t
        return None

    try:
        # ── For ML, the Action Network format is:
        #   [open_away_ml]  [open_home_ml]
        #   [best_away_ml]  [LOGO]
        #   [best_home_ml]  [LOGO]
        #   ...10 per-book ml pairs...
        #
        # For Spread/Total:
        #   [open_away_val] [open_away_odds]  [open_home_val] [open_home_odds]
        #   [best_away_val] [best_away_odds]  [LOGO]
        #   [best_home_val] [best_home_odds]  [LOGO]
        #   ...10 per-book spread/total pairs...

        def peek_logo(offset=0):
            j = i + offset
            return j < len(tokens) and is_logo(tokens[j])

        def parse_val(v):
            if v is None or v == 'N/A': return None
            v2 = re.sub(r'^[ou]', '', v, flags=re.I)
            result['under_book'] = best_home_book
        elif mtype == 'ml':
            # ML values come in as odds strings like '+127' or '-133'
            result['ml_away']      = parse_val(best_away_odds)   # odds IS the value for ML
            result['ml_away_book'] = best_away_book
            result['ml_home']      = parse_val(best_home_odds)
            result['ml_home_book'] = best_home_book

        # Skip the 10 per-book values (40 tokens, or N/A pairs)
        books_consumed = 0
        while books_consumed < 10 and i < len(tokens):
            t = tokens[i]
            # Stop if we hit a time line or next section marker
            if is_time(t) or is_team_icon(t) or t in ('First inning', 'First 5 innings'):
                break
            # N/A pair = one book slot
            if is_na(t):
                i += 1
                if i < len(tokens) and is_na(tokens[i]):
                    i += 1
                books_consumed += 1
                continue
            # Regular book: 4 values (away_val, away_odds, home_val, home_odds)
            # Or sometimes just 2 if spread/ml is identical
            consumed_this = 0
            for _ in range(4):
                if i >= len(tokens): break
                tt = tokens[i]
                if is_time(tt) or is_team_icon(tt): break
                if is_na(tt):
                    i += 1; consumed_this += 1
                    continue
                if is_logo(tt):
                    i += 1; consumed_this += 1
                    continue
                i += 1; consumed_this += 1
            if consumed_this > 0:
                books_consumed += 1

    except Exception as e:
        pass  # Return whatever we have so far

    return result, i

# ─── PARSE ONE SECTION (Full Game / F1I / F5I) ────────────────────────────────
def parse_section(tokens: list) -> list:
    """
    Parse a full section (Full Game, F1I, or F5I) into a list of game dicts.
    """
    games = []
    i = 0
    n = len(tokens)

    while i < n:
        # Look for away team icon
        if not is_team_icon(tokens[i]):
            i += 1
            continue

        # Away team
        i += 1
        if i >= n: break
        away = tokens[i]; i += 1   # team name

        # Skip game ID
        if i < n and is_game_id(tokens[i]): i += 1

        # Home team icon
        if i < n and is_team_icon(tokens[i]): i += 1
        if i >= n: break
        home = tokens[i]; i += 1

        # Skip game ID
        if i < n and is_game_id(tokens[i]): i += 1

        # Now parse market blocks until we hit the time line
        game = {'away': away, 'home': home, 'time': None,
                'spread': {}, 'total': {}, 'ml': {}}

        # Determine which market type comes next based on token shape
        market_order = ['spread', 'total', 'ml']
        mtype_idx = 0

        while i < n and not is_time(tokens[i]):
            t = tokens[i]

            # Detect market type from current token
            if is_spread(t) or (is_odds(t) and mtype_idx == 0):
                mtype = 'spread'
            elif is_over(t) or is_under(t):
                mtype = 'total'
                mtype_idx = max(mtype_idx, 1)
            elif is_odds(t) and mtype_idx >= 1:
                mtype = 'ml'
                mtype_idx = 2
            else:
                i += 1
                continue

            mdata, i = parse_market_block(tokens, i, mtype)
            game[mtype].update(mdata)

        # Capture time
        if i < n and is_time(tokens[i]):
            game['time'] = tokens[i]; i += 1

        if away and home:
            games.append(game)

    return games

# ─── DETECT SECTION BOUNDARIES ────────────────────────────────────────────────
def split_sections(text: str) -> dict:
    """Split raw paste into Full Game, First Inning, First 5 Innings sections."""
    # Normalize section headers
    text_norm = re.sub(r'\r\n', '\n', text)

    sections = {'full': '', 'f1i': '', 'f5i': ''}

    f1i_match  = re.search(r'^First inning\s*$', text_norm, re.MULTILINE | re.IGNORECASE)
    f5i_match  = re.search(r'^First 5 innings\s*$', text_norm, re.MULTILINE | re.IGNORECASE)

    if f1i_match and f5i_match:
        sections['full'] = text_norm[:f1i_match.start()]
        sections['f1i']  = text_norm[f1i_match.end():f5i_match.start()]
        sections['f5i']  = text_norm[f5i_match.end():]
    elif f5i_match:
        sections['full'] = text_norm[:f5i_match.start()]
        sections['f5i']  = text_norm[f5i_match.end():]
    elif f1i_match:
        sections['full'] = text_norm[:f1i_match.start()]
        sections['f1i']  = text_norm[f1i_match.end():]
    else:
        sections['full'] = text_norm

    return sections

# ─── MERGE SECTIONS INTO UNIFIED GAME LIST ────────────────────────────────────
def merge_games(full_games, f1i_games, f5i_games) -> list:
    """Merge the three section game lists by matchup key."""
    def key(g): return f"{g['away']}@{g['home']}"

    full_map = {key(g): g for g in full_games}
    f1i_map  = {key(g): g for g in f1i_games}
    f5i_map  = {key(g): g for g in f5i_games}

    all_keys = list(full_map.keys())
    # Add any games that appear only in f1i/f5i sections
    for k in list(f1i_map.keys()) + list(f5i_map.keys()):
        if k not in all_keys:
            all_keys.append(k)

    merged = []
    for k in all_keys:
        g_full = full_map.get(k, {})
        g_f1i  = f1i_map.get(k, {})
        g_f5i  = f5i_map.get(k, {})

        merged.append({
            'away': g_full.get('away') or g_f1i.get('away') or g_f5i.get('away', 'UNK'),
            'home': g_full.get('home') or g_f1i.get('home') or g_f5i.get('home', 'UNK'),
            'time': g_full.get('time') or g_f1i.get('time') or g_f5i.get('time'),
            'full': _to_mkt(g_full) if g_full else None,
            'f1i':  _to_mkt(g_f1i)  if g_f1i  else None,
            'f5i':  _to_mkt(g_f5i)  if g_f5i  else None,
        })

    return merged

def _to_mkt(g: dict):
    """Convert parsed section game dict into market dict format."""
    if not g: return None
    s = g.get('spread', {})
    t = g.get('total', {})
    m = g.get('ml', {})
    if not (s or t or m): return None
    return {
        'away_rl':      s.get('away_rl', '?'),
        'away_rl_odds': s.get('away_rl_odds'),
        'away_rl_book': s.get('away_rl_book', '?'),
        'home_rl':      s.get('home_rl', '?'),
        'home_rl_odds': s.get('home_rl_odds'),
        'home_rl_book': s.get('home_rl_book', '?'),
        'over_line':    t.get('over_line', 0),
        'over_odds':    t.get('over_odds'),
        'over_book':    t.get('over_book', '?'),
        'under_line':   t.get('under_line', 0),
        'under_odds':   t.get('under_odds'),
        'under_book':   t.get('under_book', '?'),
        'ml_away':      m.get('ml_away'),
        'ml_away_book': m.get('ml_away_book', '?'),
        'ml_home':      m.get('ml_home'),
        'ml_home_book': m.get('ml_home_book', '?'),
    }

# ─── GROUP INTO TIME BLOCKS ────────────────────────────────────────────────────
def group_into_blocks(games: list) -> dict:
    """Group games into time blocks for board generation."""
    blocks = {}
    for g in games:
        t = g.get('time', 'Unknown')
        if t not in blocks:
            blocks[t] = []
        blocks[t].append(g)

    # Sort blocks by time
    def time_sort(t):
        m = re.match(r'(\d+):(\d+)\s*([AP]M)', t)
        if not m: return 9999
        h, mn, ap = int(m.group(1)), int(m.group(2)), m.group(3)
        if ap == 'PM' and h != 12: h += 12
        if ap == 'AM' and h == 12: h = 0
        return h * 60 + mn

    sorted_blocks = dict(sorted(blocks.items(), key=lambda x: time_sort(x[0])))

    # Collapse into named blocks (B1, B2...) grouping close times
    result = {}
    last_time_val = -1
    block_idx = 0
    block_times = []
    block_games = []

    for t, gs in sorted_blocks.items():
        tv = time_sort(t)
        if block_idx == 0 or tv - last_time_val > 20:  # 20-min gap = new block
            if block_games:
                bkey = f'B{block_idx}'
                label = f'{block_times[0]}' if len(set(block_times)) == 1 else f'{block_times[0]}–{block_times[-1]}'
                result[bkey] = {'label': label, 'games': list(block_games)}
            block_idx += 1
            block_times = [t]
            block_games = list(gs)
        else:
            block_times.append(t)
            block_games.extend(gs)
        last_time_val = tv

    # Flush final block
    if block_games:
        bkey = f'B{block_idx}'
        label = f'{block_times[0]}' if len(set(block_times)) == 1 else f'{block_times[0]}–{block_times[-1]}'
        result[bkey] = {'label': label, 'games': list(block_games)}

    return result

# ─── MAIN PARSE FUNCTION ──────────────────────────────────────────────────────
def parse(text: str, verbose: bool = False) -> dict:
    """
    Main entry point. Parse raw pasted text into block data dict.
    Returns: {block_key: {'label': str, 'games': [...]}}
    """
    sections = split_sections(text)

    full_toks = tokenize(sections['full'])
    f1i_toks  = tokenize(sections['f1i'])
    f5i_toks  = tokenize(sections['f5i'])

    full_games = parse_section(full_toks)
    f1i_games  = parse_section(f1i_toks)
    f5i_games  = parse_section(f5i_toks)

    if verbose:
        print(f'[PARSER] Full Game: {len(full_games)} games', file=sys.stderr)
        print(f'[PARSER] F1I     : {len(f1i_games)} games', file=sys.stderr)
        print(f'[PARSER] F5I     : {len(f5i_games)} games', file=sys.stderr)

    all_games = merge_games(full_games, f1i_games, f5i_games)
    blocks    = group_into_blocks(all_games)

    if verbose:
        for bk, bv in blocks.items():
            print(f'[PARSER] {bk}: {bv["label"]} — {len(bv["games"])} games', file=sys.stderr)

    return blocks

# ─── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Parse Action Network odds paste')
    ap.add_argument('--file', '-f', help='Input file path (default: stdin)')
    ap.add_argument('--clip', '-c', action='store_true', help='Read from clipboard')
    ap.add_argument('--verbose', '-v', action='store_true')
    ap.add_argument('--out', '-o', help='Output JSON file')
    args = ap.parse_args()

    if args.clip:
        try:
            import pyperclip
            text = pyperclip.paste()
        except ImportError:
            print('pyperclip not installed. Use --file or stdin.', file=sys.stderr)
            sys.exit(1)
    elif args.file:
        text = Path(args.file).read_text(encoding='utf-8', errors='replace')
    else:
        text = sys.stdin.read()

    blocks = parse(text, verbose=args.verbose)

    out_json = json.dumps(blocks, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(out_json, encoding='utf-8')
        print(f'Written to {args.out}')
    else:
        print(out_json)
