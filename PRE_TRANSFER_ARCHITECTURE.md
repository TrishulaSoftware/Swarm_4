# TRISHULA SOFTWARE — PRE-TRANSFER ARCHITECTURE BRIEF
# Generated: 2026-05-17 | Status: PLANNING PHASE (Awaiting USB Transfer)
# Author: Antigravity | Doctrine: L0 Constitution / SQA v5 ASCENDED

==============================================================
## EXECUTIVE SUMMARY
==============================================================

Three product lines converging into one Discord-native platform:
  1. Sports Betting Models (SBM) — Data pipeline + prediction engine
  2. TradingView Indicators — 10+ private indicators, subscription-gated
  3. Cloud Arbitrage v3/4.0 — Free tier infrastructure stack

Target: A self-funding, data-rich Discord server that generates
recurring subscription revenue from both SBM picks and trading
indicator access. Zero infrastructure cost via cloud arbitrage.

==============================================================
## SECTION 1 — FREE DATA SOURCE MAP (SBM)
==============================================================

Based on pre-transfer research, the following are the highest-
value free data sources confirmed available as of 2025/2026:

### SOURCE A — The Odds API
  URL: https://the-odds-api.com
  Free Tier: 500 requests/month
  Coverage: Major US sports (NFL, NBA, MLB, NHL, NCAAB, NCAAF)
  Historical: Odds back to 2020
  Sharp Books: Yes (Pinnacle included)
  Best Use: Real-time line monitoring, opening/closing line capture
  Limit Strategy: Cache aggressively. 500 req/mo = ~16/day.
    Use for closing line value (CLV) tracking, not polling.

### SOURCE B — ParlayAPI
  URL: https://parlayapi.com
  Free Tier: 100,000 credits/month
  Coverage: NFL, NBA, NCAAB, NCAAF
  Historical: 48hr depth on free + large archive (NFL/NBA)
  Best Use: High-volume polling, closing odds, historical backtest
  Limit Strategy: Primary workhorse. 100K credits = substantial
    polling capacity. Use for model training data.

### SOURCE C — nba_api (Official NBA.com interface)
  Install: pip install nba_api
  Free: Yes, completely free, no key required
  Coverage: Full NBA stats since 1946 season
  Data: Play-by-play, player stats, team stats, game logs,
    shot charts, advanced metrics
  Best Use: NBA SBM training data, player prop modeling
  Limit Strategy: Rate limit built into library. Add sleep(0.6)
    between calls to avoid 429 errors.

### SOURCE D — nflreadpy (nflverse Python port)
  Install: pip install nflreadpy
  Free: Yes, pulls from GitHub-hosted parquet files
  Coverage: NFL play-by-play back to 1999, rosters, schedules,
    injuries, next gen stats
  Best Use: NFL SBM, ATS modeling, totals modeling, player props
  Limit Strategy: No rate limits. Downloads cached parquet files.
    Run bulk downloads once, store locally.

### BONUS SOURCES (confirmed free, lower priority):
  - football-data.co.uk: Free CSV files, European football, historical
  - sportsipy/sportsreference: Scraper for Basketball-Ref, PFR, etc.
  - OddsPapi.io: 350+ bookmakers, sharp book data on free tier
  - SportsGameOdds (SGO): 80+ bookmakers, US-focused

### RECOMMENDED STACK COMBINATION:
  NBA Model:  nba_api (stats) + The Odds API (lines) + ParlayAPI (CLV)
  NFL Model:  nflreadpy (play-by-play) + ParlayAPI (bulk) + The Odds API
  Props:      nba_api player logs + ParlayAPI prop lines
  Backtest:   nflreadpy historical + football-data.co.uk archives

==============================================================
## SECTION 2 — CLOUD ARBITRAGE v3/4.0 FRAMEWORK
## (Pre-built assumptions — will be updated from transfer files)
==============================================================

