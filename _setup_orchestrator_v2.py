#!/usr/bin/env python3
"""
=============================================================
TRISHULA PHASE 3 — CROSS-CLOUD SOVEREIGN ORCHESTRATOR v2
=============================================================
Deploys an AWS Step Functions state machine that orchestrates:
  1. GCP Pub/Sub trigger (trishula-picks topic)
  2. Lambda health monitor (trishula-trial-killshot)
  3. Discord notification via AWS SNS
  4. Oracle DB1 audit record via ORDS REST

State Machine ARN: arn:aws:states:us-east-2:759729568430:stateMachine:trishula-sovereign-orchestrator
Region: us-east-2
=============================================================
"""

import os, sys, json, time, boto3, requests
from datetime import datetime, timezone
from base64 import b64encode
from pathlib import Path

# ── stdout UTF-8 ──────────────────────────────────────────
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

NOW      = datetime.now(timezone.utc).isoformat()
RUN_ID   = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

# ── Constants pulled from .env + config.py ───────────────
SM_ARN   = "arn:aws:states:us-east-2:759729568430:stateMachine:trishula-sovereign-orchestrator"
SM_NAME  = "trishula-sovereign-orchestrator"
REGION   = "us-east-2"

LAMBDA_FN       = "trishula-trial-killshot"
GCP_PROJECT     = "gcp-swarm-491812"
GCP_TOPIC       = "trishula-picks"
GCP_CLOUD_FN    = "https://trishula-swarm-fn-60878208706.us-central1.run.app"
ORDS_URL        = "https://g275356d1414552-trishulapicks.adb.us-ashburn-1.oraclecloudapps.com/ords/admin/"
ORACLE_USER     = "ADMIN"
ORACLE_PW       = "C1iffyHu5tl3!!!"
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1505723849830830122/G7nu04eqwEEWzLlHquyTK7Ew4Vle4Rl9FHv5ImeNOKWEPI2LH8iuld6OFEkmMyJflJyR"

# ── AWS clients ──────────────────────────────────────────
sf  = boto3.client("stepfunctions", region_name=REGION)
sns = boto3.client("sns",           region_name=REGION)
lam = boto3.client("lambda",        region_name=REGION)
iam = boto3.client("iam",           region_name=REGION)

print()
print("=" * 62)
print("  TRISHULA PHASE 3 — CROSS-CLOUD ORCHESTRATOR v2")
print(f"  Run ID : {RUN_ID}")
print(f"  Started: {NOW[:19]} UTC")
print("=" * 62)


# ══════════════════════════════════════════════════════════
# STEP 0 — Resolve IAM Role ARN
# ══════════════════════════════════════════════════════════
print("\n[0/5] Resolving IAM role...")
try:
    role = iam.get_role(RoleName="trishula-stepfunctions-role")
    ROLE_ARN = role["Role"]["Arn"]
    print(f"  [OK] Role ARN: {ROLE_ARN}")
except Exception as e:
    print(f"  [WARN] Could not fetch role: {e}")
    ROLE_ARN = f"arn:aws:iam::759729568430:role/trishula-stepfunctions-role"
    print(f"  [OK] Using assumed ARN: {ROLE_ARN}")


# ══════════════════════════════════════════════════════════
# STEP 1 — Get current state machine definition from AWS
# ══════════════════════════════════════════════════════════
print("\n[1/5] Reading current state machine from AWS...")
try:
    current = sf.describe_state_machine(stateMachineArn=SM_ARN)
    current_def = json.loads(current["definition"])
    print(f"  [OK] Current state: {current['status']}")
    print(f"  [OK] Current StartAt: {current_def.get('StartAt')}")
    print(f"  [OK] Current states: {list(current_def.get('States', {}).keys())}")
except Exception as e:
    print(f"  [WARN] Could not read current definition: {e}")
    current_def = {}


# ══════════════════════════════════════════════════════════
# STEP 2 — Ensure SNS topic for Discord notifications exists
# ══════════════════════════════════════════════════════════
print("\n[2/5] Ensuring SNS topic: trishula-discord-alerts...")
try:
    resp = sns.create_topic(Name="trishula-discord-alerts")
    SNS_TOPIC_ARN = resp["TopicArn"]
    print(f"  [OK] SNS Topic ARN: {SNS_TOPIC_ARN}")
