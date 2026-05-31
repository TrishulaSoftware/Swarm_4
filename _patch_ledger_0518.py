# -*- coding: utf-8 -*-
"""
TRISHULA -- 05/18/2026 LEDGER MANUAL PATCH
Grades all PENDING entries using known final scores and boxscore data.

FINAL SCORES 05/18/2026:
  CLE @ DET: CLE 4, DET 3   (CLE wins)
  CIN @ PHI: CIN 4, PHI 8   (PHI wins)
  BAL @ TB:  BAL 5, TB 4    (BAL wins, total=9)
  ATL @ MIA: ATL 0, MIA 12  (MIA wins, ATL -1.5 LOSS)
  NYM @ WSH: NYM 5, WSH 3   (NYM wins, WSH +120 LOSS)
  TOR @ NYY: TOR 6, NYY 7   (NYY wins, NYY -1.5 LOSS [margin=1])
  HOU @ MIN: HOU 3, MIN 4   (MIN wins, HOU ML LOSS)
  MIL @ CHC: MIL 3, CHC 5   (CHC wins, total=8 UNDER 10.5)
  BOS @ KC:  BOS 2, KC 5    (KC wins, BOS ML LOSS)
  TEX @ COL: TEX 5, COL 11  (COL wins, total=16 OVER 10)
  ATH @ LAA: ATH 5, LAA 4   (ATH wins, OAK ML WIN)
  LAD @ SD:  LAD 0, SD 1    (SD wins, LAD -1.5 LOSS)
  CWS @ SEA: CWS 1, SEA 6   (SEA wins, SEA -1.5 WIN [margin=5])
  SF @ AZ:   SF 4, AZ 5     (AZ wins, ARI ML WIN)

1ST INNING RESULTS:
  CIN @ PHI: PHI scored in 1st → YRFI (CIN NRFI pick = LOSS)
  NYM @ WSH: No runs in 1st   → NRFI (NYM YRFI pick = LOSS)
  HOU @ MIN: No runs in 1st   → NRFI (HOU YRFI pick = LOSS)
  MIL @ CHC: No runs in 1st   → NRFI (CHC NRFI pick = WIN)
  TEX @ COL: Runs in 1st      → YRFI (COL YRFI pick = WIN)
  LAD @ SD:  No runs in 1st   → NRFI (LAD NRFI pick = WIN... wait LAD pick was NRFI u0.5)
  SF @ ARI:  No runs in 1st   → NRFI (ARI NRFI pick = WIN)

F5 RESULTS (first 5 innings leaders):
  CLE @ DET F5: CLE led after 5 → DET F5 -0.5 LOSS
  BAL @ TB F5:  TB led after 5  → TB F5 ML WIN
  ATL @ MIA F5: MIA dominated   → ATL F5 ML LOSS (ATL picked)
  TOR @ NYY F5: NYY led         → NYY F5 ML WIN
  BOS @ KC F5:  KC led after 5  → KC F5 ML WIN (KC picked)
  ATH @ LAA F5: ATH led         → OAK F5 ML WIN
  CWS @ SEA F5: SEA led by 3+   → SEA -0.5 F5 WIN

PLAYER RESULTS:
  De La Cruz: 0H (vs o0.5)      → LOSS
  Miguel Vargas: 2H (vs o0.5)   → WIN
  Otto Lopez: 0H (vs o0.5)      → LOSS
  Yandy Diaz: did not play      → PUSH/VOID (BAL won, TB starter scratched - ruled VOID)
  Drake Baldwin: 0R (vs o0.5)   → LOSS
  Juan Soto: 2 RBI (vs o0.5)    → WIN
  Kyle Schwarber: 1 RBI (vs o0.5) → WIN
  Aaron Judge: 1R (vs o0.5)     → WIN
  Yordan Alvarez: 0 RBI (vs o0.5) → LOSS
  Bryce Harper: 0 RBI (vs o0.5) → LOSS
  Shota Imanaga: 2K (vs o5.5)   → LOSS
  Brandon Sproat: 5K (vs o3.5)  → WIN
  Christian Scott: 5K (vs o4.5) → WIN
  Robbie Ray: 0K (vs o4.5)      → LOSS
  Nick Lodolo: 3K (vs o5.5)     → LOSS
  MacKenzie Gore: 2K (vs o6.5)  → LOSS
  Yoshinobu Yamamoto: 8K (vs o6.5) → WIN
  Spencer Steer TB: 2TB (vs o0.5)  → WIN
  Spencer Steer H+R+RBI: 2 (vs o0.5) → WIN
  Cody Bellinger H+R+RBI: 5 (vs o0.5) → WIN
  Ha-Seong Kim H+R+RBI: 0 (vs o0.5)  → LOSS
  Otto Lopez H+R+RBI: 0 (vs o0.5)    → LOSS
  Xavier Edwards H+R+RBI: 6 (vs o0.5) → WIN
  S. Cecconi SO: 4K (vs o2.5)        → WIN
  T. Rogers SO: 3K (vs o2.5)         → WIN
  Max Meyer Outs: 18 outs (vs o14.5) → WIN
"""

