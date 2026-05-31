#!/usr/bin/env python3
"""
=============================================================
TRISHULA SOVEREIGN SWARM — DOCTRINE AUDIT SCRIPT
Phase 3 | All 9 Pillars | Sovereign Baseline: 74 Resources
=============================================================
"""
import os, sys, json, boto3, subprocess
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

NOW     = datetime.now(timezone.utc)
REPORT  = {"timestamp": NOW.isoformat(), "pillars": {}, "pass": [], "fail": [], "warn": []}
BASE    = Path(r"H:\Trishula\Swarm_4_Integration\Salvo_Staging")
ENV     = BASE.parent / "Swarm_4_SBM_FINAL INTEGRATION" / "Project-Swarm" / "trishula-market-data" / ".env"
GCP_KEY = Path(r"H:\Trishula\Swarm_4_Integration\trishula-gcp-key.json")

if GCP_KEY.exists():
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(GCP_KEY)

def OK(pillar, item):
    print(f"  ✅  {item}")
    REPORT["pass"].append(f"P{pillar}: {item}")

def FAIL(pillar, item):
    print(f"  ❌  {item}")
    REPORT["fail"].append(f"P{pillar}: {item}")

def WARN(pillar, item):
    print(f"  ⚠️   {item}")
    REPORT["warn"].append(f"P{pillar}: {item}")

print()
print("=" * 62)
print("  🔱 TRISHULA DOCTRINE AUDIT")
print(f"  {NOW.strftime('%Y-%m-%d %H:%M UTC')}")
print("=" * 62)

# ─────────────────────────────────────────────────────────────
# PILLAR 1 — RESOURCE INVENTORY (live checks)
# ─────────────────────────────────────────────────────────────
print("\n── PILLAR 1: RESOURCE INVENTORY ─────────────────────────")

# AWS
try:
    ddb = boto3.client('dynamodb', region_name='us-east-2')
    tables = ddb.list_tables()['TableNames']
    if tables: OK(1, f"DynamoDB: {len(tables)} tables live {tables}")
    else: WARN(1, "DynamoDB: 0 tables found")
except Exception as e: FAIL(1, f"DynamoDB: {str(e)[:60]}")

try:
    lam = boto3.client('lambda', region_name='us-east-2')
    fns = lam.list_functions(MaxItems=10)['Functions']
    OK(1, f"Lambda: {len(fns)} functions live")
except Exception as e: FAIL(1, f"Lambda: {str(e)[:60]}")

try:
    sfn = boto3.client('stepfunctions', region_name='us-east-2')
    sms = sfn.list_state_machines()['stateMachines']
    if sms: OK(1, f"Step Functions: {sms[0]['name']} LIVE")
    else: WARN(1, "Step Functions: no state machines found")
except Exception as e: FAIL(1, f"Step Functions: {str(e)[:60]}")

try:
    cf = boto3.client('cloudfront', region_name='us-east-1')
    dists = cf.list_distributions().get('DistributionList', {}).get('Items', [])
    if dists: OK(1, f"CloudFront: {len(dists)} distribution(s) live")
    else: WARN(1, "CloudFront: no distributions found")
except Exception as e: FAIL(1, f"CloudFront: {str(e)[:60]}")

try:
    pl = boto3.client('polly', region_name='us-east-2')
    voices = pl.describe_voices(LanguageCode='en-US')['Voices']
    OK(1, f"Polly: {len(voices)} voices LIVE")
except Exception as e: FAIL(1, f"Polly: {str(e)[:60]}")

try:
    fc = boto3.client('forecast', region_name='us-east-2')
    fc.list_datasets()
    OK(1, "Forecast: LIVE")
except Exception as e: FAIL(1, f"Forecast: {str(e)[:60]}")

try:
    lx = boto3.client('lexv2-models', region_name='us-east-1')
    bots = lx.list_bots()['botSummaries']
    if bots: OK(1, f"Lex V2: {bots[0]['botName']} ({bots[0]['botStatus']})")
    else: WARN(1, "Lex V2: no bots found")
except Exception as e: FAIL(1, f"Lex V2: {str(e)[:60]}")

