# -*- coding: utf-8 -*-
"""
TRISHULA SWARM -- MLB PLAYER PROPS DISPATCH ENGINE
Handles: Batting Props + Pitching Props
Channels: Dedicated Player Props Webhook
"""

import requests
import time
import json
from config import WEBHOOKS, SWARM_IDENTITY, COLORS
from datetime import date

SLATE_DATE = date.today().strftime("%B %d, %Y")
WEBHOOK = WEBHOOKS["mlb_player_props"]

# ============================================================
#  BATTING PROPS — Home Runs, Total Bases, Hits+Runs+RBIs, Runs, Hits
# ============================================================
BATTING_PROPS = [
    {"player": "Alec Bohm", "team": "PHI", "opp": "CIN",
     "prop": "Hits", "line": "o0.5", "odds": "-242",
     "matchupEdge": "Bohm vs CIN (9-game hit streak, 100% H2H)", "streak": "9",
     "pick": "OVER 0.5", "confidence": "95%",
     "rationale": "[LOCK] 9-game hit streak. 100% H2H vs CIN. 55% 2026 rate. Parlay anchor."},
    {"player": "Samuel Basallo", "team": "BAL", "opp": "TB",
     "prop": "Hits", "line": "o0.5", "odds": "-173",
     "matchupEdge": "Basallo vs TB (10-game hit streak)", "streak": "10",
     "pick": "OVER 0.5", "confidence": "94%",
     "rationale": "[LOCK] 10-game hit streak. 65% 2026 rate. Longest active streak on the board."},
    {"player": "Spencer Steer", "team": "CIN", "opp": "PHI",
     "prop": "Hits", "line": "o0.5", "odds": "-185",
     "matchupEdge": "Steer vs PHI (9-game hit streak, 57% H2H)", "streak": "9",
     "pick": "OVER 0.5", "confidence": "93%",
     "rationale": "[LOCK] 9-game hit streak. 72% 2026 rate. 57% H2H vs PHI."},
    {"player": "Jake Bauers", "team": "MIL", "opp": "CHC",
     "prop": "Hits", "line": "o0.5", "odds": "-161",
     "matchupEdge": "Bauers vs CHC (9-game hit streak, 67% H2H)", "streak": "9",
     "pick": "OVER 0.5", "confidence": "91%",
     "rationale": "[LOCK] 9-game streak. 67% 2026 rate. 67% H2H vs CHC."},
    {"player": "Yandy Diaz", "team": "TB", "opp": "BAL",
     "prop": "Hits", "line": "o0.5", "odds": "-275",
     "matchupEdge": "Diaz vs BAL (5-game streak, 92% H2H)", "streak": "5",
     "pick": "OVER 0.5", "confidence": "89%",
     "rationale": "77% 2026 rate. 92% H2H vs BAL. One of the highest H2H rates on the board."},
    {"player": "Ivan Herrera", "team": "STL", "opp": "PIT",
     "prop": "Hits", "line": "o0.5", "odds": "-243",
     "matchupEdge": "Herrera vs PIT (6-game streak, 86% H2H)", "streak": "6",
     "pick": "OVER 0.5", "confidence": "88%",
     "rationale": "76% 2026 rate. 86% H2H vs PIT. Elite contact form."},
    {"player": "Angel Martinez", "team": "CLE", "opp": "DET",
     "prop": "Hits", "line": "o0.5", "odds": "-230",
     "matchupEdge": "Martinez vs DET (7-game streak, 79% H2H)", "streak": "7",
     "pick": "OVER 0.5", "confidence": "87%",
     "rationale": "7-game streak. 79% H2H vs DET. Consistent contact presence."},
    {"player": "Travis Bazzana", "team": "CLE", "opp": "DET",
     "prop": "Hits", "line": "o0.5", "odds": "-212",
     "matchupEdge": "Bazzana vs DET (5-game streak, 100% H2H)", "streak": "5",
     "pick": "OVER 0.5", "confidence": "86%",
     "rationale": "100% H2H vs DET. 67% 2026 rate. Strong value at this price."},
    {"player": "Juan Soto", "team": "NYM", "opp": "WSH",
     "prop": "Runs", "line": "o0.5", "odds": "-128",
     "matchupEdge": "Soto vs WSH (5-game run streak, 77% H2H)", "streak": "5",
     "pick": "OVER 0.5", "confidence": "84%",
     "rationale": "5-game streak. 77% H2H vs WSH. 47% 2026 run rate. Excellent leadoff value."},
    {"player": "Bryce Harper", "team": "PHI", "opp": "CIN",
     "prop": "Runs", "line": "o0.5", "odds": "-128",
     "matchupEdge": "Harper vs CIN (4-game run streak, A- grade)", "streak": "4",
     "pick": "OVER 0.5", "confidence": "83%",
     "rationale": "4-game run streak. 51% 2026 rate. A- matchup grade vs CIN."},

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
    {"player": "F. Freeman", "team": "LAD", "opp": "SD",
     "prop": "Hits", "line": "o0.5", "odds": "-220",
     "matchupEdge": "Outlier Trend: F. Freeman Over 0.5 Hits", "streak": "4",
     "pick": "OVER 0.5", "confidence": "90%",
     "rationale": "Outlier parlay leg: covered in 4 of last 4 games (100%)."},
    {"player": "A. Pages", "team": "LAD", "opp": "SD",
     "prop": "Hits", "line": "o0.5", "odds": "-150",
     "matchupEdge": "Outlier Trend: A. Pages Over 0.5 Hits", "streak": "4",
     "pick": "OVER 0.5", "confidence": "85%",
     "rationale": "Outlier parlay leg: covered in 4 of last 4 games (100%)."},
    {"player": "A. Pages", "team": "LAD", "opp": "SD",
     "prop": "Total Bases", "line": "o0.5", "odds": "-180",
     "matchupEdge": "Outlier Trend: A. Pages Over 0.5 TB", "streak": "4",
     "pick": "OVER 0.5", "confidence": "85%",
     "rationale": "Outlier parlay leg: covered in 4 of last 4 games (100%)."},
    {"player": "S. Ohtani", "team": "LAD", "opp": "SD",
     "prop": "Total Bases", "line": "o1.5", "odds": "+110",
     "matchupEdge": "Outlier Trend: S. Ohtani Over 1.5 TB", "streak": "4",
     "pick": "OVER 1.5", "confidence": "80%",
     "rationale": "Outlier parlay leg: covered in 4 of last 4 games (100%)."},
    {"player": "X. Edwards", "team": "MIA", "opp": "ATL",
     "prop": "Hits", "line": "o0.5", "odds": "-235",
     "matchupEdge": "Outlier Trend: X. Edwards Over 0.5 Hits", "streak": "4",
     "pick": "OVER 0.5", "confidence": "95%",
     "rationale": "Outlier Trend: covered in 4 of last 4 games and 5/5 home/away (100%)."},
    {"player": "S. Basallo", "team": "BAL", "opp": "TB",
     "prop": "Hits", "line": "o0.5", "odds": "-140",
     "matchupEdge": "Outlier Trend: S. Basallo Over 0.5 Hits", "streak": "4",
     "pick": "OVER 0.5", "confidence": "90%",
     "rationale": "Outlier Trend: covered in 4 of last 4 games and 5/5 home/away (100%)."},
    {"player": "Spencer Steer", "team": "CIN", "opp": "PHI",
     "prop": "Hits", "line": "o0.5", "odds": "-150",
     "matchupEdge": "Outlier Trend: S. Steer Over 0.5 Hits", "streak": "4",
     "pick": "OVER 0.5", "confidence": "90%",
     "rationale": "Outlier Trend: covered in 4 of last 4 games and 5/5 home/away (100%)."},
    {"player": "J. Wood", "team": "WSH", "opp": "NYM",
     "prop": "Hits", "line": "o0.5", "odds": "-150",
     "matchupEdge": "Outlier Trend: J. Wood Over 0.5 Hits", "streak": "4",
     "pick": "OVER 0.5", "confidence": "85%",
     "rationale": "Outlier Trend: covered in 4 of last 4 games and 5/5 home/away (100%)."},
    {"player": "C. Mayo", "team": "BAL", "opp": "TB",
     "prop": "Hits", "line": "o0.5", "odds": "+105",
     "matchupEdge": "Outlier Trend: C. Mayo Over 0.5 Hits", "streak": "4",
     "pick": "OVER 0.5", "confidence": "80%",
     "rationale": "Outlier Trend: covered in 4 of last 4 games and 5/5 home/away (100%). Plus-money value."},
    {"player": "C. Norby", "team": "BAL", "opp": "TB",
     "prop": "Total Bases", "line": "o0.5", "odds": "-160",
     "matchupEdge": "Outlier Trend: C. Norby Over 0.5 TB", "streak": "4",
     "pick": "OVER 0.5", "confidence": "85%",
     "rationale": "Outlier Trend: covered in 4 of last 4 games and 4/4 against opponent (100%)."},
    {"player": "CJ Abrams", "team": "WSH", "opp": "NYM",
     "prop": "Total Bases", "line": "o0.5", "odds": "-190",
     "matchupEdge": "Outlier Trend: CJ Abrams Over 0.5 TB", "streak": "4",
     "pick": "OVER 0.5", "confidence": "90%",
     "rationale": "Outlier Trend: covered in 4 of last 4 games and 4/4 against opponent (100%)."},
    {"player": "M. Busch", "team": "CHC", "opp": "MIL",
     "prop": "Total Bases", "line": "o0.5", "odds": "-140",
     "matchupEdge": "Outlier Trend: M. Busch Over 0.5 TB", "streak": "4",
     "pick": "OVER 0.5", "confidence": "85%",
     "rationale": "Outlier Trend: covered in 4 of last 4 games and 4/4 against opponent (100%)."},
    {"player": "K. Ruiz", "team": "WSH", "opp": "NYM",
     "prop": "Total Bases", "line": "o0.5", "odds": "-145",
     "matchupEdge": "Outlier Trend: K. Ruiz Over 0.5 TB", "streak": "4",
     "pick": "OVER 0.5", "confidence": "80%",
     "rationale": "Outlier Trend: covered in 4 of last 4 games and 4/4 against opponent (100%)."},
    {"player": "X. Edwards", "team": "MIA", "opp": "ATL",
     "prop": "Total Bases", "line": "o0.5", "odds": "-240",
     "matchupEdge": "Outlier Trend: X. Edwards Over 0.5 TB", "streak": "4",
     "pick": "OVER 0.5", "confidence": "95%",
     "rationale": "Outlier Trend: covered in 4 of last 4 games and 5/5 home/away (100%)."},
    {"player": "Spencer Steer", "team": "CIN", "opp": "PHI",
     "prop": "Total Bases", "line": "o0.5", "odds": "-180",
     "matchupEdge": "Outlier Trend: S. Steer Over 0.5 TB", "streak": "4",
     "pick": "OVER 0.5", "confidence": "90%",
     "rationale": "Outlier Trend: covered in 4 of last 4 games and 5/5 home/away (100%)."},
    {"player": "J. Wood", "team": "WSH", "opp": "NYM",
     "prop": "Total Bases", "line": "o0.5", "odds": "-180",
     "matchupEdge": "Outlier Trend: J. Wood Over 0.5 TB", "streak": "4",
     "pick": "OVER 0.5", "confidence": "85%",
     "rationale": "Outlier Trend: covered in 4 of last 4 games and 5/5 home/away (100%)."},
]

