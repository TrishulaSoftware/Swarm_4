# █ TRISHULA SOFTWARE — CLOUD SECURITY HARDENING GUIDE
**CONFIDENTIAL & AUDITED**

This document details the exact, step-by-step manual console procedures executed to secure the hybrid multi-cloud infrastructure supporting the TradingView webhook pipeline, the Q-Matrix options scanner, and the distributed Swarm ledger.

---

## █ 1. ORACLE CLOUD INFRASTRUCTURE (OCI): DATABASE NETWORK ACL LOCKDOWN

To prevent unauthorized access to `DB-1` (TrishulaPicks) and `DB-2` (TrishulaLedger), we restrict network ingress to whitelisted IP addresses.

### Step-by-Step Console Guide:
1. Log in to the **Oracle Cloud Console**.
2. Navigate to **Oracle Database** -> **Autonomous Database**.
3. Select the target database instance (`DB-1` or `DB-2`).
4. On the database details page, scroll down to the **Network** section.
5. Next to **Access Control List (ACL)**, click **Edit**.
6. Set the **ACL Status** to **Enabled**.
7. Configure the following **Access Control Rules**:
   - **Rule 1**: Set Type to `IP Address` and enter the local public IP of the **War Machine host**.
   - **Rule 2**: Set Type to `IP Address` and enter the public IP of the **OCI Compute instance** (staged node).
   - **Rule 3**: Set Type to `IP Address` / `CIDR Block` and enter the GCP Cloud Run outbound IP ranges for `us-central1` (or the static NAT IP if VPC Connector is deployed).
     > [!TIP]
     > To find GCP's public IP ranges, check Google's published IP blocks (`_cloud-netblocks.googleusercontent.com`) or look up the specific IP range dynamically via GCP CLI/logs.
8. Click **Save Changes**. The database status will transition to `Updating`. Once complete, only whitelisted IPs can connect via SQL*Net or ORDS.

---

## █ 2. GOOGLE CLOUD PLATFORM (GCP): LEAST-PRIVILEGE IAM SCOPING

To isolate the `trishula-gcp-key.json` credentials used by the local Starfall subscriber daemon on War Machine, we strip all global permissions and restrict the account exclusively to the target subscription.

### Step-by-Step Console Guide:
1. Log in to the **GCP Console** (`console.cloud.google.com`).
2. Navigate to **IAM & Admin** -> **IAM**.
3. Locate the service account principal (e.g., `trishula-alerts-subscriber@gcp-swarm-491812.iam.gserviceaccount.com`).
4. Click the **Edit Principal** (Pencil) icon.
5. Delete any global roles (such as `Owner`, `Editor`, `Pub/Sub Admin`, or `Storage Admin`) by clicking the trash icon next to them.
6. Click **Save**.
7. Navigate to **Pub/Sub** -> **Subscriptions**.
8. Click on the subscription named **`trishula-alerts-sub`**.
9. In the **Permissions** panel on the right side of the screen, click **Add Principal**.
10. Enter the email address of the service account.
11. Under **Select a role**, select **Pub/Sub** -> **Pub/Sub Subscriber** (`roles/pubsub.subscriber`).
12. Click **Save**.
    *The local key `trishula-gcp-key.json` can now ONLY pull messages from `trishula-alerts-sub` and has zero permission to write, delete, or list other resources.*

---

## █ 3. AMAZON WEB SERVICES (AWS): least-privilege IAM policies

To isolate the execution roles of options scanner scripts or Lambdas, we limit database access to the single target table.

### Step-by-Step Console Guide:
1. Log in to the **AWS Management Console**.
2. Navigate to **IAM** -> **Roles**.
3. Search for and select the role associated with the Q-Matrix execution agent (e.g., `TrishulaScannerRole`).
4. Under the **Permissions** tab, click **Add permissions** -> **Create inline policy**.
5. Select the **JSON** tab and paste the following policy:
   ```json
   {
       "Version": "2012-10-17",
       "Statement": [
           {
               "Sid": "DynamoDBTableAccess",
               "Effect": "Allow",
               "Action": [
                   "dynamodb:PutItem",
                   "dynamodb:GetItem",
                   "dynamodb:UpdateItem",
                   "dynamodb:Query",
                   "dynamodb:Scan"
               ],
               "Resource": "arn:aws:dynamodb:us-east-2:*:table/picks_log"
           },
           {
               "Sid": "SSMParametersAccess",
               "Effect": "Allow",
               "Action": [
                   "ssm:GetParameter",
                   "ssm:GetParameters"
               ],
               "Resource": "arn:aws:ssm:us-east-2:*:parameter/trishula/*"
           }
       ]
   }
   ```
6. Click **Review policy**. Name it `TrishulaLeastPrivilegePolicy`.
7. Click **Create policy**.
8. Ensure all broad permissions (such as `AdministratorAccess` or wildcard `dynamodb:*` on all resources) are deleted from the role.

---

## █ 4. MICROSOFT ENTRA ID (AZURE AD): ZERO-COST IDENTITY GATE

We set up a central identity registry to authenticate daemon connections and manage secure service-to-service communication.

### Step-by-Step Console Guide:
1. Log in to the **Microsoft Entra Admin Center** or **Azure Portal**.
2. Navigate to **Microsoft Entra ID** (formerly Azure Active Directory).
3. Select **App registrations** -> **New registration**.
4. Name the application: **`Trishula-Daemon-Bridge`**.
5. Keep the default options ("Accounts in this organizational directory only") and click **Register**.
6. On the application home screen, copy the **Application (client) ID** and **Directory (tenant) ID** to a secure local location.
7. Go to **Certificates & secrets** -> **Client secrets** -> **New client secret**.
8. Add a description (e.g., `Trishula Local Daemon Link`) and set the expiration (e.g., 180 days).
9. Click **Add**.
10. **CRITICAL**: Copy the value of the secret from the **Value** column immediately. It will be hidden permanently once you refresh the page. Store this secret safely in your local `.env` file.
11. (Optional) Under **API permissions**, configure specific Graph scopes or custom app role assignments to restrict API client interactions.

---

## █ SUMMARY OF PERMANENT AUDIT TRACES

All configuration changes, deployment scripts, and this security guide are tracked and signed in the Trishula Software GitHub repository:
- **Deploy Script**: `scratch/deploy_starfall_gcp.py`
- **Subscriber Daemon**: `Salvo_Staging/starfall_relay.py`
- **Security Audit Guide**: `Salvo_Staging/SECURITY_GUIDE.md`
- **Credential Templates**: `Salvo_Staging/.env.example`
- **GitHub Ignore Definitions**: `Salvo_Staging/.gitignore`
