#!/usr/bin/env python3
"""Create GCP Cloud Tasks queue."""
import os
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'H:\Trishula\Swarm_4_Integration\trishula-gcp-key.json'

from google.cloud import tasks_v2

PROJECT = 'gcp-swarm-491812'
LOCATION = 'us-central1'
QUEUE_ID = 'trishula-task-queue'

client = tasks_v2.CloudTasksClient()

parent = f"projects/{PROJECT}/locations/{LOCATION}"
queue_name = f"{parent}/queues/{QUEUE_ID}"

queue = tasks_v2.Queue(
    name=queue_name,
    retry_config=tasks_v2.RetryConfig(max_attempts=3),
)

try:
    q = client.create_queue(parent=parent, queue=queue)
    print('[CLOUD TASKS] LIVE')
    print('  Queue:', q.name)
    print('  State:', q.state)
except Exception as e:
    err = str(e)
    if 'ALREADY_EXISTS' in err or 'already exists' in err.lower():
        print('[CLOUD TASKS] LIVE - queue already exists')
        try:
            q = client.get_queue(name=queue_name)
            print('  Queue:', q.name)
        except Exception:
            pass
    else:
        print('[CLOUD TASKS] ERROR:', err[:200])
