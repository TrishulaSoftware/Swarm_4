# 🔱 TRISHULA SOVEREIGN SWARM — RESOURCE MANIFEST
# ===================================================
# Generated: 2026-05-28 · Health snapshot: 2026-05-28T14:49:54Z
# Live: 35/76 · Propagating: 6 · Unprovisioned: 35
# Monthly Cost: $0.00

---

## LEGEND
- ✅ LIVE — confirmed active
- ⏳ PROPAGATING — activated, awaiting service propagation
- 🔧 UNPROVISIONED — planned, not yet activated
- 🔑 ARN/OCID provided where available

---

## ☁️ AWS RESOURCES (12 live / 21 total)

| # | Resource | Type | ID / ARN | Status |
|---|----------|------|----------|--------|
| 1 | trishula-trial-killshot | Lambda Function | `arn:aws:lambda:us-east-2:759729568430:function:trishula-trial-killshot` | ✅ LIVE |
| 2 | trishula_injury_seen | DynamoDB Table | `arn:aws:dynamodb:us-east-2:759729568430:table/trishula_injury_seen` | ✅ LIVE |
| 3 | trishula_picks_log | DynamoDB Table | `arn:aws:dynamodb:us-east-2:759729568430:table/trishula_picks_log` | ✅ LIVE |
| 4 | trishula_rlm_lines | DynamoDB Table | `arn:aws:dynamodb:us-east-2:759729568430:table/trishula_rlm_lines` | ✅ LIVE |
| 5 | trishula_state_store | DynamoDB Table | `arn:aws:dynamodb:us-east-2:759729568430:table/trishula_state_store` | ✅ LIVE |
| 6 | trishula-sovereign-orchestrator | Step Functions State Machine | `arn:aws:states:us-east-2:759729568430:stateMachine:trishula-sovereign-orchestrator` | ✅ LIVE |
| 7 | AWS SageMaker | SageMaker Studio | `us-east-1` (trial — kill: 2026-07-26) | ✅ LIVE |
| 8 | trishula-alerts | SNS Topic | `arn:aws:sns:us-east-2:759729568430:trishula-alerts` | ✅ LIVE |
| 9 | trishula-discord | SQS Queue | `https://sqs.us-east-2.amazonaws.com/759729568430/trishula-discord` | ✅ LIVE |
| 10 | AWS Polly | Polly TTS | `us-east-2` · 8 voices | ✅ LIVE |
| 11 | AWS Forecast | Forecast | `us-east-2` (trial — kill: 2026-08-25) | ✅ LIVE |
| 12 | CloudFront Distribution | CDN | `E2U9ABHVX5BK9I` · `d3osgozw6yxhsl.cloudfront.net` | ✅ LIVE |
| 13 | trishula-api | API Gateway | `4g3s9zys7b` · `4g3s9zys7b.execute-api.us-east-2.amazonaws.com` | ✅ LIVE |
| 14 | ratecheck / hardkill rules | EventBridge | `arn:aws:events:us-east-2:759729568430:rule/ratecheck` | ✅ LIVE |
| 15 | trishula-forecast-hardkill | EventBridge Rule | `arn:aws:events:us-east-2:759729568430:rule/trishula-forecast-hardkill` | ✅ LIVE |
| 16 | trishula-sagemaker-hardkill | EventBridge Rule | `arn:aws:events:us-east-2:759729568430:rule/trishula-sagemaker-hardkill` | ✅ LIVE |
| 17 | AWS Rekognition | Vision AI | `us-east-2` | ✅ LIVE |
| 18 | AWS Comprehend | NLP | `us-east-2` | ⏳ PROPAGATING |
| 19 | AWS Translate | Translate | `us-east-2` | ⏳ PROPAGATING |
| 20 | AWS Transcribe | Speech-to-Text | `us-east-2` | ⏳ PROPAGATING |
| 21 | AWS Textract | Document AI | `us-east-2` | ⏳ PROPAGATING |
| 22 | trishula-signal-bot | Lex V2 Bot | `us-east-1` (region endpoint issue) | ⏳ PROPAGATING |

> **Kill Switch**: `trishula-trial-killshot` Lambda + EventBridge rules auto-terminate all trial services before charges. Forecast kills 2026-08-25, SageMaker kills 2026-07-26.

---

## 🌐 GCP RESOURCES (8 live / 20 total)

