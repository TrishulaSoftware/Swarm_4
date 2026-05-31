# -*- coding: utf-8 -*-
"""
TRISHULA CLOUD ARBITRAGE v4.1 — SUBSCRIBER API PROXY LAMBDA
Description: Runs on AWS us-west-2 (Account 2). Assumes role into Account 1 us-east-1
             to pull live MLB picks, filters by API key validation and subscription tier.
"""

import os
import json
import boto3
from datetime import datetime

def lambda_handler(event, context):
    print("Received API Event: ", json.dumps(event))
    
    # 1. API Key Authentication (x-api-key header)
    headers = event.get("headers", {})
    api_key = headers.get("x-api-key") or headers.get("X-API-Key")
    
    if not api_key:
        return {
            "statusCode": 401,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Missing x-api-key authentication header."})
        }

    # Connect to Account 2 local DynamoDB to validate the API key
    dynamodb_local = boto3.resource("dynamodb", region_name="us-west-2")
    keys_table = dynamodb_local.Table("trishula_api_keys")
    
    key_entry = keys_table.get_item(Key={"api_key": api_key})
    if "Item" not in key_entry:
        return {
            "statusCode": 403,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Unauthorized or invalid x-api-key."})
        }
        
    subscriber = key_entry["Item"]
    tier = subscriber.get("tier", "Scout") # Scout, Analyst, Pro, Black
    status = subscriber.get("status", "ACTIVE")
    
    if status != "ACTIVE":
        return {
            "statusCode": 402,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Subscription suspended, pending payment reconciliation."})
        }

    # 2. Assume Role into Account 1 to read trishula_picks_log (Read-Only cross-account role)
    role_arn = os.environ.get("ACCT1_DYNAMO_ROLE", "arn:aws:iam::111111111111:role/trishula-cross-account-reader")
    sts_client = boto3.client("sts")
    
    try:
        assumed_role = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName="TrishulaCrossAccountPicksProxy"
        )
        credentials = assumed_role["Credentials"]
        
        # Connect to Account 1 us-east-1 DynamoDB picks log using temporary STS credentials
        dynamodb_acct1 = boto3.resource(
            "dynamodb",
            region_name="us-east-1",
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"]
        )
        
        picks_table = dynamodb_acct1.Table("trishula_picks_log")
        # Query picks for the active system date
        today_date = datetime.now().strftime("%Y-%m-%d")
        
        # We can scan or query with partition key. Let's do standard scan for demonstration
        response = picks_table.scan()
        all_picks = response.get("Items", [])
        
    except Exception as e:
        print(f"[ERR] STS Assume Role / Cross-account query failed: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Failed to authenticate cross-account datastore tunnel.", "details": str(e)})
        }

    # 3. Filter Output according to Subscription Tier
    # TIER LEVELS:
    # Scout   --> Standard game lines, ML/Spread, low confidence (confidence < 85%)
    # Analyst --> Adds high-confidence batting/pitching props (confidence < 90%)
    # Pro     --> Adds F5 / Alternate / 1st Inning locks (confidence < 95%)
    # Black   --> UNRESTRICTED. Access to 100% of picks and dedicated 95%+ LOCKS.
    
    filtered_picks = []
    for pick in all_picks:
        conf_str = pick.get("confidence", "70%").replace("%", "")
        try:
            confidence = int(conf_str)
        except ValueError:
            confidence = 70
            
        is_lock = confidence >= 90
        
        if tier == "Black":
            filtered_picks.append(pick)
        elif tier == "Pro":
            if confidence < 95:
                filtered_picks.append(pick)
        elif tier == "Analyst":
            if confidence < 90:
                filtered_picks.append(pick)
        else: # Default: Scout
            if confidence < 85 and not is_lock:
                filtered_picks.append(pick)

    # 4. Log usage in Account 2 trishula_usage_log for metering & rate-limiting
    usage_table = dynamodb_local.Table("trishula_usage_log")
    usage_table.put_item(
        Item={
            "api_key": api_key,
            "timestamp": int(datetime.utcnow().timestamp()),
            "tier": tier,
            "picks_count": len(filtered_picks),
            "endpoint": event.get("rawPath", "/v1/picks")
        }
    )

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*" # Support browser static web app dashboard calls
        },
        "body": json.dumps({
            "tier": tier,
            "status": "SUCCESS",
            "timestamp": datetime.utcnow().isoformat(),
            "picks_count": len(filtered_picks),
            "picks": filtered_picks
        }, indent=2)
    }
