# -*- coding: utf-8 -*-
"""
Injects missed ODS streak picks into player_props_dispatch.py PITCHING_PROPS
and adds H+R+RBI O1.5 streak picks to BATTING_PROPS.
"""

EXTRA_PITCHING = '''
    {"player": "Chase Burns", "team": "CIN", "opp": "PHI",
     "prop": "Pitcher Outs", "line": "o16.5", "odds": "-115",
     "matchupEdge": "Burns @ PHI (6/L6 — 100% streak)", "streak": "6",
     "pick": "OVER 16.5", "confidence": "99%",
     "rationale": "[LOCK] 100% hit rate — 6/6 last 6. Burns goes deep in starts. Needs 5.2+ IP, well within his norm."},
    {"player": "Dylan Cease", "team": "TOR", "opp": "NYY",
     "prop": "Pitcher Outs", "line": "o15.5", "odds": "-135",
     "matchupEdge": "Cease @ NYY (4/L4 — 100% streak)", "streak": "4",
     "pick": "OVER 15.5", "confidence": "99%",
     "rationale": "[LOCK] 100% hit rate — 4/4 last 4. Cease needs 5.1+ IP. His recent workload confirms this."},
    {"player": "Dylan Cease", "team": "TOR", "opp": "NYY",
     "prop": "Pitcher Outs", "line": "o16.5", "odds": "-115",
     "matchupEdge": "Cease @ NYY (4/L4 — 100% streak, bonus line)", "streak": "4",
     "pick": "OVER 16.5", "confidence": "99%",
     "rationale": "[LOCK] 100% hit rate — 4/4 last 4 at the higher 16.5 line. Better value at -115."},
    {"player": "Kyle Bradish", "team": "BAL", "opp": "TB",
     "prop": "Hits Allowed", "line": "o4.5", "odds": "-155",
     "matchupEdge": "Bradish @ TB (5/L5 away — 100% streak)", "streak": "5",
     "pick": "OVER 4.5", "confidence": "99%",
     "rationale": "[LOCK] 100% hit rate — 5/5 last 5 away games. TB offense makes contact vs Bradish."},
    {"player": "Emmet Sheehan", "team": "LAD", "opp": "SD",
     "prop": "Strikeouts", "line": "o5.5", "odds": "-120",
     "matchupEdge": "Sheehan @ SD (4/L4 — 100% streak)", "streak": "4",
     "pick": "OVER 5.5", "confidence": "99%",
     "rationale": "[LOCK] 100% hit rate — 4/4 last 4. 75% 2026 rate. 100% H2H vs SD."},
    {"player": "Will Warren", "team": "NYY", "opp": "TOR",
     "prop": "Pitcher Outs", "line": "o16.5", "odds": "-103",
     "matchupEdge": "Warren vs TOR (4/L5 — 80% streak)", "streak": "4",
     "pick": "OVER 16.5", "confidence": "83%",
     "rationale": "80% hit rate last 5 starts. Near even-money on a pitcher consistently going deep."},
    {"player": "Martin Perez", "team": "ATL", "opp": "MIA",
     "prop": "Earned Runs", "line": "o1.5", "odds": "-150",
     "matchupEdge": "Perez @ MIA (5/L6 away — 83% streak)", "streak": "5",
     "pick": "OVER 1.5", "confidence": "83%",
     "rationale": "83% hit rate 5/6 away starts. MIA bats are a good matchup for run production."},
    {"player": "Jesus Luzardo", "team": "PHI", "opp": "CIN",
     "prop": "Hits Allowed", "line": "o4.5", "odds": "-140",
     "matchupEdge": "Luzardo vs CIN (4/L5 home — 80% streak)", "streak": "4",
     "pick": "OVER 4.5", "confidence": "80%",
     "rationale": "80% hit rate 4/5 home starts. CIN bats make contact. Hits Allowed line is very hittable."},
'''