# ============================================================
#  PITCHING PROPS — 05/19/2026
# ============================================================
PITCHING_PROPS = [
    {"player": "Nolan McLean", "team": "NYM", "opp": "WSH",
     "prop": "Strikeouts", "line": "o5.5", "odds": "-229",
     "matchupEdge": "McLean vs WSH (7-K streak, 100% H2H, B grade)", "streak": "7",
     "pick": "OVER 5.5", "confidence": "96%",
     "rationale": "[LOCK] 89% 2026 rate. 88% 2025 rate. 7-game K streak. 100% H2H vs WSH."},
    {"player": "Parker Messick", "team": "CLE", "opp": "DET",
     "prop": "Strikeouts", "line": "o5.5", "odds": "-140",
     "matchupEdge": "Messick vs DET (4-K streak, 100% H2H, B+ grade)", "streak": "4",
     "pick": "OVER 5.5", "confidence": "93%",
     "rationale": "[LOCK] 67% 2026 rate. 100% H2H vs DET. 4-game K streak."},
    {"player": "Dylan Cease", "team": "TOR", "opp": "NYY",
     "prop": "Strikeouts", "line": "o7.5", "odds": "-112",
     "matchupEdge": "Cease vs NYY (100% H2H, A- grade)", "streak": "2",
     "pick": "OVER 7.5", "confidence": "91%",
     "rationale": "[LOCK] 100% H2H vs NYY. 56% 2026 rate. High line, but H2H is perfect."},
    {"player": "Emmet Sheehan", "team": "LAD", "opp": "SD",
     "prop": "Strikeouts", "line": "o5.5", "odds": "-128",
     "matchupEdge": "Sheehan vs SD (4-K streak, 100% H2H, B- grade)", "streak": "4",
     "pick": "OVER 5.5", "confidence": "88%",
     "rationale": "75% 2026 rate. 100% H2H vs SD. 4-game K streak. Reliable."},
    {"player": "Will Warren", "team": "NYY", "opp": "TOR",
     "prop": "Strikeouts", "line": "o5.5", "odds": "+117",
     "matchupEdge": "Warren vs TOR (6-K streak, B- grade)", "streak": "6",
     "pick": "OVER 5.5", "confidence": "85%",
     "rationale": "78% 2026 rate. 6-game K streak. Plus-money (+117) on a pitcher this hot is elite value."},
    {"player": "Jacob Misiorowski", "team": "MIL", "opp": "CHC",
     "prop": "Strikeouts", "line": "o7.5", "odds": "+114",
     "matchupEdge": "Misiorowski vs CHC (5-K streak, B+ grade)", "streak": "5",
     "pick": "OVER 7.5", "confidence": "82%",
     "rationale": "78% 2026 rate. 5-game K streak. Plus-money at +114 on elite whiff rate."},
    {"player": "Jesus Luzardo", "team": "PHI", "opp": "CIN",
     "prop": "Strikeouts", "line": "o6.5", "odds": "-140",
     "matchupEdge": "Luzardo vs CIN (+0.3 edge score, B grade)", "streak": "0",
     "pick": "OVER 6.5", "confidence": "80%",
     "rationale": "56% 2026 rate. +0.3 edge score. Strong matchup advantage vs CIN bats."},

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
    {"player": "G. Sheehan", "team": "LAD", "opp": "SD",
     "prop": "Strikeouts", "line": "o5.5", "odds": "-127",
     "matchupEdge": "Outlier Trend: G. Sheehan Over 5.5 K", "streak": "4",
     "pick": "OVER 5.5", "confidence": "90%",
     "rationale": "Outlier Trend: covered in 4 of last 4 games (100%)."},
]