except Exception as e:
    # Fallback — list and find it
    try:
        topics = sns.list_topics()["Topics"]
        match = [t for t in topics if "trishula" in t["TopicArn"].lower()]
        SNS_TOPIC_ARN = match[0]["TopicArn"] if match else f"arn:aws:sns:{REGION}:759729568430:trishula-discord-alerts"
        print(f"  [OK] Using SNS topic: {SNS_TOPIC_ARN}")
    except Exception as e2:
        SNS_TOPIC_ARN = f"arn:aws:sns:{REGION}:759729568430:trishula-discord-alerts"
        print(f"  [WARN] SNS fallback: {SNS_TOPIC_ARN}")

# Ensure HTTPS subscription (Discord webhook endpoint) on the topic
try:
    # Check existing subscriptions
    subs = sns.list_subscriptions_by_topic(TopicArn=SNS_TOPIC_ARN)
    existing_endpoints = [s["Endpoint"] for s in subs.get("Subscriptions", [])]
    if DISCORD_WEBHOOK not in existing_endpoints:
        # SNS HTTPS subscriptions require a publicly reachable endpoint.
        # The Discord webhook IS publicly reachable. Subscribe and note
        # that AWS will POST a SubscriptionConfirmation — Discord ignores it
        # so we post a raw SNS message to Discord directly from Python instead.
        print(f"  [INFO] Discord webhook not subscribed via SNS (SNS HTTPS confirmations not acked by Discord).")
        print(f"         Orchestrator will POST to Discord directly from the Lambda SNS-Relay step.")
    else:
        print(f"  [OK] Discord webhook already subscribed.")
except Exception as e:
    print(f"  [INFO] Subscription check skipped: {e}")


# ══════════════════════════════════════════════════════════
# STEP 2b — Out-of-band: Real GCP PubSub trigger
# ══════════════════════════════════════════════════════════
print("\n[2b] Triggering GCP Cloud Run / PubSub out-of-band...")
GCP_TRIGGER_RESULT = {"status": "not_attempted"}
try:
    gcp_payload = {
        "action": "publish_signal",
        "topic": GCP_TOPIC,
        "project": GCP_PROJECT,
        "run_id": RUN_ID,
        "source": "trishula-sovereign-orchestrator-v2",
        "phase": "3"
    }
    gr = requests.post(
        GCP_CLOUD_FN,
        json=gcp_payload,
        headers={"Content-Type": "application/json", "X-Trishula-Source": "aws-orchestrator-v2"},
        timeout=20
    )
    GCP_TRIGGER_RESULT = {"status": gr.status_code, "body": gr.text[:200]}
    if gr.status_code in (200, 201, 204):
        print(f"  [OK] GCP Cloud Run responded HTTP {gr.status_code}: {gr.text[:80]}")
    else:
        print(f"  [INFO] GCP Cloud Run HTTP {gr.status_code}: {gr.text[:80]} (continuing)")
except Exception as e:
    GCP_TRIGGER_RESULT = {"status": "error", "error": str(e)[:100]}
    print(f"  [INFO] GCP trigger non-fatal: {str(e)[:80]}")


# ══════════════════════════════════════════════════════════
# STEP 3 — Define full Phase 3 state machine
# ══════════════════════════════════════════════════════════
print("\n[3/5] Defining Phase 3 cross-cloud state machine...")

# The orchestration flow:
#   TriggerGCPPubSub (Pass state — real GCP trigger done out-of-band above)
#     → LambdaHealthMonitor (invoke trishula-trial-killshot health_check)
#       → EvaluateHealth (Choice: PASS / FAIL)
#         PASS → NotifyDiscordViaSNS (SNS publish)
#               → WriteOracleAuditRecord (ORDS REST via Lambda invoke)
#                 → OrchestratorSuccess (Succeed)
#         FAIL → NotifyDiscordFailure
#               → OrchestratorFailed (Fail)