| # | Resource | Type | ID | Status |
|---|----------|------|----|--------|
| 23 | trishula-swarm-data | Cloud Storage Bucket | `gs://trishula-swarm-data` · `gcp-swarm-491812` | ✅ LIVE |
| 24 | aegis-scout-intel-cache | Cloud Storage Bucket | `gs://aegis-scout-intel-cache-1774885190` · `gcp-swarm-491812` | ✅ LIVE |
| 25 | trishula-swarm | BigQuery Dataset | `gcp-swarm-491812.trishula-swarm` | ✅ LIVE |
| 26 | trishula-picks | Pub/Sub Topic | `projects/gcp-swarm-491812/topics/trishula-picks` | ✅ LIVE |
| 27 | trishula-task-queue | Cloud Tasks Queue | `projects/gcp-swarm-491812/locations/us-central1/queues/trishula-task-queue` | ✅ LIVE |
| 28 | GCP Monitoring | Cloud Monitoring | `gcp-swarm-491812` | ✅ LIVE |
| 29 | trishula-swarm | Firestore Database | `gcp-swarm-491812` · `nam5` | ✅ LIVE |
| 30 | GCP Translate API | Translation | `gcp-swarm-491812` · validated: 'test'→'prueba' | ✅ LIVE |
| 31 | trishula-swarm-fn | Cloud Run Function | `https://trishula-swarm-fn-60878208706.us-central1.run.app` | ✅ LIVE |
| 32 | QMatrix_Open | Cloud Scheduler | `gcp-swarm-491812/us-central1` · 09:30 ET | ✅ LIVE |
| 33 | QMatrix_Midday | Cloud Scheduler | `gcp-swarm-491812/us-central1` · 12:00 ET | ✅ LIVE |
| 34 | QMatrix_PowerHour | Cloud Scheduler | `gcp-swarm-491812/us-central1` · 15:00 ET | ✅ LIVE |
| 35 | Gemini 2.5 Pro | Vertex AI / AI Studio | `gemini-2.5-pro-preview-05-06` · `gcp-swarm-491812` | ✅ LIVE |
| 36 | BigQuery Analytics Dataset | BigQuery | `gcp-swarm-491812` (2nd dataset) | ✅ LIVE |
| 37 | GCP Pub/Sub Sub | Pub/Sub Subscription | `trishula-picks-sub` | 🔧 UNPROVISIONED |
| 38 | Cloud Run Services | Cloud Run | `us-central1` | 🔧 UNPROVISIONED |
| 39 | Vertex AI Workbench | Vertex AI | `gcp-swarm-491812` | 🔧 UNPROVISIONED |
| 40 | Artifact Registry | Artifact Registry | `us-central1` | 🔧 UNPROVISIONED |
| 41 | Cloud Build | CI/CD | `gcp-swarm-491812` | 🔧 UNPROVISIONED |
| 42 | Secret Manager | Secret Manager | `gcp-swarm-491812` | 🔧 UNPROVISIONED |

---

## 🟦 AZURE RESOURCES (4 live / 16 total)

| # | Resource | Type | ID | Status |
|---|----------|------|----|--------|
| 43 | trishula-staticweb | Static Web App | Azure Static Web Apps (free tier) | ✅ LIVE |
| 44 | trishula-functions | Function App | `https://trishula-functions-hydec7akeha8g7dm.centralus-01.azurewebsites.net` | ✅ LIVE |
| 45 | trishulakeyvaultazure | Key Vault | `https://trishulakeyvaultazure.vault.azure.net/` | ✅ LIVE |
| 46 | trishula-containers | Container App | `westus` | ✅ LIVE |
| 47 | trishula-cosmos | Cosmos DB | (AZURE_COSMOS_KEY pending wire) | ⏳ PROPAGATING |
| 48 | Azure Computer Vision | Cognitive Services | `eastus` | 🔧 UNPROVISIONED |
| 49 | Azure Language Service | Cognitive Services | `eastus` | 🔧 UNPROVISIONED |
| 50 | Azure Speech Service | Cognitive Services | `eastus` | 🔧 UNPROVISIONED |
| 51 | Azure Form Recognizer | Cognitive Services | `eastus` | 🔧 UNPROVISIONED |
| 52 | Azure Translator | Cognitive Services | `eastus` | 🔧 UNPROVISIONED |
| 53 | Azure OpenAI | Cognitive Services | `eastus` | 🔧 UNPROVISIONED |
| 54 | Azure Anomaly Detector | Cognitive Services | `eastus` | 🔧 UNPROVISIONED |
| 55 | Azure Content Moderator | Cognitive Services | `eastus` | 🔧 UNPROVISIONED |
| 56 | Azure Face API | Cognitive Services | `eastus` | 🔧 UNPROVISIONED |
| 57 | Azure App Service F1 | App Service | `centralus` | 🔧 UNPROVISIONED |
| 58 | Azure SignalR | SignalR Service | `centralus` | 🔧 UNPROVISIONED |

---

## 🔴 OCI RESOURCES (11 live / 19 total)

