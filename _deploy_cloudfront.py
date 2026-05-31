#!/usr/bin/env python3
"""CloudFront CDN activation."""
import boto3, json
from datetime import datetime, timezone

NOW = datetime.now(timezone.utc).isoformat()
REF = "trishula-cdn-" + NOW[:10]
PORTAL = "mango-river-018d1da0f.7.azurestaticapps.net"

cf = boto3.client("cloudfront", region_name="us-east-1")

try:
    dist = cf.create_distribution(
        DistributionConfig={
            "CallerReference": REF,
            "Comment": "Trishula Sovereign Swarm CDN",
            "DefaultCacheBehavior": {
                "TargetOriginId": "trishula-portal",
                "ViewerProtocolPolicy": "redirect-to-https",
                "CachePolicyId": "658327ea-f89d-4fab-a63d-7e88639e58f6",
                "AllowedMethods": {
                    "Quantity": 2,
                    "Items": ["HEAD", "GET"],
                    "CachedMethods": {"Quantity": 2, "Items": ["HEAD", "GET"]},
                },
            },
            "Origins": {
                "Quantity": 1,
                "Items": [{
                    "Id": "trishula-portal",
                    "DomainName": PORTAL,
                    "CustomOriginConfig": {
                        "HTTPPort": 80,
                        "HTTPSPort": 443,
                        "OriginProtocolPolicy": "https-only",
                    },
                }],
            },
            "Enabled": True,
            "PriceClass": "PriceClass_100",
        }
    )
    domain = dist["Distribution"]["DomainName"]
    cf_id  = dist["Distribution"]["Id"]
    print("[CLOUDFRONT] LIVE")
    print("  ID:     " + cf_id)
    print("  CDN:    https://" + domain)
    print("  Origin: " + PORTAL)
    print("  Note:   5-15 min global propagation")

    # Update evidence file
    try:
        with open("aws_public_exposure.json", "r") as f:
            ev = json.load(f)
        ev["cloudfront"] = {"status": "LIVE", "id": cf_id, "domain": domain, "activated": NOW}
        with open("aws_public_exposure.json", "w") as f:
            json.dump(ev, f, indent=2)
        print("  Saved: aws_public_exposure.json")
    except Exception:
        pass

except Exception as e:
    print("[CLOUDFRONT ERROR] " + str(e)[:200])