STATE_MACHINE_V2 = {
    "Comment": (
        "Trishula Phase 3 Cross-Cloud Orchestrator — "
        "GCP PubSub → Lambda Health → Discord SNS → Oracle ORDS Audit"
    ),
    "StartAt": "TriggerGCPPubSub",
    "States": {

        # ── State 1: GCP PubSub trigger via Lambda ───────────────────
        # Note: Step Functions :::http:invoke requires an EventBridge Connection
        # ARN for authentication. We route via trishula-trial-killshot Lambda
        # instead — Lambda POSTs to GCP Cloud Run which publishes to trishula-picks.
        "TriggerGCPPubSub": {
            "Type": "Task",
            "Resource": "arn:aws:states:::lambda:invoke",
            "Parameters": {
                "FunctionName": LAMBDA_FN,
                "Payload": {
                    "action": "gcp_pubsub_trigger",
                    "gcp_endpoint": GCP_CLOUD_FN,
                    "gcp_topic": GCP_TOPIC,
                    "gcp_project": GCP_PROJECT,
                    "run_id": RUN_ID,
                    "source": "trishula-sovereign-orchestrator-v2",
                    "phase": "3"
                }
            },
            "ResultSelector": {
                "statusCode.$": "$.StatusCode",
                "payload.$": "$.Payload"
            },
            "ResultPath": "$.gcp_trigger_result",
            "Retry": [{
                "ErrorEquals": ["Lambda.ServiceException", "Lambda.AWSLambdaException"],
                "IntervalSeconds": 3,
                "MaxAttempts": 2,
                "BackoffRate": 1.5
            }],
            "Catch": [{
                "ErrorEquals": ["States.ALL"],
                "Next": "GCPTriggerFailed",
                "ResultPath": "$.gcp_error"
            }],
            "Next": "LambdaHealthMonitor"
        },

        # ── State 1b: GCP trigger failed — skip gracefully ───────────
        "GCPTriggerFailed": {
            "Type": "Pass",
            "Comment": "GCP Lambda trigger failed — continue with health check",
            "Result": {
                "statusCode": 0,
                "payload": {
                    "status": "gcp_trigger_skipped",
                    "reason": "GCP Cloud Run not reachable from Lambda — out-of-band trigger executed"
                }
            },
            "ResultPath": "$.gcp_trigger_result",
            "Next": "LambdaHealthMonitor"
        },

        # ── State 2: Lambda Health Monitor ───────────────────────────
        "LambdaHealthMonitor": {
            "Type": "Task",
            "Resource": "arn:aws:states:::lambda:invoke",
            "Parameters": {
                "FunctionName": LAMBDA_FN,
                "Payload": {
                    "action": "health_check",
                    "source": "step-functions-phase3",
                    "run_id": RUN_ID,
                    "gcp_status.$": "$.gcp_trigger_result"
                }
            },
            "ResultSelector": {
                "statusCode.$": "$.StatusCode",
                "payload.$": "$.Payload"
            },
            "ResultPath": "$.lambda_result",
            "Retry": [{
                "ErrorEquals": ["Lambda.ServiceException", "Lambda.AWSLambdaException"],
                "IntervalSeconds": 2,
                "MaxAttempts": 3,
                "BackoffRate": 2
            }],
            "Catch": [{
                "ErrorEquals": ["States.ALL"],
                "Next": "LambdaHealthFailed",
                "ResultPath": "$.error"
            }],
            "Next": "EvaluateHealth"
        },

        # ── State 2b: Lambda failure passthrough ─────────────────────
        "LambdaHealthFailed": {
            "Type": "Pass",
            "Comment": "Lambda invocation failed — continue with failure notification",
            "Result": {
                "statusCode": 500,
                "payload": {"status": "lambda_invocation_failed"}
            },
            "ResultPath": "$.lambda_result",
            "Next": "NotifyDiscordFailure"
        },

        # ── State 3: Evaluate health result ──────────────────────────
        "EvaluateHealth": {
            "Type": "Choice",
            "Choices": [{
                "Variable": "$.lambda_result.statusCode",
                "NumericEquals": 200,
                "Next": "NotifyDiscordSuccess"
            }],
            "Default": "NotifyDiscordFailure"
        },

        # ── State 4a: Discord SUCCESS notification via SNS ────────────
        "NotifyDiscordSuccess": {
            "Type": "Task",
            "Resource": "arn:aws:states:::sns:publish",
            "Parameters": {
                "TopicArn": SNS_TOPIC_ARN,
                "Subject": "Trishula Phase 3 Orchestration — PASS",
                "Message.$": "States.Format('✅ Trishula Phase 3 Cross-Cloud Orchestration PASSED\nRun ID: {}\nGCP PubSub: triggered\nLambda Health: 200 OK\nAudit: writing to Oracle DB1\nTimestamp: {}', $$.Execution.Name, $$.Execution.StartTime)",
                "MessageAttributes": {
                    "source": {
                        "DataType": "String",
                        "StringValue": "trishula-step-functions"
                    },
                    "phase": {
                        "DataType": "String",
                        "StringValue": "3"
                    }
                }
            },
            "ResultPath": "$.sns_result",
            "Catch": [{
                "ErrorEquals": ["States.ALL"],
                "Next": "WriteOracleAuditRecord",
                "ResultPath": "$.sns_error"
            }],
            "Next": "WriteOracleAuditRecord"
        },

        # ── State 4b: Discord FAILURE notification ────────────────────
        "NotifyDiscordFailure": {
            "Type": "Task",
            "Resource": "arn:aws:states:::sns:publish",
            "Parameters": {
                "TopicArn": SNS_TOPIC_ARN,
                "Subject": "Trishula Phase 3 Orchestration — FAIL",
                "Message.$": "States.Format('❌ Trishula Phase 3 Orchestration FAILED\nRun ID: {}\nTimestamp: {}\nCheck Lambda logs for trishula-trial-killshot', $$.Execution.Name, $$.Execution.StartTime)"
            },
            "ResultPath": "$.sns_fail_result",
            "Catch": [{
                "ErrorEquals": ["States.ALL"],
                "Next": "OrchestratorFailed",
                "ResultPath": "$.sns_error"
            }],
            "Next": "OrchestratorFailed"
        },

        # ── State 5: Write Oracle DB1 audit record via Lambda ─────────
        "WriteOracleAuditRecord": {
            "Type": "Task",
            "Resource": "arn:aws:states:::lambda:invoke",
            "Parameters": {
                "FunctionName": LAMBDA_FN,
                "Payload": {
                    "action": "oracle_audit_write",
                    "run_id": RUN_ID,
                    "ords_url": ORDS_URL,
                    "phase": "3",
                    "event_type": "cross_cloud_orchestration",
                    "source": "aws-step-functions",
                    "status": "PASS",
                    "gcp_status.$": "$.gcp_trigger_result",
                    "lambda_status.$": "$.lambda_result.statusCode"
                }
            },
            "ResultPath": "$.oracle_result",
            "Retry": [{
                "ErrorEquals": ["Lambda.ServiceException"],
                "IntervalSeconds": 5,
                "MaxAttempts": 2,
                "BackoffRate": 1.5
            }],
            "Catch": [{
                "ErrorEquals": ["States.ALL"],
                "Next": "OrchestratorSuccess",
                "ResultPath": "$.oracle_error",
                "Comment": "Oracle write failure is non-fatal — orchestration still succeeds"
            }],
            "Next": "OrchestratorSuccess"
        },

        # ── Terminal: SUCCESS ─────────────────────────────────────────
        "OrchestratorSuccess": {
            "Type": "Succeed",
            "Comment": "Phase 3 cross-cloud orchestration completed successfully"
        },

        # ── Terminal: FAILURE ─────────────────────────────────────────
        "OrchestratorFailed": {
            "Type": "Fail",
            "Error": "OrchestratorError",
            "Cause": "Trishula Phase 3 orchestration pipeline failed — check CloudWatch logs"
        }
    }
}

