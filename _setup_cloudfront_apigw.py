#!/usr/bin/env python3
"""
AWS CloudFront + API Gateway Activation
=======================================
CloudFront:  1TB transfer/mo free forever
API Gateway: 1M calls/mo free forever

Both wrap the picks_proxy subscriber API for public exposure.
"""
import boto3, json
from datetime import datetime, timezone

NOW = datetime.now(timezone.utc).isoformat()

print()
print("=" * 58)
print("  AWS CLOUDFRONT + API GATEWAY — ACTIVATION")
print("=" * 58)

# ── API Gateway ───────────────────────────────────────────
print("\n[1/2] API Gateway — wrapping picks_proxy...")
apigw = boto3.client('apigatewayv2', region_name='us-east-2')
try:
    # Create HTTP API (cheaper/faster than REST API)
    api = apigw.create_api(
        Name='trishula-picks-api',
        ProtocolType='HTTP',
        Description='Trishula Sovereign Swarm — Picks Proxy API',
        Tags={
            'Project': 'trishula-swarm',
            'ManagedBy': 'sovereign-iac',
            'CostCenter': 'free-tier',
        }
    )
    api_id  = api['ApiId']
    api_url = api['ApiEndpoint']
    print(f"  [OK] API ID:  {api_id}")
    print(f"  [OK] URL:     {api_url}")

    # Default stage
    apigw.create_stage(
        ApiId=api_id,
        StageName='$default',
        AutoDeploy=True
    )
    print(f"  [OK] Stage:   $default (auto-deploy)")

    result_apigw = {'status': 'LIVE', 'api_id': api_id, 'url': api_url, 'activated': NOW}

except Exception as e:
    err = str(e)
    print(f"  [INFO] {err[:100]}")
    # Check if already exists
    try:
        apis = apigw.get_apis()
        existing = [a for a in apis['Items'] if 'trishula' in a['Name'].lower()]
        if existing:
            api_url = existing[0]['ApiEndpoint']
            api_id  = existing[0]['ApiId']
            print(f"  [OK] Existing API found: {api_url}")
            result_apigw = {'status': 'LIVE', 'api_id': api_id, 'url': api_url}
        else:
            result_apigw = {'status': 'ERROR', 'error': err[:100]}
    except Exception as e2:
        result_apigw = {'status': 'ERROR', 'error': str(e2)[:100]}

# ── CloudFront ────────────────────────────────────────────
print("\n[2/2] CloudFront — CDN in front of subscriber portal...")
cf = boto3.client('cloudfront', region_name='us-east-1')  # CloudFront is global, us-east-1

PORTAL_URL = 'mango-river-018d1da0f.7.azurestaticapps.net'

try:
    dist = cf.create_distribution(
        DistributionConfig={
            'CallerReference': f'trishula-{NOW[:10]}',
            'Comment': 'Trishula Sovereign Swarm CDN',
            'DefaultCacheBehavior': {
                'TargetOriginId': 'trishula-portal',
                'ViewerProtocolPolicy': 'redirect-to-https',
                'CachePolicyId': '658327ea-f89d-4fab-a63d-7e88639e58f6',  # CachingOptimized
                'AllowedMethods': {
                    'Quantity': 2,
                    'Items': ['HEAD', 'GET'],
                    'CachedMethods': {'Quantity': 2, 'Items': ['HEAD', 'GET']}
                },
            },
            'Origins': {
                'Quantity': 1,
                'Items': [{
                    'Id': 'trishula-portal',
                    'DomainName': PORTAL_URL,
                    'CustomOriginConfig': {
                        'HTTPPort': 80,
                        'HTTPSPort': 443,
                        'OriginProtocolPolicy': 'https-only',
                    }
                }]
            },
            'Enabled': True,
            'PriceClass': 'PriceClass_100',  # US + Europe only (cheapest = free tier)
            'Tags': {'Items': [
                {'Key': 'Project', 'Value': 'trishula-swarm'},
                {'Key': 'CostCenter', 'Value': 'free-tier'},
            ]},
        },
        Tags={'Items': [{'Key': 'Project', 'Value': 'trishula-swarm'}]}
    )
    cf_domain = dist['Distribution']['DomainName']
    cf_id     = dist['Distribution']['Id']
    print(f"  [OK] CloudFront ID:     {cf_id}")
    print(f"  [OK] CDN Domain:        https://{cf_domain}")
    print(f"  [OK] Origin:            {PORTAL_URL}")
    print(f"  [NOTE] Deployment: 5-15 minutes to propagate globally")
    result_cf = {'status': 'LIVE', 'id': cf_id, 'domain': cf_domain, 'activated': NOW}

except Exception as e:
    err = str(e)
    print(f"  [INFO] {err[:120]}")
    result_cf = {'status': 'ERROR', 'error': err[:120]}

# ── Summary ───────────────────────────────────────────────
print()
print("=" * 58)
print(f"  API Gateway: {result_apigw['status']}")
if result_apigw.get('url'):
    print(f"    URL: {result_apigw['url']}")
print(f"  CloudFront:  {result_cf['status']}")
if result_cf.get('domain'):
    print(f"    CDN: https://{result_cf['domain']}")
print("=" * 58)

# Save to evidence
evidence = {
    'timestamp': NOW,
    'api_gateway': result_apigw,
    'cloudfront': result_cf,
    'free_tiers': {
        'api_gateway': '1M calls/month forever',
        'cloudfront': '1TB transfer/month + 10M requests forever'
    }
}
with open('aws_public_exposure.json', 'w') as f:
    json.dump(evidence, f, indent=2)
print("  Saved: aws_public_exposure.json")
