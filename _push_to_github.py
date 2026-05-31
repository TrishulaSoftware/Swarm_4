#!/usr/bin/env python3
"""
TRISHULA SOVEREIGN SWARM — GITHUB IaC PUSH
===========================================
Collects all IaC, creates clean repo structure,
generates README + .env.example, pushes to GitHub.

Run: python _push_to_github.py --init    (first time)
     python _push_to_github.py --push    (subsequent pushes)
"""
import os, shutil, subprocess, json
from pathlib import Path
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────
SALVO      = Path(r"H:\Trishula\Swarm_4_Integration\Salvo_Staging")
REPO_NAME  = "trishula-sovereign-swarm"
REPO_DIR   = Path(r"H:\Trishula") / REPO_NAME
GITHUB_URL = "https://github.com/YOUR_USERNAME/trishula-sovereign-swarm.git"
ENV_PATH   = Path(r"H:\Trishula\Swarm_4_Integration\Swarm_4_SBM_FINAL INTEGRATION\Project-Swarm\trishula-market-data\.env")

# ── File Map: source -> repo destination ──────────────────────────────────
FILES = {
    # AWS IaC
    "aws_trial_killswitch.py":      "infrastructure/aws/aws_trial_killswitch.py",
    "aws_provision_infra.py":       "infrastructure/aws/aws_provision_infra.py",
    "aws_fix_iam.py":               "infrastructure/aws/aws_fix_iam.py",
    # GCP IaC
    "setup_gcp_pubsub_scheduler.py":"infrastructure/gcp/setup_gcp_pubsub_scheduler.py",
    "_activate_gemini_pro.py":      "infrastructure/gcp/_activate_gemini_pro.py",
    "_test_gcp_apis.py":            "infrastructure/gcp/_test_gcp_apis.py",
    # Azure IaC
    "setup_cosmos.py":              "infrastructure/azure/setup_cosmos.py",
    "setup_azure_cognitive.py":     "infrastructure/azure/setup_azure_cognitive.py",
    "_setup_azure_app_service.py":  "infrastructure/azure/_setup_azure_app_service.py",
    "_test_cosmos.py":              "infrastructure/azure/_test_cosmos.py",
    # OCI IaC
    "setup_oci_sdk.py":             "infrastructure/oci/setup_oci_sdk.py",
    "_test_oracle_db.py":           "infrastructure/oci/_test_oracle_db.py",
    "_test_oracle_db2.py":          "infrastructure/oci/_test_oracle_db2.py",
    # Engine
    "sovereign_options_scanner.py": "engine/sovereign_options_scanner.py",
    "qmatrix_earnings.py":          "engine/qmatrix_earnings.py",
    "qmatrix_altmarkets.py":        "engine/qmatrix_altmarkets.py",
    "qmatrix_macro.py":             "engine/qmatrix_macro.py",
    "comprehend_engine.py":         "engine/comprehend_engine.py",
    "comprehend_nlp.py":            "engine/comprehend_nlp.py",
    # Operations
    "_run_full_stack.py":           "operations/_run_full_stack.py",
    "discord_dispatch.py":          "operations/discord_dispatch.py",
    "picks_proxy.py":               "operations/picks_proxy.py",
    "ledger_manager.py":            "operations/ledger_manager.py",
    "ledger_reconciliation.py":     "operations/ledger_reconciliation.py",
    "setup_scanner_scheduler.ps1":  "operations/setup_scanner_scheduler.ps1",
    "bootstrap_gcp_micro.sh":       "operations/bootstrap_gcp_micro.sh",
    "aws_trial_evidence.json":      "evidence/aws_trial_evidence.json",
}

GITIGNORE = """# Secrets — never commit
.env
*.env
oracle_wallet/
oracle_wallet2/
trishula-gcp-key.json
*.json.key
*credentials*
~/.oci/

# Logs
logs/
*.log

# Python
__pycache__/
*.pyc
*.pyo
.venv/
venv/

# Local scratch
scratch/
*.tmp
"""

def make_env_example():
    """Generate .env.example with structure but no values."""
    if not ENV_PATH.exists():
        return "# .env.example — copy to .env and fill in your values\n"
    lines = []
    lines.append("# TRISHULA SOVEREIGN SWARM — .env structure")
    lines.append("# Copy this file to .env and fill in your credentials")
    lines.append("# NEVER commit the actual .env file\n")
    for line in ENV_PATH.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("#") or not line.strip():
            lines.append(line)
        elif "=" in line:
            key = line.split("=", 1)[0].strip()
            lines.append(f"{key}=YOUR_{key}_HERE")
    return "\n".join(lines)