import json, requests, sys
sys.stdout.reconfigure(encoding='utf-8')
from config import WEBHOOKS

LEDGER_PATH = r'H:\Trishula_SBM\DataMine\MLB\Team Props\05_18_2026\ledger_05_18_2026.json'
FINAL_PATH  = r'H:\Trishula_SBM\DataMine\MLB\Team Props\05_18_2026\ledger_05_18_2026_FINAL.json'
WEBHOOK = WEBHOOKS["mlb_pick_ledger"]

# Manual grading map: entry id -> (result, actual_value, note)
GRADES = {
    # TEAM BASE
    "TEAM_BASE_0":  ("WIN",  "CLE 4 - DET 3",  "CLE ML +130 WIN"),
    "TEAM_BASE_1":  ("WIN",  "CIN 4 - PHI 8",  "PHI ML -120 WIN"),
    "TEAM_BASE_2":  ("LOSS", "BAL 5 - TB 4, total=9", "UNDER 7.5 LOSS — total went over"),
    "TEAM_BASE_3":  ("WIN",  "ATL 0 - MIA 12", "ATL Run Line (-1.5)... wait MIA won. ATL picked = LOSS"),
    "TEAM_BASE_4":  ("LOSS", "NYM 5 - WSH 3",  "WSH ML +120 LOSS — NYM won"),
    "TEAM_BASE_5":  ("LOSS", "TOR 6 - NYY 7",  "NYY Run Line -1.5 LOSS — margin only 1"),
    "TEAM_BASE_6":  ("LOSS", "HOU 3 - MIN 4",  "HOU ML -106 LOSS — MIN won"),
    "TEAM_BASE_7":  ("LOSS", "MIL 3 - CHC 5, total=8", "OVER 10.5 LOSS — total only 8"),
    "TEAM_BASE_8":  ("LOSS", "BOS 2 - KC 5",   "BOS ML -111 LOSS — KC won"),
    "TEAM_BASE_9":  ("WIN",  "TEX 5 - COL 11, total=16", "OVER 10 WIN — total was 16"),
    "TEAM_BASE_10": ("WIN",  "ATH 5 - LAA 4",  "OAK/ATH ML -116 WIN"),
    "TEAM_BASE_11": ("LOSS", "LAD 0 - SD 1",   "LAD Run Line -1.5 LOSS — SD won outright"),
    "TEAM_BASE_12": ("WIN",  "CWS 1 - SEA 6",  "SEA Run Line -1.5 WIN — margin 5"),
    "TEAM_BASE_13": ("WIN",  "SF 4 - AZ 5",    "ARI ML -125 WIN"),
    # TEAM ALT
    "TEAM_ALT_0":   ("LOSS", "CLE led F5",     "DET F5 Run Line -0.5 LOSS — CLE led after 5"),
    "TEAM_ALT_1":   ("LOSS", "1st inn: PHI scored", "NRFI u0.5 LOSS — PHI scored in 1st"),
    "TEAM_ALT_2":   ("WIN",  "TB led F5",      "TB F5 ML -138 WIN"),
    "TEAM_ALT_3":   ("LOSS", "MIA dominated",  "ATL F5 ML -110 LOSS — MIA led after 5"),
    "TEAM_ALT_4":   ("LOSS", "1st inn: no runs", "YRFI o0.5 LOSS — scoreless 1st"),
    "TEAM_ALT_5":   ("WIN",  "NYY led F5",     "NYY F5 ML -180 WIN"),
    "TEAM_ALT_6":   ("LOSS", "1st inn: no runs", "YRFI o0.5 LOSS — scoreless 1st"),
    "TEAM_ALT_7":   ("WIN",  "1st inn: no runs", "NRFI u0.5 WIN — scoreless 1st"),
    "TEAM_ALT_8":   ("WIN",  "KC led F5",      "KC F5 ML -110 WIN"),
    "TEAM_ALT_9":   ("WIN",  "1st inn: runs scored", "YRFI o0.5 WIN — Coors, runs in 1st"),
    "TEAM_ALT_10":  ("WIN",  "ATH led F5",     "OAK F5 ML -120 WIN"),
    "TEAM_ALT_11":  ("WIN",  "1st inn: no runs", "NRFI u0.5 WIN — LAD/SD scoreless 1st"),
    "TEAM_ALT_12":  ("WIN",  "SEA led F5 +4",  "SEA F5 Run Line -0.5 WIN — SEA dominated"),
    "TEAM_ALT_13":  ("WIN",  "1st inn: no runs", "NRFI u0.5 WIN — SF/ARI scoreless 1st"),
    # PLAYER BAT
    "PLAYER_BAT_0": ("LOSS", "0H",  "De La Cruz 0H vs o0.5 LOSS"),
    "PLAYER_BAT_1": ("WIN",  "2H",  "Miguel Vargas 2H vs o0.5 WIN"),
    "PLAYER_BAT_2": ("LOSS", "0H",  "Otto Lopez 0H vs o0.5 LOSS"),
    "PLAYER_BAT_3": ("VOID", "DNP", "Yandy Diaz did not play — VOID"),
    "PLAYER_BAT_4": ("LOSS", "0R",  "Drake Baldwin 0R vs o0.5 LOSS"),
    "PLAYER_BAT_5": ("WIN",  "2 RBI", "Juan Soto 2 RBI vs o0.5 WIN"),
    "PLAYER_BAT_6": ("WIN",  "1 RBI", "Kyle Schwarber 1 RBI vs o0.5 WIN"),
    "PLAYER_BAT_7": ("WIN",  "1R",  "Aaron Judge 1R vs o0.5 WIN"),
    "PLAYER_BAT_8": ("LOSS", "0 RBI", "Yordan Alvarez 0 RBI vs o0.5 LOSS"),
    "PLAYER_BAT_9": ("LOSS", "0 RBI", "Bryce Harper 0 RBI vs o0.5 LOSS"),
    # PLAYER PIT
    "PLAYER_PIT_0": ("LOSS", "2K",  "Imanaga 2K vs o5.5 LOSS"),
    "PLAYER_PIT_1": ("WIN",  "5K",  "Sproat 5K vs o3.5 WIN"),
    "PLAYER_PIT_2": ("WIN",  "5K",  "C. Scott 5K vs o4.5 WIN"),
    "PLAYER_PIT_3": ("LOSS", "0K",  "Robbie Ray 0K vs o4.5 LOSS"),
    "PLAYER_PIT_4": ("LOSS", "3K",  "Lodolo 3K vs o5.5 LOSS"),
    "PLAYER_PIT_5": ("LOSS", "2K",  "Gore 2K vs o6.5 LOSS"),
    "PLAYER_PIT_6": ("WIN",  "8K",  "Yamamoto 8K vs o6.5 WIN"),
    # PLAYER ALT
    "PLAYER_ALT_0": ("WIN",  "2TB", "Steer 2TB vs o0.5 WIN"),
    "PLAYER_ALT_1": ("WIN",  "2 H+R+RBI", "Steer 2 H+R+RBI vs o0.5 WIN"),
    "PLAYER_ALT_2": ("WIN",  "5 H+R+RBI", "Bellinger 5 H+R+RBI vs o0.5 WIN"),
    "PLAYER_ALT_3": ("LOSS", "0 H+R+RBI", "Ha-Seong Kim 0 vs o0.5 LOSS"),
    "PLAYER_ALT_4": ("LOSS", "0 H+R+RBI", "Otto Lopez 0 vs o0.5 LOSS"),
    "PLAYER_ALT_5": ("WIN",  "6 H+R+RBI", "Xavier Edwards 6 vs o0.5 WIN"),
    "PLAYER_ALT_6": ("WIN",  "4K",  "Cecconi 4K vs o2.5 WIN"),
    "PLAYER_ALT_7": ("WIN",  "3K",  "T. Rogers 3K vs o2.5 WIN"),
    "PLAYER_ALT_8": ("WIN",  "18 outs", "Max Meyer 18 outs vs o14.5 WIN"),
}

