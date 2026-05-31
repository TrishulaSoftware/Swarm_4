"""
Trishula Wave 1 Sender â€” fires social_outreach_queue.json
Appends live Stripe links and Google Sites URL to each email body.
Logs every send to receipts.

Usage: python send_wave1.py [--dry-run]
"""
import os, sys, json, smtplib, time, hashlib
sys.stdout.reconfigure(encoding="utf-8")
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from pathlib import Path

# â”€â”€ CONFIG â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
QUEUE_PATH    = Path(r"H:\Trishula\Swarm_4_Integration\social_outreach_queue.json")
ENV_PATH      = Path(r"H:\Trishula\Swarm_4_Integration\.env")
RECEIPT_DIR   = Path(r"H:\Trishula\Swarm_4_Integration\Salvo_Staging\Sovereign-PaaS\receipts")
LOG_PATH      = Path(r"H:\Trishula\Swarm_4_Integration\Salvo_Staging\wave1_send_log.json")

# Live Stripe payment links (replace with real links after Stripe setup)
STRIPE_AUDIT_LINK      = os.environ.get("STRIPE_AUDIT_LINK",      "https://trishulasoftware.com/audit")
STRIPE_TEAM_LINK       = os.environ.get("STRIPE_TEAM_LINK",       "https://trishulasoftware.com/team")
GOOGLE_SITES_URL       = os.environ.get("TRISHULA_SITE_URL",      "https://sites.google.com/view/trishulasoftware")
GITHUB_ORG             = "https://github.com/TrishulaSoftware"

DRY_RUN = "--dry-run" in sys.argv
DELAY   = 2  # seconds between sends â€” rate limit protection

# â”€â”€ LOAD ENV â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def load_env(path):
    env = {}
    if not path.exists():
        print(f"[WARN] No .env found at {path}")
        return env
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env

# â”€â”€ APPEND COMMERCIAL FOOTER â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def enrich_body(body, to):
    footer = f"""

---
TRISHULA SOFTWARE â€” Sovereign Security for the AI Age

  Audit Engagement ($25K, 5 days): {STRIPE_AUDIT_LINK}
  Team License ($99/month):        {STRIPE_TEAM_LINK}
  Product Arsenal (683 tests):     {GOOGLE_SITES_URL}
  GitHub Organization:             {GITHUB_ORG}

17 production tools. 683/683 deterministic tests. Zero dependencies.
All CI pipelines publicly verifiable at github.com/TrishulaSoftware.
"""
    return body + footer

# â”€â”€ SEND â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def send_email(smtp, from_addr, entry, env):
    to = entry.get("to", "")
    subject = entry.get("subject", "Trishula Security Audit")
    body = enrich_body(entry.get("body", ""), to)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = from_addr
    msg["To"]      = to
    msg.attach(MIMEText(body, "plain", "utf-8"))

    if DRY_RUN:
        print(f"  [DRY-RUN] Would send to: {to}")
        return True

    try:
        smtp.sendmail(from_addr, [to], msg.as_string())
        return True
    except Exception as e:
        print(f"  [ERROR] {to}: {e}")
        return False

# â”€â”€ MAIN â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def main():
    print(f"{'='*60}")
    print(f"  TRISHULA WAVE 1 SENDER")
    print(f"  Mode: {'DRY-RUN' if DRY_RUN else 'LIVE'}")
    print(f"{'='*60}\n")

    env = load_env(ENV_PATH)
    smtp_host = env.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(env.get("SMTP_PORT", "587"))
    smtp_user = env.get("SMTP_USER", env.get("SMTP_EMAIL", ""))
    smtp_pass = env.get("SMTP_PASS", env.get("SMTP_PASSWORD", ""))
    from_addr = env.get("FROM_EMAIL", smtp_user)

    if not smtp_user or not smtp_pass:
        print("[ERROR] SMTP credentials not found in .env")
        print("  Required: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS")
        sys.exit(1)

    queue = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    print(f"  Queue: {len(queue)} entries loaded")
    print(f"  From:  {from_addr}")
    print()

    sent = []; failed = []

    if not DRY_RUN:
        smtp = smtplib.SMTP(smtp_host, smtp_port)
        smtp.ehlo(); smtp.starttls(); smtp.login(smtp_user, smtp_pass)
        print(f"  [OK] SMTP connected to {smtp_host}:{smtp_port}\n")
    else:
        smtp = None

    for i, entry in enumerate(queue, 1):
        to = entry.get("to", "")
        print(f"  [{i:02d}/{len(queue)}] Sending -> {to}")
        ok = send_email(smtp, from_addr, entry, env)
        if ok:
            sent.append({"to": to, "subject": entry.get("subject", ""), "ts": datetime.now(timezone.utc).isoformat()})
            print(f"         âœ“ SENT")
        else:
            failed.append(to)
        time.sleep(DELAY)

    if not DRY_RUN and smtp:
        smtp.quit()

    # Write log
    log = {"sent": len(sent), "failed": len(failed), "entries": sent, "timestamp": datetime.now(timezone.utc).isoformat()}
    LOG_PATH.write_text(json.dumps(log, indent=2), encoding="utf-8")

    # Receipt
    payload = json.dumps(sent, sort_keys=True)
    receipt = {
        "id": f"wave1_send_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}",
        "type": "OUTREACH_WAVE",
        "wave": 1,
        "sent": len(sent),
        "failed": len(failed),
        "mode": "DRY_RUN" if DRY_RUN else "LIVE",
        "attestation": hashlib.sha256(payload.encode()).hexdigest()
    }
    receipt_path = RECEIPT_DIR / f"wave1_send_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}.json"
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")

    print(f"\n{'='*60}")
    print(f"  WAVE 1 COMPLETE: {len(sent)} sent / {len(failed)} failed")
    print(f"  Attestation: {receipt['attestation'][:32]}...")
    print(f"  Log: {LOG_PATH}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