### PHILOSOPHY:
  "Cloud Arbitrage" = distributing workloads across MULTIPLE
  providers' free tiers simultaneously so that NO single provider
  is burdened and NO single free tier is exceeded.
  
  This is NOT account abuse. It is legitimate multi-cloud
  architecture using each provider for what they give away free.

### FREE TIER ASSET MAP (2025/2026 confirmed):

  ORACLE CLOUD (Always Free — Best Compute)
  ├── 4x Ampere A1 ARM cores (combinable, up to 24GB RAM)
  ├── 2x AMD x86 VM (1GB RAM each)
  ├── 200GB block storage
  ├── 10GB object storage
  ├── No expiration — truly always free
  └── Best Use: PRIMARY COMPUTE — SBM model runner, cron jobs,
      Discord bot host, data pipeline orchestrator
  NOTE: Treat as disposable. Heartbeat script required to
  prevent idle reclaim. Docker + IaC for instant redeploy.

  GCP (Always Free)
  ├── 1x e2-micro (0.25 vCPU, 1GB RAM) — us-central1/us-east1/us-west1
  ├── 5GB Cloud Storage
  ├── 1M Cloud Functions invocations/month
  ├── BigQuery: 10GB storage + 1TB queries/month FREE
  ├── Cloud Run: 2M requests/month free
  └── Best Use: BigQuery as FREE data warehouse for SBM historical
      data. Cloud Functions as event triggers. Cloud Run for APIs.

  AWS (Always Free — post 12mo)
  ├── Lambda: 1M invocations/month + 400K GB-seconds compute
  ├── DynamoDB: 25GB storage + 25 WCU/RCU
  ├── SQS: 1M requests/month
  ├── SNS: 1M publishes/month
  ├── CloudWatch: 10 metrics, 10 alarms
  └── Best Use: Lambda for scheduled model runs. DynamoDB for
      pick history. SQS for job queue between components.

  CLOUDFLARE (Always Free)
  ├── Workers: 100K requests/day
  ├── Workers KV: 100K reads/day
  ├── Pages: Unlimited static sites
  ├── R2: 10GB object storage (no egress fees)
  └── Best Use: API gateway / rate limiter. R2 for storing model
      outputs and pick archives. Pages for public-facing site.

  SUPABASE (Always Free)
  ├── PostgreSQL: 500MB database
  ├── Auth: Unlimited users
  ├── Storage: 1GB
  ├── Edge Functions: 500K invocations/month
  └── Best Use: Subscriber management, Discord role tracking,
      pick history database, auth for premium content.

  RENDER (Free tier)
  ├── Web Service: 750 hours/month (one service free)
  ├── Cron Jobs: Free
  └── Best Use: Backup Discord bot host or cron scheduler.

  RAILWAY (Hobby — $5 credit/month)
  └── Best Use: Reserve for overflow or secondary bot instance.

  HUGGING FACE (Free inference)
  ├── Inference API: Free for smaller models
  └── Best Use: NLP for Discord content, sentiment analysis.

### CURRENT STATUS — TIER 1 ONLY (Live Right Now):
  A1 ARM BLOCKED: us-ashburn-1 capacity exhausted.
  Resolution: Requires second bank account → new OCI account
    in Frankfurt/Sao Paulo → A1 ARM unlocked.
  ETA: Pending. Proceed with Tier 1 assets only.