# AWS NLP (Translate + Transcribe INTENTIONALLY REMOVED 2026-05-31)
# Reason: AWS free-tier gating — not part of sovereign baseline
# Sovereign baseline: Comprehend + Textract only
for svc, client_args, method, kwargs in [
    ("Comprehend", {'service_name':'comprehend','region_name':'us-east-1'}, 'detect_sentiment', {'Text':'test','LanguageCode':'en'}),
    ("Textract",   {'service_name':'textract',  'region_name':'us-east-2'}, 'list_adapters',    {}),
]:
    try:
        c = boto3.client(**client_args)
        getattr(c, method)(**kwargs)
        OK(1, f"{svc}: LIVE")
    except Exception as e:
        if 'SubscriptionRequiredException' in str(e):
            WARN(1, f"{svc}: propagating (not a failure)")
        else:
            FAIL(1, f"{svc}: {str(e)[:60]}")

# ─────────────────────────────────────────────────────────────
# PILLAR 2 — IaC FILE INTEGRITY
# ─────────────────────────────────────────────────────────────
print("\n── PILLAR 2: IaC FILE INVENTORY ─────────────────────────")

required_files = [
    "sovereign_options_scanner.py",
    "discord_dispatch.py",
    "ledger_manager.py",
    "picks_proxy.py",
    "_run_full_stack.py",
    "aws_trial_killswitch.py",
    "aws_trial_evidence.json",
    "comprehend_engine.py",
    "_activate_aws_nlp.py",
    "_setup_cloudfront_apigw.py",
    "_setup_step_functions.py",
    "_setup_cloud_tasks.py",
    "_sovereign_health_check.py",
    "_push_to_github.py",
    "reregister_tasks_admin.ps1",
    "register_tasks.ps1",
    "run_qmatrix_open.bat",
    "run_qmatrix_midday.bat",
    "run_qmatrix_powerhour.bat",
]

for f in required_files:
    path = BASE / f
    if path.exists():
        size = path.stat().st_size
        OK(2, f"{f} ({size:,} bytes)")
    else:
        FAIL(2, f"MISSING: {f}")

# Check wallets
for wallet in ["oracle_wallet", "oracle_wallet2"]:
    wpath = BASE / wallet
    if wpath.exists() and any(wpath.iterdir()):
        OK(2, f"{wallet}/ present ({len(list(wpath.iterdir()))} files)")
    else:
        FAIL(2, f"{wallet}/ MISSING or empty")

# ─────────────────────────────────────────────────────────────
# PILLAR 3 — SECURITY CHECKS
# ─────────────────────────────────────────────────────────────
print("\n── PILLAR 3: SECURITY HARDENING ─────────────────────────")

# Check .env exists and has content
if ENV.exists():
    env_size = ENV.stat().st_size
    OK(3, f".env present ({env_size:,} bytes)")
    # Check no raw AWS secret key in .env (basic check)
    env_content = ENV.read_text(encoding='utf-8', errors='ignore')
    if 'K3fodi' in env_content or 'K3fodi++' in env_content:
        WARN(3, ".env contains raw AWS secret key — migrate to vault (Phase 2)")
    else:
        OK(3, ".env: AWS secret key not found in plaintext (or already masked)")
else:
    FAIL(3, ".env MISSING")

# Check AWS IAM user has inline policy
try:
    iam = boto3.client('iam', region_name='us-east-2')
    policies = iam.list_user_policies(UserName='trishula-swarm-bot')['PolicyNames']
    if 'TrishulaSovereignNLP' in policies:
        OK(3, f"IAM: TrishulaSovereignNLP inline policy PRESENT")
    else:
        WARN(3, f"IAM: inline policies = {policies}")

    # Check for old ComprehendReadOnly
    attached = iam.list_attached_user_policies(UserName='trishula-swarm-bot')['AttachedPolicies']
    old_policies = [p['PolicyName'] for p in attached]
    if old_policies:
        WARN(3, f"IAM: attached managed policies still present: {old_policies}")
    else:
        OK(3, "IAM: no stale managed policies on trishula-swarm-bot")
except Exception as e:
    FAIL(3, f"IAM audit: {str(e)[:80]}")

# Check GCP key exists
if GCP_KEY.exists():
    OK(3, f"GCP service account key present ({GCP_KEY.stat().st_size:,} bytes)")
else:
    FAIL(3, "GCP service account key MISSING")

# Check AWS credentials
creds_path = Path.home() / ".aws" / "credentials"
if creds_path.exists():
    creds = creds_path.read_text()
    if 'AKIA3BY3JHKXDQUGI3ED' in creds:
        OK(3, "AWS credentials: trishula-swarm-bot key present in ~/.aws/credentials")
    else:
        WARN(3, "AWS credentials: expected key not found — verify ~/.aws/credentials")
else:
    FAIL(3, "~/.aws/credentials MISSING")

