#!/usr/bin/env python3
"""
AWS Step Functions — Create sovereign orchestrator state machine.
Free tier: 4,000 state transitions/month forever.
"""
import boto3, json
from datetime import datetime, timezone

NOW = datetime.now(timezone.utc).isoformat()

sf = boto3.client('stepfunctions', region_name='us-east-2')

# Simple state machine definition — orchestrator scaffold
STATE_MACHINE = {
    "Comment": "Trishula Sovereign Swarm Orchestrator",
    "StartAt": "TriggerDataAgent",
    "States": {
        "TriggerDataAgent": {
            "Type": "Task",
            "Resource": "arn:aws:states:::lambda:invoke",
            "Parameters": {
                "FunctionName": "trishula-trial-killshot",
                "Payload": {"action": "health_check"}
            },
            "Next": "TriggerAnalysisAgent",
            "Catch": [{"ErrorEquals": ["States.ALL"], "Next": "OrchestratorFailed"}]
        },
        "TriggerAnalysisAgent": {
            "Type": "Pass",
            "Comment": "Wire to Analysis Agent in Phase 3",
            "Result": {"status": "analysis_triggered"},
            "Next": "TriggerDiscordAgent"
        },
        "TriggerDiscordAgent": {
            "Type": "Pass",
            "Comment": "Wire to Discord Agent in Phase 3",
            "Result": {"status": "dispatch_triggered"},
            "End": True
        },
        "OrchestratorFailed": {
            "Type": "Fail",
            "Error": "OrchestratorError",
            "Cause": "Swarm orchestration step failed"
        }
    }
}

# Get Lambda ARN for execution role
iam = boto3.client('iam', region_name='us-east-2')
try:
    # Create execution role for Step Functions
    assume_role = {
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "states.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }
    try:
        role = iam.create_role(
            RoleName='trishula-stepfunctions-role',
            AssumeRolePolicyDocument=json.dumps(assume_role),
            Description='Trishula Step Functions execution role'
        )
        role_arn = role['Role']['Arn']
        # Attach Lambda invoke permission
        iam.attach_role_policy(
            RoleName='trishula-stepfunctions-role',
            PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaRole'
        )
        print(f"  [OK] IAM Role created: {role_arn}")
    except iam.exceptions.EntityAlreadyExistsException:
        role = iam.get_role(RoleName='trishula-stepfunctions-role')
        role_arn = role['Role']['Arn']
        print(f"  [OK] IAM Role exists: {role_arn}")

    # Create state machine
    try:
        sm = sf.create_state_machine(
            name='trishula-sovereign-orchestrator',
            definition=json.dumps(STATE_MACHINE),
            roleArn=role_arn,
            type='STANDARD',
            tags=[
                {'key': 'Project', 'value': 'trishula-swarm'},
                {'key': 'CostCenter', 'value': 'free-tier'},
                {'key': 'Phase', 'value': 'orchestrator'},
            ]
        )
        sm_arn = sm['stateMachineArn']
        print(f"\n[STEP FUNCTIONS] LIVE")
        print(f"  ARN:     {sm_arn}")
        print(f"  Name:    trishula-sovereign-orchestrator")
        print(f"  Free:    4,000 transitions/month forever")

    except sf.exceptions.StateMachineAlreadyExists:
        sms = sf.list_state_machines()
        existing = [m for m in sms['stateMachines'] if 'trishula' in m['name'].lower()]
        if existing:
            sm_arn = existing[0]['stateMachineArn']
            print(f"\n[STEP FUNCTIONS] LIVE - already exists")
            print(f"  ARN: {sm_arn}")
        else:
            sm_arn = "exists"

except Exception as e:
    print(f"[STEP FUNCTIONS] ERROR: {str(e)[:200]}")
    sm_arn = None

if sm_arn:
    import os
    env_path = r"H:\Trishula\Swarm_4_Integration\Swarm_4_SBM_FINAL INTEGRATION\Project-Swarm\trishula-market-data\.env"
    with open(env_path, 'a', encoding='utf-8') as f:
        f.write(f"\n# -- AWS STEP FUNCTIONS (4K transitions/mo free) -------------------------\n")
        f.write(f"AWS_STATE_MACHINE_ARN={sm_arn}\n")
        f.write(f"AWS_STATE_MACHINE_NAME=trishula-sovereign-orchestrator\n")
    print(f"  [OK] Wired to .env")