### CLOUD ARBITRAGE v3/4.0 ARCHITECTURE (TIER 1 — LIVE):

  LAYER 0 — COMPUTE (Available NOW, no A1 ARM)

    OPTION A: Oracle Always Free AMD x86 (Current Account)
      - 2x VM.Standard.E2.1.Micro (1 vCPU, 1GB RAM each)
      - Available in Ashburn RIGHT NOW (AMD, not ARM)
      - Use Case: Lightweight cron runner, data fetcher
      - Limitation: 1GB RAM per VM — not enough for full
        model training. Use for scheduling + dispatch only.

    OPTION B: GCP e2-micro (Always Free, no expiry)
      - 0.25 vCPU burst, 1GB RAM
      - Regions: us-central1, us-east1, us-west1
      - Use Case: Discord bot host (persistent process)
        Low RAM but sufficient for discord.py bot loop.
      - Advantage: Truly always free, no capacity issues.

    OPTION C: Render Free Tier (Primary Bot Host)
      - 750 hours/month web service (one service free)
      - More reliable for persistent Discord bot process
        than GCP e2-micro's burst CPU limits.
      - Use Case: Discord bot primary host (Tier 1)
      - Limitation: Spins down after 15min inactivity
        (use UptimeRobot free ping to keep alive)

    OPTION D: AWS Lambda (Serverless Compute)
      - 1M invocations/month — no persistent server needed
      - Use Case: Model inference runs (triggered on schedule)
        SBM picks generated as Lambda function calls.
      - Advantage: Scales automatically, no RAM constraint
        for burst model runs (up to 10GB RAM per function)
      - Cost: $0 within free tier limits.

  LAYER 0 RECOMMENDATION (RIGHT NOW, NO A1):
    Discord Bot → Render (persistent, reliable)
    Model Runner → AWS Lambda (scheduled, serverless)
    Data Fetcher → Oracle AMD x86 VM (cron, lightweight)
    Keep-alive → UptimeRobot free tier pings Render

  LAYER 0 UPGRADE PATH (When A1 ARM unlocked):
    Migrate ALL of the above onto single A1 ARM instance
    (4 OCPUs / 24GB RAM handles everything in one place)

  LAYER 1 — DATA WAREHOUSE (GCP BigQuery)
    - Historical odds database (free 10GB)
    - Model training data (nba_api, nflreadpy exports)
    - Pick performance tracking
    - CLV analysis tables

  LAYER 2 — EVENT BUS (AWS Lambda + SQS)
    - Scheduled triggers for model runs
    - Queue for Discord webhook dispatch
    - Serverless API endpoints for subscriber queries

  LAYER 3 — EDGE / DELIVERY (Cloudflare Workers + R2)
    - API rate limiting gateway
    - Pick archive storage (R2)
    - Public-facing pick history page (Pages)

  LAYER 4 — DATABASE (Supabase PostgreSQL)
    - Subscriber records
    - Discord user → tier mapping
    - Pick log with outcomes
    - Model performance metrics

  LAYER 5 — DISCORD (discord.py bot)
    - Webhook dispatch for automated picks
    - Slash commands for subscriber queries
    - Role-gated channel access
    - Embed-formatted pick cards

==============================================================
## SECTION 3 — DISCORD SERVER ARCHITECTURE
==============================================================

### SERVER STRUCTURE (Proposed):

  TRISHULA SOFTWARE DISCORD
  │
  ├── 📢 ANNOUNCEMENTS
  │   ├── #welcome
  │   ├── #server-rules
  │   └── #updates
  │
  ├── 🎯 SPORTS BETTING MODELS (Gated — Paid Role)
  │   ├── #sbm-nba-picks          ← Automated bot posts
  │   ├── #sbm-nfl-picks          ← Automated bot posts
  │   ├── #sbm-props              ← Automated bot posts
  │   ├── #model-performance      ← Win/loss tracking
  │   └── #sbm-discussion
  │
  ├── 📈 TRADING INDICATORS (Gated — Paid Role)
  │   ├── #starfall-signals       ← Starfall webhook alerts
  │   ├── #indicator-library      ← All 10 writeups posted
  │   ├── #chart-analysis
  │   └── #indicator-discussion
  │
  ├── 🆓 FREE ZONE (Public)
  │   ├── #free-picks-preview     ← 1 delayed pick/day free
  │   ├── #market-talk
  │   └── #general
  │
  └── ⚙️ ADMIN (Private)
      ├── #bot-logs
      ├── #model-outputs-raw
      └── #revenue-tracking