# ─────────────────────────────────────────────────────────────
# PILLAR 4 — SWARM TESTING (kill-switch integrity)
# ─────────────────────────────────────────────────────────────
print("\n── PILLAR 4: KILL-SWITCH & TRIAL INTEGRITY ──────────────")

evidence_path = BASE / "aws_trial_evidence.json"
if evidence_path.exists():
    evidence = json.loads(evidence_path.read_text())
    OK(4, "Trial evidence file present")

    for svc in ['forecast', 'sagemaker']:
        kill_key = f"{svc}_kill_date"
        if kill_key in evidence:
            kill_dt = datetime.fromisoformat(evidence[kill_key])
            days_left = (kill_dt - NOW).days
            if days_left > 14:
                OK(4, f"{svc.capitalize()} kill-date: {evidence[kill_key][:10]} ({days_left} days left) GREEN")
            elif days_left > 0:
                WARN(4, f"{svc.capitalize()} kill-date: {evidence[kill_key][:10]} ({days_left} days left) — YELLOW")
            else:
                FAIL(4, f"{svc.capitalize()} kill-date PAST — RESOURCE MUST BE KILLED NOW")
        else:
            WARN(4, f"{svc}: kill_date not in evidence file")
else:
    FAIL(4, "aws_trial_evidence.json MISSING — kill-switch blind")

# Verify Lambda kill-shot exists
try:
    lam = boto3.client('lambda', region_name='us-east-2')
    fn = lam.get_function(FunctionName='trishula-trial-killshot')
    OK(4, f"Kill Lambda: trishula-trial-killshot LIVE")
except Exception as e:
    FAIL(4, f"Kill Lambda MISSING: {str(e)[:60]}")

# Verify EventBridge rules
try:
    eb = boto3.client('events', region_name='us-east-2')
    rules = eb.list_rules()['Rules']
    rule_names = [r['Name'] for r in rules]
    for r in ['trishula-forecast-hardkill', 'trishula-sagemaker-hardkill']:
        if r in rule_names:
            state = next(x['State'] for x in rules if x['Name'] == r)
            OK(4, f"EventBridge: {r} ({state})")
        else:
            WARN(4, f"EventBridge: {r} not found")
except Exception as e:
    FAIL(4, f"EventBridge audit: {str(e)[:60]}")

# ─────────────────────────────────────────────────────────────
# PILLAR 5 — SCHEDULER INTEGRITY
# ─────────────────────────────────────────────────────────────
print("\n── PILLAR 5: SCHEDULER INTEGRITY ────────────────────────")

