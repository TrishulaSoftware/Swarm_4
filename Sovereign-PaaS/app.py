"""
Sovereign Webhook Gateway (v2.0 - Hardened)
Secure CI/CD receiver for Trishula Infrastructure.

Security properties:
 - HMAC-SHA256 verification with constant-time comparison
 - Strict repository allowlist (no user-controlled path construction)
 - Safe environment variable fetching (no KeyError crash vector)
 - GitHub signature prefix stripping (sha256=...)
"""

import os
import hmac
import hashlib
import logging
import subprocess
from flask import Flask, request, abort, jsonify

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# SECURITY: Hard-coded allowlist. Only these repos can trigger local scripts.
# Keys are exact GitHub repository names. Values are absolute local script paths.
ALLOWED_REPOS: dict[str, str] = {
    "Sovereign-PaaS": r"C:\Trishula-Sovereign\scripts\deploy_paas.ps1",
    "Swarm-Alpha":    r"C:\Trishula-Sovereign\scripts\update_swarm.ps1",
}


def verify_signature(payload: bytes, signature_header: str) -> bool:
    """
    Validates the GitHub HMAC-SHA256 webhook signature.

    GitHub sends the header as: 'sha256=<hex_digest>'
    We strip the prefix before constant-time comparison.
    """
    secret = os.getenv("TRISHULA_HMAC_SECRET")
    if not secret:
        logger.critical("TRISHULA_HMAC_SECRET is not set. Refusing all traffic.")
        return False

    # Strip the 'sha256=' prefix sent by GitHub
    if not signature_header.startswith("sha256="):
        logger.warning("Malformed signature header received.")
        return False
    incoming_digest = signature_header[len("sha256="):]

    expected_digest = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256
    ).hexdigest()

    # Constant-time comparison prevents timing side-channel attacks
    return hmac.compare_digest(expected_digest, incoming_digest)


@app.route("/webhook", methods=["POST"])
def webhook():
    signature_header = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(request.data, signature_header):
        logger.warning("Rejected request: invalid or missing HMAC signature.")
        abort(403)

    data = request.get_json(silent=True)
    if not data:
        abort(400)

    repo_name = data.get("repository", {}).get("name", "")
    script_path = ALLOWED_REPOS.get(repo_name)

    if not script_path:
        logger.info(f"Repo '{repo_name}' is not in the allowlist. Ignoring.")
        # Return 200 so GitHub doesn't retry — this event is intentionally unhandled
        return jsonify({"status": "ignored", "reason": "repo not in allowlist"}), 200

    if not os.path.isfile(script_path):
        logger.error(f"Authorized script not found on disk: {script_path}")
        abort(500)

    logger.info(f"Authorized deploy triggered for repo '{repo_name}': {script_path}")
    try:
        proc = subprocess.Popen(
            ["powershell.exe", "-NonInteractive", "-File", script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        logger.info(f"Script launched with PID {proc.pid}")
    except OSError as e:
        logger.error(f"Failed to launch deployment script: {e}")
        return jsonify({"status": "error", "message": "Script execution failed"}), 500

    return jsonify({"status": "accepted", "repo": repo_name, "pid": proc.pid}), 202


if __name__ == "__main__":
    port = int(os.getenv("SOVEREIGN_PORT", 5000))
    logger.info(f"Sovereign Gateway online — listening on port {port}")
    # debug=False is critical in production; never expose debug mode externally
    app.run(host="127.0.0.1", port=port, debug=False)