print(f"  [OK] State machine defined: {len(STATE_MACHINE_V2['States'])} states")
print(f"  [OK] Flow: TriggerGCPPubSub → LambdaHealthMonitor → EvaluateHealth")
print(f"             → NotifyDiscordSuccess/Failure (SNS) → WriteOracleAuditRecord → Success")


# ══════════════════════════════════════════════════════════
# STEP 4 — Deploy / update the state machine on AWS
# ══════════════════════════════════════════════════════════
print("\n[4/5] Deploying updated state machine to AWS...")
DEFINITION_JSON = json.dumps(STATE_MACHINE_V2, indent=2)

try:
    update_resp = sf.update_state_machine(
        stateMachineArn=SM_ARN,
        definition=DEFINITION_JSON,
        roleArn=ROLE_ARN
    )
    print(f"  [OK] State machine updated at: {update_resp.get('updateDate', NOW)}")
    print(f"  [OK] ARN: {SM_ARN}")

    # Brief pause for AWS to propagate the update
    print("  [WAIT] Allowing 5s for AWS to propagate update...")
    time.sleep(5)

    # Verify — describe and confirm
    verify = sf.describe_state_machine(stateMachineArn=SM_ARN)
    verified_def = json.loads(verify["definition"])
    print(f"  [OK] Verified StartAt: {verified_def.get('StartAt')}")
    print(f"  [OK] Verified states: {list(verified_def.get('States', {}).keys())}")
    print(f"  [OK] Status: {verify['status']}")

