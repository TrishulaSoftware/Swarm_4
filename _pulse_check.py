#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Trishula Swarm Pulse Check"""
import boto3, json, subprocess
from datetime import datetime, timezone
from pathlib import Path

NOW = datetime.now(timezone.utc)
results = {}

# AWS
try:
    ddb = boto3.client('dynamodb', region_name='us-east-2')
    tables = ddb.list_tables()['TableNames']
    results['DynamoDB'] = f'LIVE - {len(tables)} tables: {tables}'
except Exception as e:
    results['DynamoDB'] = f'ERROR: {str(e)[:50]}'

try:
    lam = boto3.client('lambda', region_name='us-east-2')
    fns = [f['FunctionName'] for f in lam.list_functions()['Functions']]
    results['Lambda'] = f'LIVE - {fns}'
except Exception as e:
    results['Lambda'] = f'ERROR: {str(e)[:50]}'

try:
    sqs = boto3.client('sqs', region_name='us-east-2')
    queues = sqs.list_queues().get('QueueUrls', [])
    results['SQS'] = f'LIVE - {len(queues)} queue(s)'
except Exception as e:
    results['SQS'] = f'ERROR: {str(e)[:50]}'

try:
    sns = boto3.client('sns', region_name='us-east-2')
    topics = sns.list_topics()['Topics']
    results['SNS'] = f'LIVE - {len(topics)} topic(s)'
except Exception as e:
    results['SNS'] = f'ERROR: {str(e)[:50]}'

try:
    eb = boto3.client('events', region_name='us-east-2')
    rules = eb.list_rules()['Rules']
    names = [r['Name'] for r in rules]
    results['EventBridge'] = f'LIVE - {len(rules)} rules: {names}'
except Exception as e:
    results['EventBridge'] = f'ERROR: {str(e)[:50]}'

try:
    sfn = boto3.client('stepfunctions', region_name='us-east-2')
    sms = sfn.list_state_machines()['stateMachines']
    results['StepFunctions'] = f'LIVE - {[s["name"] for s in sms]}'
except Exception as e:
    results['StepFunctions'] = f'ERROR: {str(e)[:50]}'

try:
    pl = boto3.client('polly', region_name='us-east-2')
    voices = pl.describe_voices(LanguageCode='en-US')['Voices']
    results['Polly'] = f'LIVE - {len(voices)} voices'
except Exception as e:
    results['Polly'] = f'ERROR: {str(e)[:50]}'

try:
    fc = boto3.client('forecast', region_name='us-east-2')
    fc.list_datasets()
    results['Forecast'] = 'LIVE'
except Exception as e:
    results['Forecast'] = f'ERROR: {str(e)[:50]}'

try:
    cf = boto3.client('cloudfront', region_name='us-east-1')
    dists = cf.list_distributions().get('DistributionList', {}).get('Items', [])
    results['CloudFront'] = f'LIVE - {len(dists)} distribution(s)'
except Exception as e:
    results['CloudFront'] = f'ERROR: {str(e)[:50]}'

try:
    lx = boto3.client('lexv2-models', region_name='us-east-1')
    bots = lx.list_bots()['botSummaries']
    results['Lex-V2'] = f'LIVE - {bots[0]["botName"]} ({bots[0]["botStatus"]})' if bots else 'LIVE - 0 bots'
except Exception as e:
    results['Lex-V2'] = f'ERROR: {str(e)[:50]}'

results['Comprehend'] = 'PROPAGATING (auto-clear tonight)'
results['Textract']   = 'PROPAGATING (auto-clear tonight)'

# GCP
import os
GCP_KEY = r'H:\Trishula\Swarm_4_Integration\trishula-gcp-key.json'
if os.path.exists(GCP_KEY):
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = GCP_KEY

try:
    from google.cloud import storage as gcs
    buckets = list(gcs.Client().list_buckets())
    results['GCS'] = f'LIVE - {[b.name for b in buckets]}'
except Exception as e:
    results['GCS'] = f'ERROR: {str(e)[:50]}'

try:
    from google.cloud import tasks_v2
    tc = tasks_v2.CloudTasksClient()
    q = tc.get_queue(name='projects/gcp-swarm-491812/locations/us-central1/queues/trishula-task-queue')
    results['CloudTasks'] = 'LIVE - trishula-task-queue'
except Exception as e:
    results['CloudTasks'] = f'ERROR: {str(e)[:50]}'

# Kill-switch
evidence_path = Path(r'H:\Trishula\Swarm_4_Integration\Salvo_Staging\aws_trial_evidence.json')
kill_status = {}
if evidence_path.exists():
    evidence = json.loads(evidence_path.read_text())
    for svc in ['forecast', 'sagemaker']:
        key = f'{svc}_kill_date'
        if key in evidence:
            kill_dt = datetime.fromisoformat(evidence[key])
            days_left = (kill_dt - NOW).days
            kill_status[svc] = f'{evidence[key][:10]} ({days_left}d left)'

# Scheduler
sched_status = {}
try:
    res = subprocess.run(
        ['powershell', '-Command',
         'Get-ScheduledTask | Where-Object { $_.TaskName -match "QMatrix" } | Select-Object TaskName, State | ConvertTo-Json'],
        capture_output=True, text=True, timeout=10
    )
    if res.returncode == 0 and res.stdout.strip():
        tasks = json.loads(res.stdout)
        if isinstance(tasks, dict): tasks = [tasks]
        for t in tasks:
            state = 'Ready' if t.get('State') == 3 else f'State={t.get("State")}'
            sched_status[t['TaskName']] = state
except Exception:
    sched_status['error'] = 'scheduler query failed'

# Output for pulse
print(json.dumps({
    'timestamp': NOW.isoformat(),
    'aws': {k: v for k, v in results.items()},
    'kill_switch': kill_status,
    'scheduler': sched_status
}, indent=2))

