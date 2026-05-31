#!/usr/bin/env python3
"""
TRISHULA -- AZURE COSMOS DB FREE TIER SETUP
============================================
Provisions Azure Cosmos DB (always-free 1,000 RU/s + 25GB)
and wires store_cosmos.py for picks + line history redundancy.

Free tier: 1 account per subscription, permanently free.
Create at: portal.azure.com -> Create Resource -> Azure Cosmos DB -> Core (SQL) API

Settings:
  Name:         trishula-cosmos
  API:          Core (SQL) -- NoSQL
  Region:       East US
  Free tier:    Apply Free Tier Discount -> ON
  Capacity:     Serverless OR Provisioned (free tier = 1000 RU/s)

After creation:
  Keys blade -> copy PRIMARY CONNECTION STRING
  Run: python setup_cosmos.py --conn "<connection string>"
"""

import os, json, sys, argparse, requests
from pathlib import Path

ENV_PATH = Path(r"H:\Trishula\Swarm_4_Integration\Swarm_4_SBM_FINAL INTEGRATION\Project-Swarm\trishula-market-data\.env")

COSMOS_DB   = "trishula"
COLLECTIONS = {
    "qmatrix_snapshots": "/symbol",
    "picks_history":     "/sport",
    "line_history":      "/sport",
    "discord_log":       "/channel",
}

def update_env(key, value):
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    updated = False
    new_lines = []
    for line in lines:
        if line.startswith(key + "="):
            new_lines.append(f"{key}={value}")
            updated = True
        else:
            new_lines.append(line)
    if not updated:
        new_lines.append(f"{key}={value}")
    ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

def get_cosmos_headers(account_name, master_key, verb, resource_type, resource_id, date_str):
    """Generate Cosmos DB REST auth headers."""
    import hmac, hashlib, base64
    text = f"{verb.lower()}\n{resource_type.lower()}\n{resource_id}\n{date_str.lower()}\n\n"
    key  = base64.b64decode(master_key)
    sig  = base64.b64encode(hmac.new(key, text.encode("utf-8"), hashlib.sha256).digest()).decode()
    return f"type=master&ver=1.0&sig={sig}"

def test_cosmos(endpoint, key):
    """Test Cosmos DB connectivity — list databases."""
    from datetime import datetime, timezone
    date_str = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
    auth = get_cosmos_headers("", key, "GET", "dbs", "", date_str)
    headers = {
        "Authorization": requests.utils.quote(auth),
        "x-ms-date": date_str,
        "x-ms-version": "2018-12-31",
        "Content-Type": "application/json",
    }
    r = requests.get(f"{endpoint.rstrip('/')}/dbs", headers=headers, timeout=15)
    if r.status_code in (200, 201):
        dbs = [d["id"] for d in r.json().get("Databases", [])]
        print(f"  [PASS] Cosmos DB connected — databases: {dbs or ['(empty, ready)']}")
        return True
    else:
        print(f"  [FAIL] Cosmos: HTTP {r.status_code} — {r.text[:100]}")
        return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--conn", help="Cosmos DB primary connection string")
    parser.add_argument("--endpoint", help="Cosmos DB endpoint URL")
    parser.add_argument("--key",  help="Cosmos DB primary key")
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()

    if args.test or (not args.conn and not args.endpoint):
        print(__doc__)
        print("\nAzure Portal Steps:")
        print("  1. portal.azure.com -> Create a resource")
        print("  2. Search: 'Azure Cosmos DB'")
        print("  3. Select: Azure Cosmos DB for NoSQL")
        print("  4. Apply Free Tier Discount: YES")
        print("  5. Region: East US | Name: trishula-cosmos")
        print("  6. After creation: Keys blade -> copy PRIMARY CONNECTION STRING")
        print("  7. Run: python setup_cosmos.py --conn \"AccountEndpoint=...\"")
        return

    # Parse connection string
    if args.conn:
        parts = dict(p.split("=", 1) for p in args.conn.split(";") if "=" in p)
        endpoint = parts.get("AccountEndpoint", "")
        key      = parts.get("AccountKey", "")
    else:
        endpoint = args.endpoint
        key      = args.key

    print(f"\n  Endpoint: {endpoint}")
    print(f"  Key:      {key[:8]}...\n")

    # Save to .env
    update_env("COSMOS_ENDPOINT", endpoint)
    update_env("COSMOS_KEY",      key)
    print("  [OK] Saved to .env")

    # Test connectivity
    print("  Testing connection...")
    test_cosmos(endpoint, key)

if __name__ == "__main__":
    main()