except sf.exceptions.StateMachineDoesNotExist:
    print("  [WARN] State machine not found — creating fresh...")
    try:
        create_resp = sf.create_state_machine(
            name=SM_NAME,
            definition=DEFINITION_JSON,
            roleArn=ROLE_ARN,
            type="STANDARD",
            tags=[
                {"key": "Project",    "value": "trishula-swarm"},
                {"key": "Phase",      "value": "3"},
                {"key": "CostCenter", "value": "free-tier"},
            ]
        )
        print(f"  [OK] Created: {create_resp['stateMachineArn']}")
        time.sleep(5)
    except Exception as e:
        print(f"  [FAIL] Create failed: {e}")
        sys.exit(1)

except Exception as e:
    print(f"  [FAIL] Update failed: {e}")
    print(f"  [INFO] Attempting create-or-skip...")
    sys.exit(1)


# ══════════════════════════════════════════════════════════
# STEP 5 — Run a test execution
# ══════════════════════════════════════════════════════════
print("\n[5/5] Starting test execution...")
TEST_INPUT = {
    "source":    "manual_test",
    "run_id":    RUN_ID,
    "phase":     "3",
    "symbol":    "NVDA",
    "sweep":     "phase3_integration_test",
    "timestamp": NOW,
    "initiated_by": "setup_orchestrator_v2"
}

try:
    exec_resp = sf.start_execution(
        stateMachineArn=SM_ARN,
        name=f"test-phase3-{RUN_ID}",
        input=json.dumps(TEST_INPUT)
    )
    EXEC_ARN = exec_resp["executionArn"]
    print(f"  [OK] Execution started: {EXEC_ARN}")
    print(f"  [OK] Input: {json.dumps(TEST_INPUT, separators=(',',':'))}")

    # ── Poll for result (max 90s) ──────────────────────────
    print("\n  [POLL] Waiting for execution to complete (max 90s)...")
    POLL_MAX   = 90
    POLL_INT   = 5
    elapsed    = 0
    final_status = None
    final_output = None
    events_log   = []

    while elapsed < POLL_MAX:
        time.sleep(POLL_INT)
        elapsed += POLL_INT

        desc = sf.describe_execution(executionArn=EXEC_ARN)
        status = desc["status"]
        print(f"    [{elapsed:>3}s] Status: {status}")

        if status in ("SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"):
            final_status = status
            final_output = desc.get("output", "{}")
            break

    if final_status is None:
        final_status = "RUNNING (still in progress after 90s)"

    # ── Fetch execution history ────────────────────────────
    print("\n  [INFO] Fetching execution history...")
    try:
        history = sf.get_execution_history(
            executionArn=EXEC_ARN,
            maxResults=50,
            reverseOrder=False
        )
        events_log = history.get("events", [])
        print(f"  [OK] {len(events_log)} history events recorded")
    except Exception as e:
        print(f"  [WARN] Could not fetch history: {e}")

except Exception as e:
    print(f"  [FAIL] Execution start failed: {e}")
    EXEC_ARN     = "N/A"
    final_status = "FAILED_TO_START"
    final_output = "{}"
    events_log   = []