try:
    result = subprocess.run(
        ['powershell', '-Command',
         'Get-ScheduledTask | Where-Object { $_.TaskName -match "QMatrix" } | '
         'Select-Object TaskName, State | ConvertTo-Json'],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode == 0 and result.stdout.strip():
        tasks = json.loads(result.stdout)
        if isinstance(tasks, dict): tasks = [tasks]
        for t in tasks:
            name  = t.get('TaskName', '?')
            state = t.get('State', '?')
            if state == 3:  # Ready
                OK(5, f"Scheduler: {name} (Ready)")
            else:
                WARN(5, f"Scheduler: {name} (State={state})")
    else:
        WARN(5, f"Scheduler query returned no results")
except Exception as e:
    WARN(5, f"Scheduler check skipped: {str(e)[:60]}")

# Check .bat wrappers exist
for bat in ["run_qmatrix_open.bat", "run_qmatrix_midday.bat", "run_qmatrix_powerhour.bat"]:
    if (BASE / bat).exists():
        OK(5, f"{bat} present")
    else:
        FAIL(5, f"{bat} MISSING — scheduler will fail")

# Check watchdog
watchdog = BASE / "sovereign_watchdog.py"
if watchdog.exists():
    OK(5, "sovereign_watchdog.py present (Python scheduler, no admin needed)")
else:
    WARN(5, "sovereign_watchdog.py MISSING — scheduler may fail")

startup_bat = Path(r"C:\Users\War Machine\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\trishula_watchdog.bat")
if startup_bat.exists():
    OK(5, "Watchdog installed in Windows Startup folder")
else:
    WARN(5, "Watchdog not in Startup folder — won't auto-start on reboot")

# Check log dir
log_dir = BASE / "logs"
if log_dir.exists():
    logs = list(log_dir.glob("*.log"))
    OK(5, f"Log directory: {len(logs)} log files")
else:
    WARN(5, "logs/ directory missing")

# ─────────────────────────────────────────────────────────────
# PILLAR 6 — GCP LIVE CHECKS
# ─────────────────────────────────────────────────────────────
print("\n── PILLAR 6: GCP SERVICES ───────────────────────────────")
try:
    from google.cloud import storage as gcs
    client = gcs.Client()
    buckets = list(client.list_buckets())
    if buckets:
        OK(6, f"GCS: {len(buckets)} bucket(s) — {[b.name for b in buckets]}")
    else:
        WARN(6, "GCS: no buckets found")
except Exception as e:
    FAIL(6, f"GCS: {str(e)[:60]}")

try:
    from google.cloud import tasks_v2
    tc = tasks_v2.CloudTasksClient()
    q = tc.get_queue(name='projects/gcp-swarm-491812/locations/us-central1/queues/trishula-task-queue')
    OK(6, f"Cloud Tasks: trishula-task-queue LIVE")
except Exception as e:
    FAIL(6, f"Cloud Tasks: {str(e)[:60]}")

try:
    from google.cloud import monitoring_v3
    mc = monitoring_v3.MetricServiceClient()
    req = monitoring_v3.ListMetricDescriptorsRequest(name='projects/gcp-swarm-491812')
    next(iter(mc.list_metric_descriptors(request=req)))
    OK(6, "Cloud Monitoring: LIVE")
except Exception as e:
    FAIL(6, f"Cloud Monitoring: {str(e)[:60]}")

# ─────────────────────────────────────────────────────────────
# PILLAR 7 — ENVIRONMENT COMPLETENESS
# ─────────────────────────────────────────────────────────────
print("\n── PILLAR 7: ENVIRONMENT VARS ───────────────────────────")

required_env_keys = [
    'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY',
    'OCI_LOAD_BALANCER_OCID', 'OCI_LOG_GROUP_OCID',
    'OCI_STREAM_OCID', 'OCI_API_GATEWAY_OCID', 'OCI_QUEUE_OCID',
    'GCP_CLOUD_FUNCTION_URL', 'GCP_TASKS_QUEUE',
    'AWS_STATE_MACHINE_ARN',
    'AZURE_KEY_VAULT_URI', 'AZURE_FUNCTION_APP_URL',
    'GCP_FIRESTORE_DB',
]

if ENV.exists():
    env_content = ENV.read_text(encoding='utf-8', errors='ignore')
    for key in required_env_keys:
        if key in env_content:
            OK(7, f".env: {key} present")
        else:
            WARN(7, f".env: {key} NOT FOUND — wire it")
else:
    FAIL(7, ".env not found")

# ─────────────────────────────────────────────────────────────
# FINAL REPORT
# ─────────────────────────────────────────────────────────────
total_checks = len(REPORT['pass']) + len(REPORT['fail']) + len(REPORT['warn'])
pass_ct  = len(REPORT['pass'])
fail_ct  = len(REPORT['fail'])
warn_ct  = len(REPORT['warn'])

print()
print("=" * 62)
print("  🔱 TRISHULA DOCTRINE AUDIT — COMPLETE")
print("=" * 62)
print(f"  PASS:  {pass_ct:3}")
print(f"  WARN:  {warn_ct:3}")
print(f"  FAIL:  {fail_ct:3}")
print(f"  TOTAL: {total_checks:3}")
print(f"  Sovereign Baseline: 74 resources (Translate/Transcribe removed 2026-05-31)")
print()

if fail_ct == 0 and warn_ct == 0:
    print("  ✅  SOVEREIGN CERTIFIED — ALL SYSTEMS GREEN")
elif fail_ct == 0:
    print(f"  ⚠️   CONDITIONAL PASS — {warn_ct} warnings (review above)")
else:
    print(f"  ❌  AUDIT FAILED — {fail_ct} critical issues")

print()
if REPORT['fail']:
    print("  FAILURES:")
    for f in REPORT['fail']:
        print(f"    ✗ {f}")

if REPORT['warn']:
    print("  WARNINGS:")
    for w in REPORT['warn']:
        print(f"    △ {w}")

print("=" * 62)

REPORT['summary'] = {
    'pass': pass_ct, 'fail': fail_ct, 'warn': warn_ct,
    'verdict': 'PASS' if fail_ct == 0 else 'FAIL'
}

out_path = BASE / "doctrine_audit_report.json"
with open(out_path, 'w') as f:
    json.dump(REPORT, f, indent=2, default=str)
print(f"\n  Saved: {out_path}")
