#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Post MLB Betting Boards to Discord.
Usage: python post_boards_discord.py [channel]
Channels: team_props | pick_ledger | parlays | player_props | player_parlays
Default: pick_ledger (mlb_pick_ledger channel)
"""

import sys, requests
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent))
from config import WEBHOOKS, SWARM_IDENTITY

BOARDS_DIR = Path(r"H:\Trishula\Swarm_4_Integration\Salvo_Staging\swarm_boards")

# Map CLI arg to webhook key
CHANNEL_MAP = {
    'team_props':     'mlb_team_props',
    'pick_ledger':    'mlb_pick_ledger',
    'parlays':        'mlb_parlays',
    'player_props':   'mlb_player_props',
    'player_parlays': 'mlb_player_parlays',
}

BOARD_ORDER = [
    ('B1', 'swarm_b1_640_645_PM.png',  '6:40–6:45 PM'),
    ('B2', 'swarm_b2_705_715_PM.png',  '7:05–7:15 PM'),
    ('B3', 'swarm_b3_740_745_PM.png',  '7:40–7:45 PM'),
    ('B4', 'swarm_b4_805_810_PM.png',  '8:05–8:10 PM'),
    ('B5', 'swarm_b5_938_940_PM.png',  '9:38–9:40 PM'),
]

def post_board(webhook, img_path, label, is_first=False):
    content = '⚾ **MLB BETTING BOARD — Jun 2, 2026**\n`Full Game · First Inning · First 5 Inn`' if is_first else f'`{label}`'
    with open(img_path, 'rb') as f:
        r = requests.post(
            webhook,
            data={
                'content':  content,
                'username': SWARM_IDENTITY['username'],
            },
            files={'file': (img_path.name, f, 'image/png')},
            timeout=30
        )
    if r.status_code in (200, 204):
        print(f'  ✓  [{label}] posted')
        return True
    else:
        print(f'  ✗  [{label}] HTTP {r.status_code}: {r.text[:100]}')
        return False

def main():
    channel_key = sys.argv[1] if len(sys.argv) > 1 else 'pick_ledger'
    wh_key      = CHANNEL_MAP.get(channel_key, 'mlb_pick_ledger')
    webhook     = WEBHOOKS[wh_key]

    print(f'\nTrishula Swarm — Board Post')
    print(f'Channel : {wh_key}')
    print(f'Boards  : {BOARDS_DIR}')
    print('─' * 45)

    for i, (bkey, fname, label) in enumerate(BOARD_ORDER):
        img = BOARDS_DIR / fname
        if not img.exists():
            print(f'  ⚠  [{label}] file not found — skipping')
            continue
        post_board(webhook, img, label, is_first=(i == 0))

    print('─' * 45)
    print('Done.')

if __name__ == '__main__':
    main()