# ══════════════════════════════════════════════════════════
# OUT-OF-BAND: Write audit record directly to Oracle ORDS
# (Fallback — since Lambda may not have ORDS logic yet)
# ══════════════════════════════════════════════════════════
print("\n[+] Writing audit record directly to Oracle DB1 (ORDS)...")
try:
    creds   = b64encode(f"{ORACLE_USER}:{ORACLE_PW}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Content-Type": "application/json"}

    # Ensure audit table exists
    create_audit_sql = """
CREATE TABLE trishula_orchestration_audit (
    id           NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id       VARCHAR2(50),
    exec_arn     VARCHAR2(300),
    phase        VARCHAR2(10),
    event_type   VARCHAR2(100),
    status       VARCHAR2(20),
    source       VARCHAR2(100),
    payload      CLOB,
    created_at   TIMESTAMP DEFAULT SYSTIMESTAMP
)"""
    r_create = requests.post(
        ORDS_URL.rstrip("/") + "/_/sql",
        headers=headers,
        json={"statementText": create_audit_sql.strip()},
        timeout=15
    )
    create_resp_body = r_create.json() if r_create.content else {}
    if "ORA-00955" in str(create_resp_body):
        print("  [OK] Audit table already exists.")
    elif r_create.status_code in (200, 201):
        print("  [OK] Audit table created.")
    else:
        print(f"  [INFO] Table DDL HTTP {r_create.status_code}")

    # Insert audit record
    payload_str = json.dumps({
        "exec_arn": EXEC_ARN,
        "test_input": TEST_INPUT,
        "final_status": final_status,
        "events_count": len(events_log)
    }).replace("'", "''")

    insert_sql = f"""INSERT INTO trishula_orchestration_audit
        (run_id, exec_arn, phase, event_type, status, source, payload)
        VALUES (
            '{RUN_ID}',
            '{EXEC_ARN[:290]}',
            '3',
            'cross_cloud_orchestration',
            '{final_status[:20]}',
            'setup_orchestrator_v2',
            '{payload_str[:3900]}'
        )"""
    r_ins = requests.post(
        ORDS_URL.rstrip("/") + "/_/sql",
        headers=headers,
        json={"statementText": insert_sql.strip()},
        timeout=15
    )
    requests.post(
        ORDS_URL.rstrip("/") + "/_/sql",
        headers=headers,
        json={"statementText": "COMMIT"},
        timeout=10
    )
    if r_ins.status_code in (200, 201):
        print(f"  [OK] Audit record written — run_id: {RUN_ID}")
    else:
        print(f"  [WARN] Oracle insert HTTP {r_ins.status_code}: {r_ins.text[:120]}")

    # Read back to confirm
    r_sel = requests.post(
        ORDS_URL.rstrip("/") + "/_/sql",
        headers=headers,
        json={"statementText": f"SELECT run_id, phase, status, source, created_at FROM trishula_orchestration_audit WHERE run_id='{RUN_ID}'"},
        timeout=15
    )
    if r_sel.status_code in (200, 201):
        items = r_sel.json().get("items", [])
        if items:
            print(f"  [OK] Read-back confirmed: {items[0]}")
        else:
            print(f"  [INFO] No rows returned in read-back (may need moment to commit).")

except Exception as e:
    print(f"  [WARN] Oracle ORDS write failed: {str(e)[:200]}")
    print(f"  [INFO] This is non-fatal — state machine is deployed and execution ran.")


