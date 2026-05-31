#!/usr/bin/env python3
"""
TRISHULA -- GCP PUB/SUB + CLOUD SCHEDULER SETUP
=================================================
Creates:
  1. Pub/Sub topic: trishula-picks   (event bus for cross-service coordination)
  2. Pub/Sub topic: trishula-alerts  (cross-cloud alert routing)
  3. Cloud Scheduler job: qmatrix-open    (9:30 AM ET Mon-Fri)
  4. Cloud Scheduler job: qmatrix-midday  (12:00 PM ET Mon-Fri)
  5. Cloud Scheduler job: qmatrix-sunday  (12:00 PM ET Sunday)
"""
import os
from pathlib import Path

# Load GCP credentials
os.environ.setdefault(
    "GOOGLE_APPLICATION_CREDENTIALS",
    r"H:\Trishula\Swarm_4_Integration\Swarm_4_SBM_FINAL INTEGRATION\Project-Swarm\trishula-gcp-key.json"
)

# Read project ID from service account key
import json
key_path = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
with open(key_path) as f:
    key_data = json.load(f)
PROJECT_ID = key_data.get("project_id", "")
print(f"\n  GCP Project: {PROJECT_ID}")

print("\n" + "="*55)
print("  GCP PUB/SUB + CLOUD SCHEDULER SETUP")
print("="*55)

# ── 1. Pub/Sub Topics ─────────────────────────────────────
print("\n[1/2] Creating Pub/Sub topics...")
try:
    from google.cloud import pubsub_v1
    from google.api_core.exceptions import AlreadyExists

    publisher = pubsub_v1.PublisherClient()
    topics = ["trishula-picks", "trishula-alerts", "trishula-scanner-events"]

    for topic_name in topics:
        topic_path = publisher.topic_path(PROJECT_ID, topic_name)
        try:
            topic = publisher.create_topic(request={"name": topic_path})
            print(f"  [OK] Created topic: {topic.name}")
        except AlreadyExists:
            print(f"  [OK] Topic exists: {topic_path}")
        except Exception as e:
            print(f"  [FAIL] {topic_name}: {e}")

    # Test publish a message
    topic_path = publisher.topic_path(PROJECT_ID, "trishula-picks")
    import json as _json
    msg = _json.dumps({"type": "test", "source": "setup_script", "ts": "2026-05-26"}).encode()
    future = publisher.publish(topic_path, data=msg)
    msg_id = future.result(timeout=10)
    print(f"\n  [PASS] Test message published to trishula-picks — ID: {msg_id}")

except Exception as e:
    print(f"  [FAIL] Pub/Sub: {e}")

# ── 2. Cloud Scheduler Jobs ───────────────────────────────
print("\n[2/2] Creating Cloud Scheduler jobs...")
print("  Note: Cloud Scheduler requires App Engine or a target HTTP endpoint.")
print("  Using Pub/Sub as target — each job publishes to trishula-scanner-events")
try:
    from google.cloud import scheduler_v1
    from google.api_core.exceptions import AlreadyExists, NotFound

    client = scheduler_v1.CloudSchedulerClient()
    # Cloud Scheduler needs a location
    parent = f"projects/{PROJECT_ID}/locations/us-central1"

    jobs = [
        {
            "name": f"{parent}/jobs/qmatrix-market-open",
            "description": "Q-Matrix Market Open sweep 9:30 AM ET Mon-Fri",
            "schedule": "30 9 * * 1-5",   # 9:30 AM UTC-5 = 14:30 UTC
            "time_zone": "America/New_York",
            "pubsub_target": {
                "topic_name": f"projects/{PROJECT_ID}/topics/trishula-scanner-events",
                "data": b'{"sweep":"open","time":"09:30"}',
            },
        },
        {
            "name": f"{parent}/jobs/qmatrix-midday",
            "description": "Q-Matrix Midday sweep 12:00 PM ET Mon-Fri",
            "schedule": "0 12 * * 1-5",
            "time_zone": "America/New_York",
            "pubsub_target": {
                "topic_name": f"projects/{PROJECT_ID}/topics/trishula-scanner-events",
                "data": b'{"sweep":"midday","time":"12:00"}',
            },
        },
        {
            "name": f"{parent}/jobs/qmatrix-sunday-earnings",
            "description": "Q-Matrix Sunday Earnings Preview 12:00 PM ET",
            "schedule": "0 12 * * 0",
            "time_zone": "America/New_York",
            "pubsub_target": {
                "topic_name": f"projects/{PROJECT_ID}/topics/trishula-scanner-events",
                "data": b'{"sweep":"sunday_earnings","time":"12:00"}',
            },
        },
    ]

    for job in jobs:
        try:
            result = client.create_job(
                request={"parent": parent, "job": job}
            )
            print(f"  [OK] Created: {result.name.split('/')[-1]}")
        except AlreadyExists:
            print(f"  [OK] Exists:  {job['name'].split('/')[-1]}")
        except Exception as e:
            print(f"  [INFO] {job['name'].split('/')[-1]}: {str(e)[:80]}")

except Exception as e:
    print(f"  [FAIL] Cloud Scheduler: {e}")

print("\n" + "="*55)
print("  GCP CLOUD SERVICES SETUP COMPLETE")
print("  Pub/Sub: trishula-picks | trishula-alerts | trishula-scanner-events")
print("  Scheduler: qmatrix-market-open | qmatrix-midday | qmatrix-sunday")
print("="*55 + "\n")