# Fix TEAM_BASE_3 — we picked ATL, MIA won 12-0 so ATL Run Line -1.5 = LOSS
GRADES["TEAM_BASE_3"] = ("LOSS", "ATL 0 - MIA 12", "ATL Run Line -1.5 LOSS — MIA won outright 12-0")

# Load ledger and apply grades
data = json.load(open(LEDGER_PATH, encoding='utf-8'))
entries = data['entries']

wins = losses = voids = 0
for e in entries:
    eid = e['id']
    if eid in GRADES:
        result, actual, note = GRADES[eid]
        e['result'] = result
        e['actual_value'] = actual
        e['grade_note'] = note
        if result == 'WIN':   wins += 1
        elif result == 'LOSS': losses += 1
        elif result == 'VOID': voids += 1

total_graded = wins + losses
pct = round((wins / total_graded) * 100, 1) if total_graded > 0 else 0

data['final_record'] = f"{wins}W - {losses}L - {voids}V"
data['win_rate'] = f"{pct}%"
data['status'] = 'FINAL'

# Save FINAL
with open(FINAL_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2)
print(f"[OK] Ledger sealed: {wins}W - {losses}L - {voids}V | {pct}% | Saved to FINAL.json")

# Build Discord report
lines = []
lines.append(f"```")
lines.append(f"TRISHULA SWARM | MAY 18, 2026 — FINAL LEDGER")
lines.append(f"{'='*48}")
lines.append(f"  RECORD   : {wins}W - {losses}L - {voids}V")
lines.append(f"  WIN RATE : {pct}%")
lines.append(f"  TOTAL    : {total_graded} graded picks")
lines.append(f"{'='*48}")
lines.append(f"")
lines.append(f"TEAM PICKS")
lines.append(f"{'-'*48}")
for e in entries:
    if e['id'].startswith('TEAM_BASE') or e['id'].startswith('TEAM_ALT'):
        r = e.get('result','?')
        tag = '[WIN] ' if r=='WIN' else ('[LOSS]' if r=='LOSS' else '[VOID]')
        lines.append(f"  {tag} {e['id']}: {e.get('game','')} | {e.get('pick','')}")
lines.append(f"")
lines.append(f"PLAYER PICKS")
lines.append(f"{'-'*48}")
for e in entries:
    if e['id'].startswith('PLAYER'):
        r = e.get('result','?')
        tag = '[WIN] ' if r=='WIN' else ('[LOSS]' if r=='LOSS' else '[VOID]')
        lines.append(f"  {tag} {e.get('game','')} | {e.get('pick','')}")
lines.append(f"```")

msg = "\n".join(lines)
# Split if too long
chunks = [msg[i:i+1900] for i in range(0, len(msg), 1900)]
for chunk in chunks:
    r = requests.post(WEBHOOK, json={"content": chunk})
    if r.status_code in [200, 204]:
        print(f"[OK] Dispatched chunk to Discord.")
    else:
        print(f"[ERR] Discord: {r.status_code} {r.text}")

print("[DONE] 05/18/2026 ledger finalized and dispatched.")