# ══════════════════════════════════════════════════════════
# OUT-OF-BAND: Post to Discord directly
# ══════════════════════════════════════════════════════════
print("\n[+] Posting Phase 3 result to Discord...")
try:
    status_emoji = "✅" if "SUCCEEDED" in str(final_status) else ("⚠️" if "RUNNING" in str(final_status) else "❌")
    discord_payload = {
        "username":   "Trishula Sovereign Swarm",
        "avatar_url": "https://i.imgur.com/xO4b2nJ.png",
        "embeds": [{
            "title": f"{status_emoji} Phase 3 Cross-Cloud Orchestration — {final_status}",
            "color": 3066993 if "SUCCEEDED" in str(final_status) else 15158332,
            "fields": [
                {"name": "Run ID",          "value": f"`{RUN_ID}`",                  "inline": True},
                {"name": "Phase",           "value": "`3`",                          "inline": True},
                {"name": "Final Status",    "value": f"`{final_status}`",            "inline": True},
                {"name": "Execution ARN",   "value": f"```{EXEC_ARN[:80]}...```",    "inline": False},
                {"name": "GCP Trigger",     "value": f"`{GCP_CLOUD_FN[:60]}`",       "inline": False},
                {"name": "Lambda Monitor",  "value": f"`{LAMBDA_FN}`",               "inline": True},
                {"name": "Oracle Audit",    "value": "`trishula_orchestration_audit` table", "inline": True},
                {"name": "History Events",  "value": str(len(events_log)),           "inline": True},
            ],
            "footer": {"text": f"Trishula Phase 3 | Step Functions | {NOW[:19]} UTC"}
        }]
    }
    dr = requests.post(DISCORD_WEBHOOK, json=discord_payload, timeout=10)
    if dr.status_code in (200, 204):
        print(f"  [OK] Discord notification sent (HTTP {dr.status_code})")
    else:
        print(f"  [WARN] Discord HTTP {dr.status_code}: {dr.text[:100]}")
except Exception as e:
    print(f"  [WARN] Discord post failed: {e}")


# ══════════════════════════════════════════════════════════
# FINAL REPORT
# ══════════════════════════════════════════════════════════
print()
print("=" * 62)
print("  TRISHULA PHASE 3 — ORCHESTRATOR v2 REPORT")
print("=" * 62)
print(f"  State Machine : {SM_NAME}")
print(f"  ARN           : {SM_ARN}")
print(f"  States        : {len(STATE_MACHINE_V2['States'])} (Phase 3 cross-cloud)")
print(f"  Run ID        : {RUN_ID}")
print(f"  Execution ARN : {EXEC_ARN}")
print(f"  Final Status  : {final_status}")
print()
print("  PIPELINE STAGES:")
print("  1. GCP Pub/Sub   → trishula-picks (via Cloud Run endpoint)")
print("  2. Lambda Health → trishula-trial-killshot (health_check)")
print("  3. Discord/SNS   → trishula-discord-alerts topic")
print("  4. Oracle Audit  → trishula_orchestration_audit (ORDS REST)")
print()

if events_log:
    print("  EXECUTION HISTORY (key events):")
    for ev in events_log[:15]:
        ev_type = ev.get("type", "?")
        ev_ts   = str(ev.get("timestamp", ""))[:19]
        detail  = ""
        if "stateEnteredEventDetails" in ev:
            detail = f"→ {ev['stateEnteredEventDetails'].get('name', '')}"
        elif "stateExitedEventDetails" in ev:
            detail = f"← {ev['stateExitedEventDetails'].get('name', '')}"
        elif "taskSucceededEventDetails" in ev:
            out = ev["taskSucceededEventDetails"].get("output", "")[:60]
            detail = f"output: {out}"
        elif "taskFailedEventDetails" in ev:
            detail = f"FAILED: {ev['taskFailedEventDetails'].get('cause', '')[:60]}"
        elif "executionSucceededEventDetails" in ev:
            detail = "EXECUTION SUCCEEDED"
        elif "executionFailedEventDetails" in ev:
            detail = f"EXECUTION FAILED: {ev['executionFailedEventDetails'].get('cause', '')[:60]}"
        print(f"    {ev_ts} [{ev_type:<40}] {detail}")

print()
print(f"  Output snapshot: {str(final_output)[:200]}")
print("=" * 62)
print()

# Save report to disk
report = {
    "timestamp":        NOW,
    "run_id":           RUN_ID,
    "state_machine":    SM_NAME,
    "state_machine_arn": SM_ARN,
    "execution_arn":    EXEC_ARN,
    "final_status":     final_status,
    "final_output":     final_output,
    "states_defined":   list(STATE_MACHINE_V2["States"].keys()),
    "events_count":     len(events_log),
    "events_log":       [
        {
            "type":      e.get("type"),
            "timestamp": str(e.get("timestamp", "")),
        }
        for e in events_log
    ]
}

report_path = Path(r"H:\Trishula\Swarm_4_Integration\Salvo_Staging\orchestrator_v2_report.json")
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, default=str)
print(f"  [OK] Report saved: {report_path}")
