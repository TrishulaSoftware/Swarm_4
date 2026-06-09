import json

with open('action_network_20260607.json', encoding='utf-8') as f:
    data = json.load(f)

games = data['raw']['games']

print("=== CHECKING ALL PERIODS IN RAW DATA ===\n")
for g in games:
    teams  = {t['id']: t for t in g.get('teams', [])}
    away   = teams.get(g['away_team_id'], {}).get('abbr', '?')
    home   = teams.get(g['home_team_id'], {}).get('abbr', '?')
    status = g.get('status_display') or g.get('real_status', '')
    markets = g.get('markets', {})

    all_periods = set()
    for book_id, periods_dict in markets.items():
        if isinstance(periods_dict, dict):
            all_periods.update(periods_dict.keys())

    print(f"{away} @ {home} [{status}]: periods = {sorted(all_periods)}")

print("\n=== RAW API URL ===")
print(data.get('raw_url', data.get('GAME', {}).get('url', 'not stored')))