README = f"""# 🔱 Trishula Sovereign Swarm

**Autonomous multi-cloud trading intelligence platform — $0.00/month**

[![Cloud Resources](https://img.shields.io/badge/Cloud%20Resources-53%2F76-brightgreen)]()
[![Monthly Cost](https://img.shields.io/badge/Monthly%20Cost-%240.00-blue)]()
[![AI Services](https://img.shields.io/badge/AI%20Services-18%20Live-purple)]()
[![Clouds](https://img.shields.io/badge/Clouds-4%20Hyperscalers-orange)]()

## Architecture

Deployed across **4 hyperscalers** using exclusively permanent free-tier services:

| Cloud | Live Resources | Key Services |
|---|---|---|
| **OCI** | 13/19 | Dual Autonomous DB, Vault (HSM), Functions, NoSQL, Vision AI |
| **GCP** | 16/20 | Gemini 2.5/3.x (4 models), Pub/Sub, Cloud Scheduler, BigQuery |
| **Azure** | 13/16 | Cosmos DB, 9 Cognitive Services, App Service F1, Static Web App |
| **AWS** | 11/21 | Lambda, DynamoDB (4 tables), Comprehend, SageMaker, SNS/SQS |
| **Total** | **53/76** | **18 AI/ML services · 5,000+ lines Python** |

## Q-Matrix Trading Engine

Real-time options scanner for 38 tickers: SPY, QQQ, NVDA, TSLA, Mag-7, mid-cap universe.

- **6-panel analysis** per ticker: MaxPain, GEX, Whale Liquidity, Multi-expiry modeling
- **Autonomous dispatch** to 11 Discord channels at market open (9:30 AM ET)
- **AI-augmented** via Gemini 2.5 Pro for trade thesis + AWS Comprehend for injury/news NLP

## Key Features

- **Zero cost**: All resources on permanent always-free tiers
- **Kill-switch system**: AWS EventBridge + Lambda auto-terminates trial services before charges
- **Autonomous scheduling**: GCP Cloud Scheduler + Windows Task Scheduler, self-healing
- **Sovereign persistence**: Dual Oracle Autonomous DBs with mTLS wallet authentication
- **Phase 2 hardening**: IAM least-privilege, vault secret migration, unified audit logging

## Repo Structure

```
infrastructure/  # IaC per cloud (Python-native, no Terraform required)
engine/          # Q-Matrix scanner, AI/NLP pipelines
operations/      # Schedulers, Discord dispatch, ledger
evidence/        # Activation timestamps, kill-switch evidence
docs/            # Architecture docs, status, hardening doctrine
```

## Setup

```bash
cp .env.example .env
# Fill in credentials for each cloud
python infrastructure/oci/setup_oci_sdk.py
python infrastructure/gcp/setup_gcp_pubsub_scheduler.py
python infrastructure/aws/aws_provision_infra.py
python operations/_run_full_stack.py
```

## Cloud Arbitrage Status

Full resource status: [cloud_arbitrage_status.md](docs/cloud_arbitrage_status.md)
Phase 2 hardening plan: [phase2_hardening_doctrine.md](docs/phase2_hardening_doctrine.md)

---
*Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d')} | Cost: $0.00/month*
"""

def init_repo():
    """Initialize git repo and copy all files."""
    print("\n" + "="*55)
    print("  TRISHULA GITHUB PUSH -- REPO INIT")
    print("="*55)

    # Create repo dir
    REPO_DIR.mkdir(parents=True, exist_ok=True)
    print(f"  [OK] Repo dir: {REPO_DIR}")

    # Create directory structure
    for folder in ["infrastructure/aws", "infrastructure/gcp",
                   "infrastructure/azure", "infrastructure/oci",
                   "engine", "operations", "evidence", "docs"]:
        (REPO_DIR / folder).mkdir(parents=True, exist_ok=True)

    # Copy IaC files
    copied, missing = [], []
    for src_name, dest_rel in FILES.items():
        src  = SALVO / src_name
        dest = REPO_DIR / dest_rel
        if src.exists():
            shutil.copy2(src, dest)
            copied.append(src_name)
            print(f"  [OK] {src_name}")
        else:
            missing.append(src_name)
            print(f"  [--] MISSING: {src_name}")

    # Copy docs from artifacts
    artifacts = Path(r"C:\Users\War Machine\.gemini\antigravity\brain\93864e2c-9ed8-4427-b83f-230719792669\artifacts")
    for doc in ["cloud_arbitrage_status.md", "phase2_hardening_doctrine.md"]:
        src = artifacts / doc
        if src.exists():
            shutil.copy2(src, REPO_DIR / "docs" / doc)
            print(f"  [OK] docs/{doc}")

    # Write generated files
    (REPO_DIR / "README.md").write_text(README, encoding="utf-8")
    (REPO_DIR / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    (REPO_DIR / ".env.example").write_text(make_env_example(), encoding="utf-8")
    print(f"  [OK] README.md, .gitignore, .env.example")

    # Write manifest
    manifest = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "resources_live": 53,
        "resources_total": 76,
        "monthly_cost_usd": 0.00,
        "clouds": ["AWS", "GCP", "Azure", "OCI"],
        "ai_services_live": 18,
        "files_copied": copied,
        "files_missing": missing,
    }
    (REPO_DIR / "evidence" / "ACTIVATION_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"  [OK] evidence/ACTIVATION_MANIFEST.json")

    # Git init + commit
    def git(cmd):
        r = subprocess.run(cmd, shell=True, cwd=REPO_DIR,
                           capture_output=True, text=True)
        return r.stdout.strip() or r.stderr.strip()

    print("\n  [GIT] Initializing...")
    print(git("git init"))
    print(git('git config user.email "trishula@sovereign.io"'))
    print(git('git config user.name "Trishula Swarm"'))
    print(git("git add -A"))
    print(git(f'git commit -m "feat: Trishula Sovereign Swarm v4.0 — 53/76 resources, $0.00/mo"'))

    print(f"\n  [DONE] Repo ready at: {REPO_DIR}")
    print(f"  [NEXT] Set your GitHub remote:")
    print(f"         git remote add origin <your-repo-url>")
    print(f"         git push -u origin main")
    print("="*55)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--init", action="store_true", help="Initialize repo + first commit")
    parser.add_argument("--push", action="store_true", help="Update files + push")
    args = parser.parse_args()

    if args.init or not args.push:
        init_repo()
    elif args.push:
        print("Syncing files and pushing...")
        init_repo()
        def git(cmd):
            r = subprocess.run(cmd, shell=True, cwd=REPO_DIR,
                               capture_output=True, text=True)
            return r.stdout.strip() or r.stderr.strip()
        print(git("git add -A"))
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        print(git(f'git commit -m "chore: IaC sync {ts}"'))
        print(git("git push origin main"))