| # | Resource | Type | OCID | Status |
|---|----------|------|------|--------|
| 59 | Trishula-DB1 | Autonomous Database | (wallet: `oracle_wallet/`) · `us-ashburn-1` | ✅ LIVE |
| 60 | Trishula-DB2 | Autonomous Database | (wallet: `oracle_wallet2/`) · `us-ashburn-1` | ✅ LIVE |
| 61 | trishula-swarm-bucket | Object Storage | `us-ashburn-1` | ✅ LIVE |
| 62 | Trishula-Vault | Vault HSM | `ocid1.vault.oc1.iad.ejvbkgriaaf4s.abuwcljt4mr4z7atnv7q5l6uatdr3vkkb5dralsnq3cbekzdykl4ccfnlzyq` | ✅ LIVE |
| 63 | Vault Master Key | KMS Key | `ocid1.key.oc1.iad.ejvbkgriaaf4s.abuwcljtzbn4jorjhhaaeyof5lcn5tabh4if6lv4cglef2uqdwmlrblsnddq` | ✅ LIVE |
| 64 | trishula-fn-app | OCI Functions App | `ocid1.fnapp.oc1.iad.amaaaaaaao2vejyazopflfuvjsnnewz34gfubror4yq3dy7x2ogyovojsmoq` | ✅ LIVE |
| 65 | swarm_events | OCI NoSQL Table | `ocid1.nosqltable.oc1.iad.amaaaaaaao2vejyaqs2qu5py6hcpv23t7y6oilvff3rc2hmnkyjfwrlfivwa` | ✅ LIVE |
| 66 | trishula-events-stream | OCI Streaming | `ocid1.stream.oc1.iad.amaaaaaaao2vejyaoccat2dpomsm2t2svjonzr75t43gnboymgh2eeoyqkjq` | ✅ LIVE |
| 67 | trishula-lb | Load Balancer | `ocid1.loadbalancer.oc1.iad.aaaaaaaaywvdevfpsclrdwewnrgsnodiae2ibeddls6b24gwm7n5e4lfzfpq` | ✅ LIVE |
| 68 | trishula-log-group | Log Group | `ocid1.loggroup.oc1.iad.amaaaaaaao2vejyatxqvsxrybk2kq6p5oiwjppapoaq4xtn77wn2hmghnehq` | ✅ LIVE |
| 69 | trishula-api-gw | API Gateway | `ocid1.apigateway.oc1.iad.amaaaaaaao2vejyakkg7zpmdhsse2tt7ydsvsnwldsxm5z3ksb5hc3zqv3vq` | ✅ LIVE |
| 70 | trishula-signal-queue | OCI Queue | `ocid1.queue.oc1.iad.amaaaaaaao2vejyacnc4np4ek2lvan54im6hxqwsj6bg6nxvuggwplz3rzwa` | ✅ LIVE |
| 71 | OCI Notifications Topic | ONS Topic | `ocid1.onstopic.oc1.iad.amaaaaaaao2vejyah6kswind7ajmsjkbugqcs32ytptbxgrxzr3nkzrnolca` | ✅ LIVE |
| 72 | OCI Vision AI | Vision AI | `us-ashburn-1` | 🔧 UNPROVISIONED |
| 73 | OCI Data Science | Data Science | `us-ashburn-1` | 🔧 UNPROVISIONED |
| 74 | OCI Bastion | Bastion Service | `us-ashburn-1` | 🔧 UNPROVISIONED |
| 75 | OCI WAF | Web App Firewall | `us-ashburn-1` | 🔧 UNPROVISIONED |
| 76 | OCI DNS | DNS Zone | `us-ashburn-1` | 🔧 UNPROVISIONED |

---

## 📊 SUMMARY MATRIX

| Cloud | Live | Propagating | Unprovisioned | Total |
|-------|------|-------------|----------------|-------|
| AWS | 12 | 5 | 5 | 22 |
| GCP | 9 | 0 | 6 | 15 |  
| Azure | 4 | 1 | 11 | 16 |
| OCI | 12 | 0 | 5 | 17 |
| **TOTAL** | **35** | **6** | **27** | **76** |

> **Note**: Live count of 35 reflects 2026-05-28 health snapshot. AWS NLP services (Comprehend, Translate, Transcribe, Textract) are propagating and expected to resolve within 24–72 hours per AWS docs.

---

## 🔑 KILL-SWITCH REGISTRY

| Service | Kill Lambda | EventBridge Rule | Kill Date |
|---------|-------------|-----------------|-----------|
| AWS Forecast | `trishula-trial-killshot` | `trishula-forecast-hardkill` | 2026-08-25 ✅ |
| AWS SageMaker | `trishula-trial-killshot` | `trishula-sagemaker-hardkill` | 2026-07-26 ✅ |

---

*SWARM_MANIFEST.md · Trishula Sovereign Swarm v4.0 · 2026-05-28*
*AWS Account: 759729568430 · GCP Project: gcp-swarm-491812 · OCI Region: us-ashburn-1 · Azure: centralus*