### SUBSCRIPTION TIERS (Proposed):

  FREE
    - #free-picks-preview (1 delayed pick/day)
    - #general, #market-talk
    - View indicator descriptions (no access)

  SBM TIER — $49/mo
    - All SBM channels (NBA, NFL, Props)
    - Model performance tracking
    - Historical pick log

  INDICATORS TIER — $99/mo  
    - All trading indicator channels
    - Starfall live signals
    - Full indicator documentation

  FULL ARSENAL — $149/mo
    - Everything: SBM + Indicators
    - Priority support
    - Early access to new models/indicators

### DISCORD BOT STACK:

  Primary Bot (discord.py):
    - Slash commands: /picks, /record, /subscribe, /model-stats
    - Role assignment on Stripe webhook payment confirmation
    - Embed-formatted pick cards with color coding:
        GREEN = model bet (value identified)
        YELLOW = lean (lower confidence)
        RED = fade alert (model strongly against)
    - Auto-post picks on schedule (pre-game)
    - Auto-update pick outcomes post-game

  Webhook Layer (discord-webhook):
    - Starfall alerts → Trading channel
    - Model outputs → SBM channels
    - Performance updates → #model-performance

==============================================================
## SECTION 4 — SBM MODEL ARCHITECTURE
==============================================================

### MODEL TYPES (Initial):

  MODEL 1 — NBA ATS (Against The Spread)
    Data: nba_api (team stats, pace, efficiency)
    Odds: ParlayAPI (opening + closing lines)
    Features: Offensive/Defensive rating delta, rest days,
      home/away, travel distance, back-to-back, line movement
    Target: Cover/No Cover
    Validation: CLV (closing line value) tracking

  MODEL 2 — NBA Totals (Over/Under)
    Data: nba_api (pace, true shooting%, possessions)
    Odds: ParlayAPI + The Odds API
    Features: Combined pace, ORtg + DRtg, weather (irrelevant
      for NBA), referee tendencies (via historical totals)
    Target: Over/Under

  MODEL 3 — NFL ATS
    Data: nflreadpy (EPA, DVOA proxies, situational stats)
    Odds: ParlayAPI historical + The Odds API live
    Features: EPA/play differential, turnover margin, special
      teams efficiency, coaching tendencies, weather
    Target: Cover/No Cover

  MODEL 4 — NFL Totals
    Data: nflreadpy (pace, play count, time of possession)
    Features: Offensive tempo, defensive DVOA proxy, wind speed
    Target: Over/Under

  MODEL 5 — Player Props (Phase 2)
    Data: nba_api (player game logs, matchup data)
    Odds: ParlayAPI prop lines
    Features: Usage rate, matchup defensive rating,
      recent form, minutes projection

### MODEL PIPELINE:

  [DATA FETCH] → [FEATURE ENGINEERING] → [MODEL INFERENCE]
       ↓                  ↓                      ↓
  nba_api/nflreadpy   pandas/numpy          scikit-learn /
  ParlayAPI/OddsAPI   cached parquet        XGBoost / LR
       ↓                  ↓                      ↓
  [CONFIDENCE FILTER] → [VALUE CHECK vs LINE] → [DISCORD POST]
  (threshold: >55%)   (EV positive only)      (discord-webhook)

### QUALITY GATES:
  - No pick posted below 55% model confidence
  - No pick posted without confirmed line from sharp book
  - CLV tracking mandatory — every pick logged with
    opening line, closing line, result, CLV delta
  - Model performance dashboard updated daily in Discord

==============================================================
## SECTION 5 — INTEGRATION WITH EXISTING TRISHULA STACK
==============================================================

### EXISTING ASSETS THAT PLUG IN DIRECTLY:

  send_wave1.py       → Outreach to Discord server recruiting
  trishula_storefront.md → Trading indicators copy (already done)
  Security-Janitor    → Audit CI for bot code
  Constitutional AI   → VetoGate on any model outputs
  pqc_interlock.py    → Sign model outputs for integrity
  RESULTS.md          → Social proof for Discord server credibility
  Wave 1 send log     → 61 targets already in pipeline, Discord
                         server link can be added to follow-ups