# ============================================================
#  ALTERNATE BATTING PROPS — 100% Hit Rate Cheatsheet 05/19/2026
# ============================================================
ALT_BATTING_PROPS = [
    {"player": "M. Garcia", "team": "NYY", "opp": "BOS",
     "prop": "H+R+RBI", "line": "o0.5", "odds": "-385",
     "matchupEdge": "12/L12 — Supreme Lock", "streak": "12",
     "pick": "OVER 0.5", "confidence": "99%",
     "rationale": "[SUPREME LOCK] 12/12 last 12 games. Longest 100% streak on the board."},
    {"player": "E. De La Cruz", "team": "CIN", "opp": "PHI",
     "prop": "H+R+RBI", "line": "o0.5", "odds": "-250",
     "matchupEdge": "11/L11 — Lock", "streak": "11",
     "pick": "OVER 0.5", "confidence": "99%",
     "rationale": "[LOCK] 11/11. Elly is on fire heading into PHI."},
    {"player": "E. De La Cruz", "team": "CIN", "opp": "PHI",
     "prop": "Total Bases", "line": "o0.5", "odds": "-215",
     "matchupEdge": "10/L10 — Lock", "streak": "10",
     "pick": "OVER 0.5", "confidence": "99%",
     "rationale": "[LOCK] 10/10 Total Bases. Near-automatic parlay piece."},
    {"player": "K. Griffin", "team": "PIT", "opp": "STL",
     "prop": "H+R+RBI", "line": "o0.5", "odds": "-362",
     "matchupEdge": "9/L9 — Lock", "streak": "9",
     "pick": "OVER 0.5", "confidence": "99%",
     "rationale": "[LOCK] 9/9. High juice but mathematically near-certain."},
    {"player": "J. Bauers", "team": "MIL", "opp": "CHC",
     "prop": "H+R+RBI", "line": "o0.5", "odds": "-225",
     "matchupEdge": "9/L9 — Lock", "streak": "9",
     "pick": "OVER 0.5", "confidence": "99%",
     "rationale": "[LOCK] 9/9. Bauers hitting in every game this stretch."},
    {"player": "A. Bohm", "team": "PHI", "opp": "CIN",
     "prop": "H+R+RBI", "line": "o0.5", "odds": "-250",
     "matchupEdge": "8/L8 — Lock", "streak": "8",
     "pick": "OVER 0.5", "confidence": "99%",
     "rationale": "[LOCK] 8/8. PHI lineup producing every night."},
    {"player": "S. Steer", "team": "CIN", "opp": "PHI",
     "prop": "H+R+RBI", "line": "o0.5", "odds": "-247",
     "matchupEdge": "8/L8 — Lock", "streak": "8",
     "pick": "OVER 0.5", "confidence": "99%",
     "rationale": "[LOCK] 8/8. Steer is an automatic H+R+RBI machine right now."},
    {"player": "W. Warren", "team": "NYY", "opp": "TOR",
     "prop": "Strikeouts", "line": "o3.5", "odds": "-400",
     "matchupEdge": "8/L8 K streak — Lock", "streak": "8",
     "pick": "OVER 3.5", "confidence": "99%",
     "rationale": "[LOCK] 8/8. Warren strikes out 3+ in every recent start."},
    {"player": "B. Baty", "team": "NYM", "opp": "WSH",
     "prop": "H+R+RBI", "line": "o0.5", "odds": "-215",
     "matchupEdge": "6/L6 — Lock", "streak": "6",
     "pick": "OVER 0.5", "confidence": "99%",
     "rationale": "[LOCK] 6/6. NYM offense rolling, Baty contributing every night."},
    {"player": "J. Soto", "team": "NYM", "opp": "WSH",
     "prop": "H+R+RBI", "line": "o0.5", "odds": "-400",
     "matchupEdge": "4/L4 — Lock", "streak": "4",
     "pick": "OVER 0.5", "confidence": "99%",
     "rationale": "[LOCK] 4/4. Soto is the anchor. Heavy juice but automatic."},
]

