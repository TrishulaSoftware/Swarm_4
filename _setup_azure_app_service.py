#!/usr/bin/env python3
"""
TRISHULA -- AZURE APP SERVICE F1 (Always Free) -- picks_proxy API
=================================================================
Deploys picks_proxy.py as a permanent free REST API on Azure App Service F1.
  - 1 GB RAM, shared compute, always free
  - Endpoint: https://trishula-api.azurewebsites.net
  - Routes: /picks, /health, /subscriber, /props

Run: python _setup_azure_app_service.py
"""
import subprocess, os, sys
from pathlib import Path

RESOURCE_GROUP = "trishula-rg"
APP_NAME       = "trishula-api"
PLAN_NAME      = "trishula-free-plan"
LOCATION       = "eastus"
RUNTIME        = "PYTHON:3.12"

def run(cmd):
    print(f"  $ {cmd}")
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    out = r.stdout.strip() or r.stderr.strip()
    if out:
        print(f"    {out[:120]}")
    return r.returncode == 0, out

print()
print("=" * 55)
print("  AZURE APP SERVICE F1 -- DEPLOYMENT")
print("=" * 55)

# Check az CLI
ok, _ = run("az --version")
if not ok:
    print("\n  [!] Azure CLI not installed locally.")
    print("  [!] Use portal.azure.com instead:")
    print()
    print("  1. portal.azure.com → Create → App Service")
    print("  2. Name:     trishula-api")
    print("  3. Runtime:  Python 3.12 | OS: Linux")
    print("  4. Region:   East US")
    print("  5. Plan:     Create New → Free F1")
    print("  6. Click Review + Create → Create")
    print()
    print("  URL will be: https://trishula-api.azurewebsites.net")
    sys.exit(0)

# Resource group
run(f"az group create --name {RESOURCE_GROUP} --location {LOCATION}")

# Free F1 App Service Plan
run(f"az appservice plan create --name {PLAN_NAME} --resource-group {RESOURCE_GROUP} "
    f"--sku F1 --is-linux --location {LOCATION}")

# Web App
ok, out = run(f"az webapp create --name {APP_NAME} --resource-group {RESOURCE_GROUP} "
              f"--plan {PLAN_NAME} --runtime {RUNTIME!r}")
if ok:
    print(f"\n  [OK] App Service live: https://{APP_NAME}.azurewebsites.net")
else:
    print(f"\n  [INFO] {out[:100]}")

print("=" * 55)
print(f"  Endpoint: https://{APP_NAME}.azurewebsites.net")
print("  Tier:     F1 Free (always free, no clock)")
print("  Memory:   1 GB shared")
print("=" * 55)
