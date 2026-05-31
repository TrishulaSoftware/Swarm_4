# 🔱 Trishula Sovereign Swarm

**Autonomous multi-cloud trading intelligence platform — $0.00/month**

[![Cloud Resources](https://img.shields.io/badge/Cloud%20Resources-35%2F76%20Live-brightgreen)]()
[![Monthly Cost](https://img.shields.io/badge/Monthly%20Cost-%240.00-blue)]()
[![AI Services](https://img.shields.io/badge/AI%20Services-20%20Live-purple)]()
[![Clouds](https://img.shields.io/badge/Clouds-4%20Hyperscalers-orange)]()
[![Doctrine Audit](https://img.shields.io/badge/Doctrine%20Audit-62%20PASS%20%7C%200%20FAIL-success)]()
[![Kill Switch](https://img.shields.io/badge/Kill%20Switch-ARMED-red)]()

---

## 🏛 Architecture Overview

Trishula is a sovereign, self-healing trading intelligence swarm deployed across **4 hyperscalers** using
exclusively permanent free-tier and trial-managed services. It costs **$0.00/month** to operate.

```
╔══════════════════════════════════════════════════════════════════╗
║          TRISHULA SOVEREIGN SWARM  —  v4.0                      ║
║          35 / 76 Resources Live  ·  $0.00/month                 ║
╠══════════════╦═══════════════╦══════════════════════════════════╣
║  OCI (11/19) ║  GCP  (8/20)  ║  Azure (4/16)  ║  AWS  (12/21)  ║
╚══════════════╩═══════════════╩══════════════════════════════════╝
```

| Cloud | Live | Key Services |
|-------|------|-------------|
| **OCI** | 11 live | Dual Autonomous DB (DB1 + DB2), Vault HSM, Functions, NoSQL, Streaming, Queue, Load Balancer, API Gateway, Object Storage, Logging |
| **GCP** | 8 live | Gemini 2.5 Pro, Pub/Sub, Cloud Storage (2 buckets), BigQuery, Cloud Tasks, Cloud Monitoring, Firestore, Cloud Run / Functions, Translate |
| **Azure** | 4 live | Static Web App, Function App, Key Vault, Container App, Cosmos DB (pending key), 9 Cognitive Services |
| **AWS** | 12 live | Lambda (3 fns), DynamoDB (4 tables), SageMaker, Forecast, Polly, SNS, SQS, CloudFront, API Gateway, Step Functions, EventBridge, Rekognition |
| **Total** | **35/76** | **20 AI/ML services · 5,000+ lines Python · 0 failures** |

---

## ⚡ Q-Matrix Options Scanner

Real-time 6-panel options scanner for **38 tickers**: SPY, QQQ, NVDA, TSLA, Mag-7 + mid-cap universe.

### Scan Panels per Ticker
| Panel | Signal |
|-------|--------|
| **MaxPain** | OI-weighted strike gravity for expiry |
| **GEX (Gamma Exposure)** | Dealer hedging pressure zones |
| **Whale Liquidity** | Institutional block-trade support/resistance |
| **Multi-Expiry Modeling** | 0DTE / weekly / monthly convergence |
| **Earnings Alpha** | Pre/post earnings vol surface distortion |
| **Alt Markets** | Crypto/commodities cross-asset regime |

### Autonomous Dispatch Pipeline
```
09:30 AM ET  →  QMatrix_Open       (38 tickers, full scan)
12:00 PM ET  →  QMatrix_Midday     (momentum re-score)
03:00 PM ET  →  QMatrix_PowerHour  (power-hour compression)
Sunday PM    →  QMatrix_Earnings   (pre-market earnings stack)
```

- **Discord dispatch**: 11 channels, auto-formatted embed cards
- **AI augmentation**: Gemini 2.5 Pro for trade thesis narrative
- **NLP layer**: AWS Comprehend (propagating) + AWS Polly for injury/news signals
- **Windows Task Scheduler** + GCP Cloud Scheduler → dual-redundant firing

---

## 🔐 Security Architecture

| Layer | Implementation |
|-------|---------------|
| **Secret Management** | OCI Vault HSM (150 secrets, 20 keys · always free) |
| **AWS Secrets** | Azure Key Vault (`trishulakeyvaultazure`) as secondary |
| **Kill Switch** | `trishula-trial-killshot` Lambda + EventBridge hard-kill rules |
| **Forecast expiry** | 2026-08-25 (auto-terminates) |
| **SageMaker expiry** | 2026-07-26 (auto-terminates) |
| **IAM** | Least-privilege inline policy `TrishulaSovereignNLP` |
| **mTLS** | Dual Oracle wallet auth for Autonomous DB |

---

## 🗂 Repo Structure

```
trishula-sovereign-swarm/
├── infrastructure/
│   ├── aws/          # Lambda, DynamoDB, IAM, kill-switch IaC
│   ├── gcp/          # Pub/Sub, Scheduler, Gemini activation
│   ├── azure/        # Cosmos DB, Cognitive, App Service
│   └── oci/          # Autonomous DB, Vault, NoSQL, Functions
├── engine/
│   ├── sovereign_options_scanner.py   # 72,756 bytes — core scanner
│   ├── qmatrix_earnings.py
│   ├── qmatrix_altmarkets.py
│   ├── qmatrix_macro.py
│   ├── comprehend_engine.py
│   └── comprehend_nlp.py
├── operations/
│   ├── _run_full_stack.py
│   ├── discord_dispatch.py            # 25,980 bytes — 11-channel router
│   ├── picks_proxy.py
│   ├── ledger_manager.py
│   ├── ledger_reconciliation.py
│   └── setup_scanner_scheduler.ps1
├── evidence/
│   ├── aws_trial_evidence.json        # Kill-switch activation timestamps
│   └── ACTIVATION_MANIFEST.json      # Generated resource manifest
└── docs/
    ├── cloud_arbitrage_status.md
    └── phase2_hardening_doctrine.md
```

---

## 🚀 Setup

### Prerequisites
- Python 3.11+
- AWS CLI configured (`~/.aws/credentials`)
- GCP ADC set (`gcloud auth application-default login`)
- OCI CLI + wallet in `oracle_wallet/` + `oracle_wallet2/`
- Azure CLI authenticated (`az login`)

### Bootstrap
```bash
# 1. Copy and fill in credentials
cp .env.example .env

# 2. Provision each cloud layer (order matters)
python infrastructure/oci/setup_oci_sdk.py
python infrastructure/gcp/setup_gcp_pubsub_scheduler.py
python infrastructure/aws/aws_provision_infra.py
python infrastructure/azure/setup_cosmos.py

# 3. Run the full stack
python operations/_run_full_stack.py
```

### Scheduler Registration (Windows)
```powershell
# Run as Administrator
.\operations\setup_scanner_scheduler.ps1
```

---

## 📊 Backtest Results (May 2026)

| Strategy | Window | Hit Rate | P/L |
|----------|--------|----------|-----|
| Whale Liquidity POC | May 22–23 | Tracked | `backtest_may22_23.json` |
| GEX/MaxPain overlay | Historical | Validated | `_backtest_gex_maxpain.py` |

Backtest data: [`whale_backtest_results.json`](evidence/whale_backtest_results.json)

---

## 🌐 Exposed Endpoints

| Service | URL |
|---------|-----|
| AWS CloudFront CDN | `https://d3osgozw6yxhsl.cloudfront.net` |
| AWS API Gateway | `https://4g3s9zys7b.execute-api.us-east-2.amazonaws.com` |
| GCP Cloud Run Function | `https://trishula-swarm-fn-60878208706.us-central1.run.app` |
| Azure Function App | `https://trishula-functions-hydec7akeha8g7dm.centralus-01.azurewebsites.net` |
| Azure Key Vault | `https://trishulakeyvaultazure.vault.azure.net/` |

---

## 📋 Doctrine Audit (2026-05-28)

```
Pillar Audit — VERDICT: PASS
  ✅ 62 checks passing
  ⚠️   7 warnings (NLP propagation — expected)
  ❌   0 failures

Kill-switch: ARMED
  Forecast   → 2026-08-25  (green)
  SageMaker  → 2026-07-26  (green)
```

Full audit: [`doctrine_audit_report.json`](evidence/doctrine_audit_report.json)

---

## 🔄 Push Workflow

```bash
# Initial setup
python _push_to_github.py --init

# Subsequent syncs
python _push_to_github.py --push
```

---

*Generated: 2026-05-28 | Trishula Sovereign Swarm v4.0 | Cost: $0.00/month*
*Account: AWS 759729568430 · GCP gcp-swarm-491812 · OCI us-ashburn-1 · Azure centralus*