def chunk(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def build_bat_embed(p):
    is_lock = int(p["confidence"].replace("%", "")) >= 90
    color = COLORS["lock"] if is_lock else COLORS["player_bat"]
    return {
        "title": f"⚾  {p['player']} ({p['team']})  vs  {p['opp']}",
        "color": color,
        "fields": [
            {"name": "Prop Line", "value": f"`{p['prop']}`  |  `{p['line']}`", "inline": True},
            {"name": "Odds", "value": f"`{p['odds']}`", "inline": True},
            {"name": "⚡ Matchup Edge", "value": f"{p['matchupEdge']}", "inline": False},
            {"name": f"{'🔒 LOCK' if is_lock else '🎯 THE PICK'} — {p['pick']}",
             "value": f"**Confidence:** `{p['confidence']}`\n{p['rationale']}",
             "inline": False},
        ],
        "footer": {"text": f"Trishula Swarm | Batting Props | {SLATE_DATE}"}
    }

def build_pit_embed(p):
    is_lock = int(p["confidence"].replace("%", "")) >= 90
    color = COLORS["lock"] if is_lock else COLORS["player_pit"]
    return {
        "title": f"🎯  {p['player']} ({p['team']})  vs  {p['opp']}",
        "color": color,
        "fields": [
            {"name": "Prop Line", "value": f"`{p['prop']}`  |  `{p['line']}`", "inline": True},
            {"name": "Odds", "value": f"`{p['odds']}`", "inline": True},
            {"name": "🔬 Matchup Edge", "value": f"{p['matchupEdge']}", "inline": False},
            {"name": f"{'🔒 LOCK' if is_lock else '🎯 THE PICK'} — {p['pick']}",
             "value": f"**Confidence:** `{p['confidence']}`\n{p['rationale']}",
             "inline": False},
        ],
        "footer": {"text": f"Trishula Swarm | Pitching Props | {SLATE_DATE}"}
    }

def build_alt_bat_embed(p):
    is_lock = int(p["confidence"].replace("%", "")) >= 90
    color = COLORS["lock"] if is_lock else 15277667   # Magenta for Alt Batting
    return {
        "title": f"⚡  {p['player']} ({p['team']})  vs  {p['opp']} — ALT PROP",
        "color": color,
        "fields": [
            {"name": "Alt Prop Line", "value": f"`{p['prop']}`  |  `{p['line']}`", "inline": True},
            {"name": "Odds", "value": f"`{p['odds']}`", "inline": True},
            {"name": "⚡ Matchup Edge", "value": f"{p['matchupEdge']}", "inline": False},
            {"name": f"{'🔒 LOCK' if is_lock else '🎯 THE PICK'} — {p['pick']}",
             "value": f"**Confidence:** `{p['confidence']}`\n{p['rationale']}",
             "inline": False},
        ],
        "footer": {"text": f"Trishula Swarm | Alt Batting Props | {SLATE_DATE}"}
    }

def post_embeds(embeds, content=""):
    for batch in chunk(embeds, 10):
        payload = {**SWARM_IDENTITY, "content": content, "embeds": batch}
        r = requests.post(WEBHOOK, json=payload)
        if r.status_code in [200, 204]:
            print(f"  [OK] Batch dispatched ({len(batch)} embeds)")
        else:
            print(f"  [ERR] {r.status_code}: {r.text}")
        time.sleep(2)
        content = ""

# ============================================================
# HTML Generation
# ============================================================
def export_html():
    file_path = fr"H:\Trishula_SBM\DataMine\MLB\Team Props\05_18_2026\mlb_player_props_{date.today().strftime('%m%d%Y')}.html"
    
    html_content = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>⚾ MLB Trishula Player Props — {SLATE_DATE}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#0d1117;color:#e6edf3;font-family:'Inter',sans-serif;padding:32px;min-height:100vh}}
h1{{font-size:2.2rem;font-weight:900;margin-bottom:8px;text-transform:uppercase;letter-spacing:1px;background:-webkit-linear-gradient(45deg, #ff7b72, #58a6ff);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.meta{{color:#8b949e;font-size:0.9rem;margin-bottom:24px;font-weight:600}}
.tabs{{display:flex;gap:12px;margin-bottom:24px;border-bottom:1px solid rgba(255,255,255,0.1);padding-bottom:12px}}
.tab{{background:rgba(255,255,255,0.05);color:#8b949e;padding:10px 20px;border-radius:8px;font-weight:700;cursor:pointer;transition:all 0.2s}}
.tab.active{{background:rgba(255,123,114,0.15);color:#ff7b72;border:1px solid rgba(255,123,114,0.3)}}
#tab-pit.active{{background:rgba(88,166,255,0.15);color:#58a6ff;border:1px solid rgba(88,166,255,0.3)}}
#tab-alt-bat.active{{background:rgba(232,67,147,0.15);color:#e84393;border:1px solid rgba(232,67,147,0.3)}}

/* SPREADSHEET TABLE DESIGN */
table {{width: 100%; border-collapse: separate; border-spacing: 0 8px;}}
th {{text-align: left; padding: 12px 16px; color: #8b949e; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px; font-weight: 700; border-bottom: 1px solid rgba(255,255,255,0.1);}}
td {{padding: 16px; background: rgba(22, 27, 34, 0.8); border-top: 1px solid rgba(255,255,255,0.05); border-bottom: 1px solid rgba(255,255,255,0.05); vertical-align: middle;}}
td:first-child {{border-left: 1px solid rgba(255,255,255,0.05); border-top-left-radius: 8px; border-bottom-left-radius: 8px; border-left: 4px solid rgba(255,255,255,0.1);}}
td:last-child {{border-right: 1px solid rgba(255,255,255,0.05); border-top-right-radius: 8px; border-bottom-right-radius: 8px;}}

/* ROW HIGHLIGHTS (LOCKS) */
tr.lock td {{background: rgba(240, 192, 64, 0.08); border-top-color: rgba(240, 192, 64, 0.2); border-bottom-color: rgba(240, 192, 64, 0.2);}}
tr.lock td:first-child {{border-left: 4px solid #f0c040;}}
tr.lock td:last-child {{border-right-color: rgba(240, 192, 64, 0.2);}}

/* DATA CELLS */
.player-name {{font-size: 1.1rem; font-weight: 900; color: #ffffff; margin-bottom: 2px; display: block;}}
.team-matchup {{font-size: 0.75rem; color: #8b949e; font-weight: 600; text-transform: uppercase;}}
.prop-type {{font-size: 0.85rem; color: #c9d1d9; font-weight: 700;}}
.line-val {{font-size: 1.1rem; font-weight: 900; color: #ffffff;}}
.odds-badge {{padding: 4px 8px; border-radius: 4px; font-size: 0.85rem; font-weight: 800; display: inline-block; margin-left: 6px;}}
.odds-pos {{background: rgba(63,185,80,0.15); color: #3fb950; border: 1px solid rgba(63,185,80,0.3);}}
.odds-neg {{background: rgba(255,123,114,0.15); color: #ff7b72; border: 1px solid rgba(255,123,114,0.3);}}
.pick-text {{font-size: 1.0rem; font-weight: 900; color: #58a6ff;}}
tr.lock .pick-text {{color: #f0c040;}}
.conf-text {{font-size: 0.85rem; font-weight: 900; color: #3fb950;}}
.rationale-text {{font-size: 0.75rem; color: #8b949e; font-style: italic; line-height: 1.4; max-width: 250px;}}

.hidden {{ display: none !important; }}
</style></head><body>

<h1>⚾ Trishula Player Props Dashboard</h1>
<p class="meta">Premium Social Intelligence Spreadsheet · Batting, Pitching & Alt Props · {SLATE_DATE}</p>

<div class="tabs">
  <div class="tab active" id="tab-bat" onclick="switchTab('bat')">BATTING PROPS</div>
  <div class="tab" id="tab-pit" onclick="switchTab('pit')">PITCHING PROPS</div>
  <div class="tab" id="tab-alt-bat" onclick="switchTab('alt-bat')">ALT BATTING PROPS</div>
</div>

<div id="games-bat">
  <table>
    <thead><tr><th>Player & Matchup</th><th>Prop</th><th>Line / Odds</th><th>The Pick</th><th>Analysis</th></tr></thead>
    <tbody id="tbody-bat"></tbody>
  </table>
</div>
<div id="games-pit" class="hidden">
  <table>
    <thead><tr><th>Player & Matchup</th><th>Prop</th><th>Line / Odds</th><th>The Pick</th><th>Analysis</th></tr></thead>
    <tbody id="tbody-pit"></tbody>
  </table>
</div>
<div id="games-alt-bat" class="hidden">
  <table>
    <thead><tr><th>Player & Matchup</th><th>Prop</th><th>Line / Odds</th><th>The Pick</th><th>Analysis</th></tr></thead>
    <tbody id="tbody-alt-bat"></tbody>
  </table>
</div>

<script>
const BAT = {json.dumps(BATTING_PROPS)};
const PIT = {json.dumps(PITCHING_PROPS)};
const ALT_BAT = {json.dumps(ALT_BATTING_PROPS)};

function getOddsClass(odds) {{
  if(!odds) return '';
  if(odds.includes('+')) return 'odds-pos';
  if(odds.includes('-')) return 'odds-neg';
  return '';
}}

function renderTable(data, tbodyId) {{
  const tbody = document.getElementById(tbodyId);
  data.forEach((p)=>{{
    const confInt = parseInt(p.confidence.replace('%',''));
    const isLock = confInt >= 90;
    const lockClass = isLock ? 'lock' : '';

    tbody.innerHTML += `
    <tr class="${{lockClass}}">
      <td>
        <span class="player-name">${{p.player}}</span>
        <span class="team-matchup">${{p.team}} vs ${{p.opp}}</span>
      </td>
      <td><span class="prop-type">${{p.prop}}</span></td>
      <td>
        <span class="line-val">${{p.line}}</span>
        <span class="odds-badge ${{getOddsClass(p.odds)}}">${{p.odds}}</span>
      </td>
      <td>
        <span class="pick-text">${{p.pick}}</span><br>
        <span class="conf-text">${{p.confidence}} Edge</span>
      </td>
      <td><div class="rationale-text">${{p.rationale}}</div></td>
    </tr>`;
  }});
}}

function switchTab(tabId) {{
  document.getElementById('tab-bat').classList.remove('active');
  document.getElementById('tab-pit').classList.remove('active');
  document.getElementById('tab-alt-bat').classList.remove('active');
  document.getElementById('games-bat').classList.add('hidden');
  document.getElementById('games-pit').classList.add('hidden');
  document.getElementById('games-alt-bat').classList.add('hidden');
  document.getElementById('tab-' + tabId).classList.add('active');
  document.getElementById('games-' + tabId).classList.remove('hidden');
}}

renderTable(BAT, 'tbody-bat');
renderTable(PIT, 'tbody-pit');
renderTable(ALT_BAT, 'tbody-alt-bat');
</script></body></html>"""

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"  [OK] Generated HTML: {file_path}")
    return file_path

# ============================================================
# Playwright Screenshot & Discord Image Upload
# ============================================================
def post_html_screenshot(html_path):
    import time
    from playwright.sync_api import sync_playwright
    
    bat_png_path = html_path.replace(".html", "_batting.png")
    pit_png_path = html_path.replace(".html", "_pitching.png")
    alt_bat_png_path = html_path.replace(".html", "_alt_batting.png")
    
    print("  [WAIT] Booting Headless Browser to screenshot Player Props tabs...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 900, "height": 1000})
        page.goto(f"file:///{html_path.replace(chr(92), '/')}") 
        time.sleep(2)
        
        # Screenshot Batting Props
        page.screenshot(path=bat_png_path, full_page=True)
        print(f"  [OK] Saved Batting PNG: {bat_png_path}")
        
        # Switch to Pitching Props Tab
        page.click("#tab-pit")
        time.sleep(1)
        
        # Screenshot Pitching Props
        page.screenshot(path=pit_png_path, full_page=True)
        print(f"  [OK] Saved Pitching PNG: {pit_png_path}")

        # Switch to Alt Batting Props Tab
        page.click("#tab-alt-bat")
        time.sleep(1)
        
        # Screenshot Alt Batting Props
        page.screenshot(path=alt_bat_png_path, full_page=True)
        print(f"  [OK] Saved Alt Batting PNG: {alt_bat_png_path}")
        
        browser.close()
        
    print("  [WAIT] Uploading Images to Discord Webhook...")
    for png in [bat_png_path, pit_png_path, alt_bat_png_path]:
        with open(png, "rb") as f:
            files = {"file": (png.split("\\")[-1], f, "image/png")}
            payload = {"content": f"**SOCIAL MEDIA ASSET READY**\nGenerated `{png.split(chr(92))[-1]}`"}
            r = requests.post(WEBHOOK, data=payload, files=files)
            if r.status_code in [200, 204]:
                print(f"  [OK] {png.split(chr(92))[-1]} uploaded to Discord successfully.")
            else:
                print(f"  [ERR] Failed to upload image: {r.status_code} {r.text}")


def dispatch():
    print("\n" + "="*55)
    print("  TRISHULA SWARM -- MLB PLAYER PROPS DISPATCH")
    print(f"  {SLATE_DATE}")
    print("="*55 + "\n")

    # Try loading dynamic slate data from today's ODS dump
    global BATTING_PROPS, PITCHING_PROPS, ALT_BATTING_PROPS
    import os, json
    RAW_DATE = date.today().strftime("%m_%d_%Y")
    JSON_PATH = fr"H:\Trishula_SBM\DataMine\MLB\Team Props\{RAW_DATE}\player_slate_{RAW_DATE}.json"
    if os.path.exists(JSON_PATH):
        try:
            with open(JSON_PATH, "r", encoding="utf-8") as f:
                dynamic_data = json.load(f)
                BATTING_PROPS = dynamic_data.get("BATTING_PROPS", BATTING_PROPS)
                PITCHING_PROPS = dynamic_data.get("PITCHING_PROPS", PITCHING_PROPS)
                ALT_BATTING_PROPS = dynamic_data.get("ALT_BATTING_PROPS", ALT_BATTING_PROPS)
                print(f"[OK] Dynamically loaded {len(BATTING_PROPS)} Batting, {len(PITCHING_PROPS)} Pitching, {len(ALT_BATTING_PROPS)} Alt Batting Props from {JSON_PATH}")
        except Exception as e:
            print(f"[WARN] Failed to load dynamic JSON player slate: {e}")


    # print("Dispatching Batting Props...")
    # bat_embeds = [build_bat_embed(p) for p in BATTING_PROPS]
    # post_embeds(bat_embeds, content=f"**MLB BATTING PROPS -- {SLATE_DATE.upper()}**\nTrishula Intelligence Output")

    # time.sleep(3)

    # print("\nDispatching Pitching Props...")
    # pit_embeds = [build_pit_embed(p) for p in PITCHING_PROPS]
    # post_embeds(pit_embeds, content=f"**MLB PITCHING PROPS -- {SLATE_DATE.upper()}**\nTrishula Intelligence Output")

    # time.sleep(3)

    # print("\nDispatching Alternate Batting Props...")
    # alt_bat_embeds = [build_alt_bat_embed(p) for p in ALT_BATTING_PROPS]
    # post_embeds(alt_bat_embeds, content=f"**MLB ALTERNATE BATTING PROPS -- {SLATE_DATE.upper()}**\nHigh Variance / Alt Lines Intelligence")

    # print("\n[DONE] Full Player Props slate dispatched successfully.\n")

    # Generate HTML automatically & post screenshots
    html_file = export_html()
    post_html_screenshot(html_file)

if __name__ == "__main__":
    dispatch()
