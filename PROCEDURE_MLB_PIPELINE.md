# TRISHULA DOCTRINE — UNIVERSAL SBM PIPELINE PROCEDURE
# Classification: SOVEREIGN OPERATIONAL STANDARD — BASELINE
# Status: ACTIVE | Revision: 1.1
# Issued: 2026-05-17 | Author: Antigravity / War Machine
#
# SCOPE: This document is the governing baseline for ALL sports
# and ALL model prop types operated under the Trishula Swarm.
# MLB was the first module. Every sport that follows inherits
# this exact structure, discipline, and accountability standard.
# Deviation from this baseline requires a formal doctrine update.

==============================================================
## PROCEDURE: MLB — DAILY DATA INGESTION & DISPATCH
## (BASELINE TEMPLATE — APPLIES TO ALL SPORTS)
==============================================================

### OVERVIEW
One run per day. No exceptions. Full accountability.
The Trishula Edge is not a system of guesses — it is a 
sovereign intelligence model operating under strict doctrine,
clear pick logic, and an immutable ledger of record.

==============================================================
## SECTION 1 — DATA COLLECTION (Human Execution)
==============================================================

SOURCE: https://www.actionnetwork.com/mlb/props

TIMING:
  - Run no earlier than 11:00 PM the night before game day.
  - Ensures all lines, markets, and props have settled for
    the following day's slate.
  - New Jersey (ET) timezone is the reference clock.

SETTINGS:
  - Market Filter: "All Markets"
  - Market View: Start at "Game" tab

SCREENSHOT PROTOCOL (per game, in order):
  Step 1. Scroll to Game tab → "All Markets"
          Screenshot every game section top to bottom.
          Capture: Moneyline, Spread, Total (O/U)

  Step 2. Click dropdown → Select "1st Inning"
          Screenshot every game section (YRFI/NRFI lines).

  Step 3. Click dropdown → Select "F5" (First 5 Innings)
          Screenshot every game section (F5 ML + Run Lines).

  * Each screenshot must capture the full game row including
    both teams, opening line, best odds, and book columns.
  * Do NOT skip partial rows or cut off the bottom of a game.

OUTPUT (TEAM PROPS):
  - All screenshots pasted into a single ODS spreadsheet file.
  - Naming convention: MM_DD_YYYY_team_main.ods
  - Saved to dated subdirectory: H:\Trishula_SBM\DataMine\MLB\Team Props\MM_DD_YYYY\

OUTPUT (PLAYER PROPS):
  - Batting Props: MM_DD_YYYY player batting props.ods
  - Pitching Props: MM_DD_YYYY player pitching props.ods
  - Alt Batting Props: MM_DD_YYYY alt player batting props.ods
  - Saved to dated subdirectory: H:\Trishula_SBM\DataMine\MLB\Team Props\MM_DD_YYYY\

==============================================================
## SECTION 2 — SWARM INGESTION (Machine Execution)
==============================================================

TRIGGER: Human drops new ODS into DataMine directory.

SWARM ACTIONS (automated sequence):
  1. Extract embedded images from ODS (ZIP extraction)
  2. Parse all screenshots: Game props, 1st Inning, F5 lines
  3. Populate BASE_GAMES and ALT_GAMES arrays
  4. Apply Trishula Edge Detection logic per game:
       - Homefield Advantage (HFA) run differential
       - Head-to-Head trend (H2H last 5 / last 10)
       - Current win/loss streak
       - Starting pitcher matchup edge
       - Weather / park factors
       - Sharp money signal (where available)
  5. Generate Trishula Edge Pick per game (Base + Alt)
  6. Render mlb_unified_props_MMDDYYYY.html  (props dashboard)
  7. Render mlb_parlays_MMDDYYYY.html        (parlay dashboard)
  8. Render mlb_player_props_MMDDYYYY.html   (player props dashboard)
  9. Execute Headless Browser (Playwright) to capture PNG screenshots of all tabs.
  10. Execute discord_dispatch.py  -- fire Team Props to #mlb-team-props
  11. Execute parlay_generator.py  -- fire parlays to dedicated parlay channel
  12. Execute player_props_dispatch.py -- fire Player Props to dedicated player props channel

FREQUENCY: ONCE PER DAY. No repeat dispatches.

SPORT MODULES (inheriting this baseline):
  [ACTIVE]   MLB  — Team Props / F5 / 1st Inning
  [ACTIVE]   MLB  — Player Props (Batting / Pitching)
  [PENDING]  NBA  — Team Totals / Player Props / 1st Qtr
  [PENDING]  NFL  — Team Totals / Player Props / 1st Half
  [PENDING]  NCAAB — Team Totals / Player Props
  [PENDING]  NCAAF — Team Totals / Player Props
  [PENDING]  NHL  — Puck Line / Team Totals / Period Props
  [PENDING]  MODEL PROPS — Swarm-generated custom prop models

  Each new sport module follows this exact ingestion →
  analysis → dispatch → ledger flow. The data source,
  screenshot protocol, and ODS format remain identical.
  Only sport-specific market names and prop types change.

==============================================================
## SECTION 3 — DISCORD OUTPUT FORMAT
==============================================================

CHANNEL: #mlb-team-props
  Block 1 — BASE PROPS (Game ML / Spread / Total)
    - Full daily slate (game count varies by sport/day)
    - Color: Purple (sovereign signal)
    - Includes: HFA, H2H, Streak, Pick, Confidence, Rationale

  Block 2 — ALTERNATE PROPS (sport-specific)
    - MLB:  F5 / 1st Inning (YRFI/NRFI)
    - NBA:  1st Quarter / 1st Half totals
    - NFL:  1st Half / player prop models
    - NHL:  Period totals / puck line alts
    - Color: Blue (alt signal)
    - Includes: Split-line odds, SP/starter edge, Weather, Pick

  Block 3 — MODEL PROPS (when Swarm-generated models are active)
    - Custom prop models generated by the Trishula intelligence layer
    - Color: Gold
    - Marked: [MODEL] tag — distinguishes from raw market picks

