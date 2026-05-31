#!/usr/bin/env python3
# TRISHULA -- AWS TRIAL HARD-KILL SYSTEM
# IaC Evidence File | Preserved permanently
# ==========================================
# Forecast:  3-month trial. Hard-kill on Day 85 (2026-08-19)
# SageMaker: 2-month trial. Hard-kill on Day 55 (2026-07-20)
#
# KILL-SHOT TARGETS:
#   Forecast:  All datasets, predictors, forecasts, dataset groups
#   SageMaker: All notebook instances (stopped + deleted), models, endpoints
#
# SYSTEM STATUS (activated 2026-05-26):
#   Lambda:     arn:aws:lambda:us-east-2:759729568430:function:trishula-trial-killshot
#   EB Rule 1:  trishula-forecast-hardkill  -> fires 2026-08-19
#   EB Rule 2:  trishula-sagemaker-hardkill -> fires 2026-07-20
#   Billing:    $0.01 trip-wire alarm -> SNS trishula-alerts -> Discord
#   Evidence:   Salvo_Staging/aws_trial_evidence.json
#
# Usage:
#   python aws_trial_killswitch.py --status       Check days remaining
#   python aws_trial_killswitch.py --kill-now     Emergency manual kill
#   python aws_trial_killswitch.py --kill-now --service forecast

import boto3, json, os, argparse
from datetime import datetime, timezone
from pathlib import Path

REGION       = os.getenv("AWS_REGION", "us-east-2")
ACCOUNT_ID   = "759729568430"
EVIDENCE_LOG = Path(r"H:\Trishula\Swarm_4_Integration\Salvo_Staging\aws_trial_evidence.json")

def load_evidence():
    return json.loads(EVIDENCE_LOG.read_text()) if EVIDENCE_LOG.exists() else {}

def status():
    evidence = load_evidence()
    now = datetime.now(timezone.utc)
    print("\n" + "="*55)
    print("  TRISHULA TRIAL HARD-KILL STATUS")
    print("="*55)
    for svc in ["forecast", "sagemaker"]:
        act_key  = f"{svc}_activated"
        kill_key = f"{svc}_kill_date"
        if act_key in evidence:
            activated = datetime.fromisoformat(evidence[act_key])
            kill_date = datetime.fromisoformat(evidence[kill_key])
            days_live = (now - activated).days
            days_left = (kill_date - now).days
            flag      = "[GREEN]" if days_left > 10 else ("[WARN]" if days_left > 3 else "[KILL IMMINENT]")
            print(f"\n  {svc.upper()}")
            print(f"    Activated:  {activated.strftime('%Y-%m-%d %H:%M UTC')}")
            print(f"    Kill-date:  {kill_date.strftime('%Y-%m-%d')}")
            print(f"    Days live:  {days_live}")
            print(f"    Days left:  {days_left}  {flag}")
        else:
            print(f"\n  {svc.upper()}: Not in evidence log")
    print("\n  Lambda: arn:aws:lambda:us-east-2:759729568430:function:trishula-trial-killshot")
    print("  Rules:  trishula-forecast-hardkill | trishula-sagemaker-hardkill")
    print("="*55 + "\n")

def kill_now(service="all"):
    print(f"\n  MANUAL KILL-SHOT FIRED: {service.upper()}")
    lc = boto3.client("lambda", region_name=REGION,
                      aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                      aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"))
    payload = json.dumps({"service": service, "reason": "manual_kill",
                           "ts": datetime.now(timezone.utc).isoformat()})
    r  = lc.invoke(FunctionName="trishula-trial-killshot",
                   InvocationType="RequestResponse", Payload=payload.encode())
    result = json.loads(r["Payload"].read())
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trishula Trial Hard-Kill")
    parser.add_argument("--status",   action="store_true")
    parser.add_argument("--kill-now", action="store_true")
    parser.add_argument("--service",  default="all", choices=["all","forecast","sagemaker"])
    args = parser.parse_args()
    if args.kill_now:
        kill_now(args.service)
    else:
        status()