### NEW COMPONENTS NEEDED (Post-Transfer):

  sbm_pipeline/
  ├── fetch_nba.py          ← nba_api data fetcher
  ├── fetch_nfl.py          ← nflreadpy data fetcher
  ├── fetch_odds.py         ← ParlayAPI + The Odds API
  ├── feature_engineer.py   ← Feature construction
  ├── model_nba_ats.pkl     ← Trained model (scikit-learn)
  ├── model_nfl_ats.pkl     ← Trained model
  ├── model_totals.pkl      ← Trained model
  ├── inference.py          ← Run predictions
  ├── discord_dispatch.py   ← Format + post to Discord
  └── scheduler.py          ← APScheduler cron triggers

  discord_bot/
  ├── bot.py                ← Main discord.py bot
  ├── cogs/
  │   ├── picks.py          ← /picks slash command
  │   ├── stats.py          ← /record, /model-stats
  │   └── subscribe.py      ← Subscription management
  ├── webhooks.py           ← Webhook dispatch layer
  └── embeds.py             ← Embed templates

==============================================================
## SECTION 6 — CLEANUP PLAN (Post-Transfer)
==============================================================

### FILES TO REVIEW FOR BLOAT:
  - implementation_plan.md.resolved.* (83 duplicates) → PURGE
  - task.md.resolved.* (87 duplicates) → PURGE
  - walkthrough.md.resolved.* (26 duplicates) → PURGE
  - *.resolved.* pattern throughout root → AUDIT ALL

### CLEANUP SCRIPT NEEDED:
  - Scan workspace for .resolved.* files
  - Move canonical versions to archive
  - Delete duplicates
  - Receipt the cleanup as a Pulse to H:\Trishula_Pulses\

### CLOUD ARBITRAGE CLEANUP:
  From transfer files (v3.0 / v4.0):
  - Identify old cloud configs to deprecate
  - Map which provider handles which workload
  - Update credentials in .env
  - Verify each cloud account is active and within free tier

==============================================================
## SECTION 7 — IMMEDIATE ACTION QUEUE (Post-Transfer)
==============================================================

  PRIORITY 1 (Day 1 post-transfer):
  [ ] Ingest all transfer files — inventory and categorize
  [ ] Run bloat cleanup script — purge .resolved.* duplicates
  [ ] Read cloud_arbitrage_v3.0 and v4.0 files
  [ ] Read Discord URL links file
  [ ] Map existing swarm → new Discord architecture

  PRIORITY 2 (Days 2-3):
  [ ] Set up Oracle Always Free ARM instance (primary compute)
  [ ] Deploy GCP BigQuery dataset for SBM historical data
  [ ] Configure AWS Lambda scheduled triggers
  [ ] Set up Supabase database schema
  [ ] Deploy Cloudflare R2 bucket for pick archives

  PRIORITY 3 (Days 4-7):
  [ ] Build sbm_pipeline/ — data fetch layer first
  [ ] Load historical NBA + NFL data into BigQuery
  [ ] Train Model 1 (NBA ATS) — backtest to 2020 season
  [ ] Train Model 2 (NFL ATS) — backtest to 2019 season
  [ ] Validate model CLV positive on holdout set

  PRIORITY 4 (Days 8-14):
  [ ] Build discord_bot/ — basic slash commands
  [ ] Set up Discord server structure (channels + roles)
  [ ] Connect model outputs → Discord webhook dispatch
  [ ] Soft launch — test with internal accounts
  [ ] Wire Stripe → Discord role assignment

  PRIORITY 5 (Days 15-30):
  [ ] Finalize remaining TradingView indicator writeups
  [ ] Post all 10 indicator writeups in Discord
  [ ] Set up Starfall → Discord webhook alerts
  [ ] Launch public Discord invite
  [ ] Add Discord server link to Wave 1 follow-up emails

==============================================================
## STATUS: HOLDING — AWAITING USB TRANSFER
## Next Action: Ingest transfer files, update this doc
## Pulse to be filed: PULSE_V2_SBM_DISCORD_LAUNCH.md
==============================================================