EXTRA_BATTING = '''
    {"player": "Spencer Steer", "team": "CIN", "opp": "PHI",
     "prop": "H+R+RBI", "line": "o1.5", "odds": "-105",
     "matchupEdge": "Steer vs PHI (9-streak O1.5, 43% H2H)", "streak": "9",
     "pick": "OVER 1.5", "confidence": "91%",
     "rationale": "[LOCK] 9-game O1.5 H+R+RBI streak. 52% 2026 rate. Near even-money value."},
    {"player": "Samuel Basallo", "team": "BAL", "opp": "TB",
     "prop": "H+R+RBI", "line": "o1.5", "odds": "-104",
     "matchupEdge": "Basallo vs TB (10-streak O1.5, 0% H2H — new matchup)", "streak": "10",
     "pick": "OVER 1.5", "confidence": "89%",
     "rationale": "10-game O1.5 H+R+RBI streak. 59% 2026 rate. Near even-money at -104 is elite value."},
    {"player": "Taylor Walls", "team": "TB", "opp": "BAL",
     "prop": "H+R+RBI", "line": "o1.5", "odds": "-172",
     "matchupEdge": "Walls vs BAL (7-streak O1.5, 57% H2H)", "streak": "7",
     "pick": "OVER 1.5", "confidence": "88%",
     "rationale": "7-game O1.5 H+R+RBI streak. 68% 2026 rate. 57% H2H vs BAL. Strong floor."},
    {"player": "Alec Bohm", "team": "PHI", "opp": "CIN",
     "prop": "H+R+RBI", "line": "o1.5", "odds": "-120",
     "matchupEdge": "Bohm vs CIN (5-streak O1.5, 75% H2H)", "streak": "5",
     "pick": "OVER 1.5", "confidence": "87%",
     "rationale": "5-game O1.5 H+R+RBI streak. 39% 2026 rate but 75% H2H. Strong matchup value."},
    {"player": "Juan Soto", "team": "NYM", "opp": "WSH",
     "prop": "H+R+RBI", "line": "o1.5", "odds": "-172",
     "matchupEdge": "Soto vs WSH (5-streak O1.5, 77% H2H)", "streak": "5",
     "pick": "OVER 1.5", "confidence": "86%",
     "rationale": "5-game O1.5 H+R+RBI streak. 77% H2H vs WSH is exceptional. Soto produces multi-category."},
'''

# Load and patch player_props_dispatch.py
content = open(
    r'H:\Trishula\Swarm_4_Integration\Salvo_Staging\player_props_dispatch.py',
    encoding='utf-8'
).read()

# Inject extra pitching before the closing bracket of PITCHING_PROPS
pit_end = content.rfind(']', 0, content.find('\ndef chunk(lst, n):'))
# Find the actual closing ] of PITCHING_PROPS block
pit_marker = 'PITCHING_PROPS = ['
pit_start_idx = content.find(pit_marker)
# Find the matching closing ] after PITCHING_PROPS
depth = 0
i = pit_start_idx + len(pit_marker) - 1
while i < len(content):
    if content[i] == '[':
        depth += 1
    elif content[i] == ']':
        depth -= 1
        if depth == 0:
            pit_close = i
            break
    i += 1

content = content[:pit_close] + EXTRA_PITCHING + content[pit_close:]

# Inject extra batting before the closing ] of BATTING_PROPS
bat_marker = 'BATTING_PROPS = ['
bat_start_idx = content.find(bat_marker)
depth = 0
i = bat_start_idx + len(bat_marker) - 1
while i < len(content):
    if content[i] == '[':
        depth += 1
    elif content[i] == ']':
        depth -= 1
        if depth == 0:
            bat_close = i
            break
    i += 1

content = content[:bat_close] + EXTRA_BATTING + content[bat_close:]

open(
    r'H:\Trishula\Swarm_4_Integration\Salvo_Staging\player_props_dispatch.py',
    'w', encoding='utf-8'
).write(content)
print(f'[OK] player_props_dispatch.py updated. Total chars: {len(content)}')