CHANNEL: Dedicated Parlays Channel (via mlb_parlays webhook)
  Block 4 — PARLAYS (daily, 3 structured parlays)
    - Format: 2-3 legs ONLY. No exceptions.
    - Parlay 1: LOCK TIER (highest confidence legs, favored teams)
    - Parlay 2: VALUE DOGS (plus-money underdogs, 2-leg)
    - Parlay 3: ALT PROPS (NRFI/YRFI or sport-specific 1st period)
    - Color: Gold (parlay signal)
    - Includes: Each leg with odds + confidence, combined payout
    - Payout shown at $50 / $100 / $250 / $500 bet sizes

LOCK CONDITION:
  - Any pick >= 90% confidence is auto-flagged as a LOCK
  - Color override: Gold
  - Marked with lock indicator in title

==============================================================
## SECTION 4 — THE LEDGER (Full Accountability)
==============================================================

CHANNEL: #mlb-pick-ledger
WEBHOOK: config.py → WEBHOOKS["mlb_pick_ledger"]

LEDGER TRACKS (per pick, per day):
  - Date
  - Game (Away @ Home)
  - Pick Type (ML / Run Line / Total / F5 / NRFI / YRFI / PARLAY)
  - Pick Selection
  - Odds at time of dispatch
  - Confidence %
  - Result: WIN / LOSS / PUSH / PENDING
  - Units Wagered (standardized)
  - Units Returned

  PARLAY LEDGER ENTRIES (additional fields):
  - Parlay Type (Lock / Value / Alt Props)
  - Number of Legs
  - Each leg listed individually
  - Combined odds at time of dispatch
  - Full parlay result (ALL legs must win = WIN)
  - Partial results noted (e.g. 2/3 legs hit) for model learning

LEDGER ALSO TRACKS:
  - Daily Record (W-L-P) per sport
  - Overall Record (cumulative, cross-sport)
  - Overall Units Profit/Loss (unified bankroll view)
  - Parlay tracking (separate entry per parlay leg + result)
  - LOCK pick record (tracked independently for accountability)
  - Model Pick record (MODEL PROPS tracked separately)
  - Sport-by-sport breakdown (MLB vs NBA vs NFL vs other)
  - Best performing pick type (ML / RL / Total / F5 / NRFI)
  - Best performing confidence tier (65-75% / 75-85% / 85%+)

ACCOUNTABILITY STANDARD:
  - No picks are removed retroactively.
  - No results are adjusted after the fact.
  - Every dispatch is timestamped and immutable.
  - Full Trishula Doctrine compliance: sovereign, honest,
    zero manipulation of record.

==============================================================
## SECTION 5 — GOVERNING DOCTRINE
==============================================================

This procedure operates under:
  - L0 Constitution (Trishula Sovereign Law)
  - SEPTIP-v2 Protocol (Sovereign Execution & Transparency)
  - SQA v5 ASCENDED (Quality & Accountability Standard)

Core principles enforced:
  1. ONE run per day. No redundant dispatches.
  2. All picks logged. Wins AND losses, without exception.
  3. No retroactive edits. The ledger is law.
  4. All data sourced from Action Network.
     No fabricated odds. No adjusted lines.
  5. The Swarm serves the doctrine.
     The doctrine serves the record.
     The record serves the mission.

HTML OUTPUT STANDARD (per daily run):
  mlb_unified_props_MMDDYYYY.html  -- Base + Alt Props dashboard
  mlb_parlays_MMDDYYYY.html        -- Parlay board with payout calculator

  Saved to: H:\Trishula_SBM\DataMine\[SPORT]\Team Props\

  PURPOSE (dual-use):
    1. LOCAL DASHBOARD  -- Full intelligence review before posting
    2. SOCIAL MEDIA     -- Screenshot and post directly to social
                          platforms (X, Instagram, etc.) as
                          branded Trishula intelligence cards.
                          The HTML design is intentionally
                          premium and screenshot-optimized.

  Both HTMLs include a live LEDGER TRACKING indicator
  that updates to WIN / LOSS / PUSH once results are entered.

PARLAY STANDARD (LOCKED):
  - Always 2 or 3 legs. Never more. Never fewer.
  - Always 3 parlays per slate:
      1. Lock Tier (high confidence, may include favorites)
      2. Value Dogs (plus-money, underdog focus)
      3. Alt Props (1st inning / period props)
  - Parlay leg reuse allowed but not required.
  - All parlays dispatched same day as base/alt props.
  - All parlays tracked in ledger independently.
  - Parlays have their own HTML (mlb_parlays_MMDDYYYY.html)
    which is also social-media screenshot ready.

==============================================================
## REVISION LOG
==============================================================
  v1.0 -- 2026-05-17 -- Initial sovereign procedure established.
                        MLB pipeline operational.
                        Base props + Alt props + Ledger active.

  v1.1 -- 2026-05-17 -- MLB procedure elevated to UNIVERSAL BASELINE.
                        All future sport modules inherit this structure.

  v1.2 -- 2026-05-17 -- Parlay standard added (2-3 legs, 3 parlays/day).
                        HTML files mandated as social media assets.
                        Parlay ledger tracking added to doctrine.

  v1.3 -- 2026-05-17 -- Parlays routed to their own dedicated webhook.
                        Explicit mandate added to strictly generate
                        mlb_parlays_MMDDYYYY.html every run for
                        social media continuity.

==============================================================
# END OF PROCEDURE DOCUMENT
==============================================================
