#!/usr/bin/env python3
"""Stamp kill-switch evidence file with trial activation dates."""
import json, os
from datetime import datetime, timezone, timedelta

EVIDENCE_PATH = r'H:\Trishula\Swarm_4_Integration\Salvo_Staging\aws_trial_evidence.json'
NOW = datetime.now(timezone.utc)

evidence = {}
if os.path.exists(EVIDENCE_PATH):
    with open(EVIDENCE_PATH, 'r') as f:
        try:
            evidence = json.load(f)
        except Exception:
            evidence = {}

# Forecast — 3 month trial
evidence['forecast_activated']       = NOW.isoformat()
evidence['forecast_kill_date']       = (NOW + timedelta(days=90)).isoformat()
evidence['forecast_kill_date_human'] = (NOW + timedelta(days=90)).strftime('%Y-%m-%d')
evidence['forecast_status']          = 'LIVE'

# SageMaker — 2 month trial
evidence['sagemaker_activated']      = NOW.isoformat()
evidence['sagemaker_kill_date']      = (NOW + timedelta(days=60)).isoformat()
evidence['sagemaker_status']         = 'LIVE'

# Always-free services
evidence['polly_status']             = 'LIVE'
evidence['lex_status']               = 'LIVE'
evidence['step_functions_status']    = 'LIVE'
evidence['last_updated']             = NOW.isoformat()

with open(EVIDENCE_PATH, 'w') as f:
    json.dump(evidence, f, indent=2)

print('[OK] Kill-switch evidence stamped')
print(f'  Forecast kill date: {evidence["forecast_kill_date_human"]}')
print(f'  File: {EVIDENCE_PATH}')
