"""
SOVEREIGN LISTENER — Webhook Deployment Daemon
Part of the Trishula Sovereign PaaS (Gap 1 — Phase 2)

A lightweight webhook receiver that listens for Git merge/push events and
autonomously triggers a zero-downtime deployment pipeline.

Architecture:
    ┌──────────────┐    POST /deploy     ┌──────────────────┐
    │  Git Hook /  │ ──────────────────▶ │  Sovereign       │
    │  GitHub /    │   HMAC-signed JSON  │  Listener :8080  │
    │  GitLab      │                     │                  │
    └──────────────┘                     │  ┌────────────┐  │
                                         │  │ HMAC Auth  │  │
                                         │  └─────┬──────┘  │
                                         │        ▼         │
                                         │  ┌────────────┐  │
                                         │  │ Event      │  │
                                         │  │ Router     │  │
                                         │  └─────┬──────┘  │
                                         │        ▼         │
                                         │  ┌────────────┐  │
                                         │  │ Deploy     │  │
                                         │  │ Pipeline   │  │
                                         │  └────────────┘  │
                                         └──────────────────┘
Usage:
    # Start the listener daemon
    python sovereign_listener.py

    # Custom port and secret
    python sovereign_listener.py --port 9090 --secret my-webhook-secret

    # With deployment domain template
    python sovereign_listener.py --domain-template "{app}.mydomain.com"

    # Verbose logging
    python sovereign_listener.py --log-level DEBUG

Security:
    - HMAC-SHA256 signature verification on every payload
    - Rejects unsigned or tampered requests
    - Rate limiting per source IP
    - Request size cap (10MB)
"""

import argparse
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sys
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional

# ─── Ensure sibling modules are importable ───────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from deploy_core import DeployConfig, SovereignDeployer, sanitize_app_name

# ─── Configuration ───────────────────────────────────────────────────────────

LOG_FORMAT = "%(asctime)s │ %(levelname)-8s │ %(name)-24s │ %(message)s"
LOG_DATE_FORMAT = "%H:%M:%S"

DEFAULT_PORT = 8080
MAX_PAYLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 30     # max requests per window per IP

# Protected branches that trigger deployments
DEPLOY_BRANCHES = {"main", "master"}


# ─── Data Models ─────────────────────────────────────────────────────────────

@dataclass
class WebhookEvent:
    """Parsed webhook event."""
    event_type: str              # push, merge, pull_request
    source: str                  # github, gitlab, local, generic
    branch: str                  # target branch
    repo_name: str               # repository name
    repo_path: Optional[str]     # local path (for local hooks)
    repo_url: Optional[str]      # remote URL (for github/gitlab)
    commit_sha: Optional[str]    # head commit
    commit_message: Optional[str]
    sender: Optional[str]        # who triggered it
    raw: dict = field(default_factory=dict)

    @property
    def is_deploy_target(self) -> bool:
        """Check if this event should trigger a deployment."""
        return self.branch in DEPLOY_BRANCHES


@dataclass
class DeploymentRecord:
    """Record of a deployment triggered by a webhook."""
    event: WebhookEvent
    started_at: str
    completed_at: Optional[str] = None
    success: bool = False
    duration_ms: int = 0
    container_id: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None
    septip_verified: bool = False


# ─── Rate Limiter ────────────────────────────────────────────────────────────

class RateLimiter:
    """Simple sliding-window rate limiter per IP."""

    def __init__(self, window: int = RATE_LIMIT_WINDOW, max_requests: int = RATE_LIMIT_MAX):
        self.window = window
        self.max_requests = max_requests
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, ip: str) -> bool:
        now = time.time()
        with self._lock:
            # Prune old entries
            self._requests[ip] = [
                t for t in self._requests[ip] if now - t < self.window
            ]
            if len(self._requests[ip]) >= self.max_requests:
                return False
            self._requests[ip].append(now)
            return True


# ─── SEPTIP Overwatch Auditor (The Gate) ───────────────────────────────────

class SEPTIPAuditor:
    """
    Enforces Operation Iron Gate compliance.
    Audits deployment pulses against L0, SEPTIP, and SQA_v5_ascended laws.
    """

    def __init__(self):
        self.logger = logging.getLogger("Sovereign.Overwatch")
        self.latency_ceiling = 0.1200 # 120ms floor

    def audit(self, record: DeploymentRecord) -> bool:
        """
        Perform the sub-second L0/SEPTIP audit.
        """
        start_time = time.monotonic()
        event = record.event

        self.logger.info("[AUDIT] Initializing SEPTIP Overwatch check for '%s'...", event.repo_name)

        # 1. Chronological Anchor Verification (L0 Addendum)
        # We check the 'started_at' timestamp generated for the record
        ts = record.started_at
        if not ts or "T" not in ts or "Z" not in ts:
            self.logger.error("[VETO] Missing or malformed ISO-8601 Chronological Anchor.")
            return False

        # 2. Binding Isolation Check (SEPTIP-v2)
        # Scan raw payload for unauthorized 0.0.0.0 bindings
        raw_str = str(event.raw)
        if "0.0.0.0" in raw_str:
            self.logger.error("[VETO] Unauthorized 0.0.0.0 binding detected in payload (Iron Junk).")
            return False

        # 3. Latency Audit (L0 Law)
        audit_latency = time.monotonic() - start_time
        if audit_latency > self.latency_ceiling:
             self.logger.error(f"[VETO] Audit latency {audit_latency:.4f}s exceeds floor.")
             return False

        self.logger.info("[AUDIT] Pulses ratified. Relational Truth Verified. (%.4fs)", audit_latency)
        record.septip_verified = True
        return True


# ─── HMAC Authenticator ─────────────────────────────────────────────────────

class HMACAuthenticator:
    """Verifies HMAC-SHA256 webhook signatures."""

    def __init__(self, secret: str):
        self.secret = secret.encode("utf-8")
        self.logger = logging.getLogger("Sovereign.Auth")

    def verify(self, payload: bytes, signature_header: Optional[str]) -> bool:
        """Verify the HMAC signature of a webhook payload.

        Supports formats:
            - sha256=<hex>   (GitHub style)
            - <hex>          (bare signature)

        Args:
            payload: Raw request body
            signature_header: Value of the signature header

        Returns:
            True if signature is valid
        """
        if not signature_header:
            self.logger.warning("No signature provided")
            return False

        # Extract the hex digest
        if signature_header.startswith("sha256="):
            received_sig = signature_header[7:]
        else:
            received_sig = signature_header

        # Compute expected signature
        expected_sig = hmac.new(
            self.secret, payload, hashlib.sha256
        ).hexdigest()

        # Constant-time comparison
        if hmac.compare_digest(expected_sig, received_sig):
            self.logger.debug("Signature verified ✓")
            return True
        else:
            self.logger.warning("Signature mismatch — REJECTED")
            return False


# ─── Event Parser ────────────────────────────────────────────────────────────

class EventParser:
    """Parses webhook payloads from different Git providers."""

    def __init__(self):
        self.logger = logging.getLogger("Sovereign.Parser")

    def parse(self, headers: dict, body: dict) -> Optional[WebhookEvent]:
        """Route to the correct parser based on headers."""

        # Detect source from headers
        if "X-GitHub-Event" in headers:
            return self._parse_github(headers, body)
        elif "X-Gitlab-Event" in headers:
            return self._parse_gitlab(headers, body)
        elif body.get("source") == "local":
            return self._parse_local(body)
        else:
            return self._parse_generic(body)

    def _parse_github(self, headers: dict, body: dict) -> Optional[WebhookEvent]:
        """Parse a GitHub webhook payload."""
        event_type = headers.get("X-GitHub-Event", "unknown")

        if event_type == "push":
            ref = body.get("ref", "")
            branch = ref.replace("refs/heads/", "")
            repo = body.get("repository", {})
            head_commit = body.get("head_commit", {})

            return WebhookEvent(
                event_type="push",
                source="github",
                branch=branch,
                repo_name=repo.get("name", "unknown"),
                repo_path=None,
                repo_url=repo.get("clone_url"),
                commit_sha=head_commit.get("id"),
                commit_message=head_commit.get("message"),
                sender=body.get("pusher", {}).get("name"),
                raw=body,
            )

        elif event_type == "pull_request":
            action = body.get("action", "")
            pr = body.get("pull_request", {})

            if action == "closed" and pr.get("merged"):
                repo = body.get("repository", {})
                return WebhookEvent(
                    event_type="merge",
                    source="github",
                    branch=pr.get("base", {}).get("ref", "unknown"),
                    repo_name=repo.get("name", "unknown"),
                    repo_path=None,
                    repo_url=repo.get("clone_url"),
                    commit_sha=pr.get("merge_commit_sha"),
                    commit_message=pr.get("title"),
                    sender=pr.get("merged_by", {}).get("login"),
                    raw=body,
                )

        self.logger.debug("Ignoring GitHub event: %s", event_type)
        return None

    def _parse_gitlab(self, headers: dict, body: dict) -> Optional[WebhookEvent]:
        """Parse a GitLab webhook payload."""
        event_type = headers.get("X-Gitlab-Event", "")

        if "Push" in event_type:
            ref = body.get("ref", "")
            branch = ref.replace("refs/heads/", "")
            project = body.get("project", {})
            commits = body.get("commits", [])
            last_commit = commits[-1] if commits else {}

            return WebhookEvent(
                event_type="push",
                source="gitlab",
                branch=branch,
                repo_name=project.get("name", "unknown"),
                repo_path=None,
                repo_url=project.get("git_http_url"),
                commit_sha=body.get("after"),
                commit_message=last_commit.get("message"),
                sender=body.get("user_name"),
                raw=body,
            )

        elif "Merge Request" in event_type:
            attrs = body.get("object_attributes", {})
            if attrs.get("action") == "merge":
                project = body.get("project", {})
                return WebhookEvent(
                    event_type="merge",
                    source="gitlab",
                    branch=attrs.get("target_branch", "unknown"),
                    repo_name=project.get("name", "unknown"),
                    repo_path=None,
                    repo_url=project.get("git_http_url"),
                    commit_sha=attrs.get("merge_commit_sha"),
                    commit_message=attrs.get("title"),
                    sender=body.get("user", {}).get("username"),
                    raw=body,
                )

        self.logger.debug("Ignoring GitLab event: %s", event_type)
        return None

    def _parse_local(self, body: dict) -> Optional[WebhookEvent]:
        """Parse a local git hook payload (from setup_local_hook)."""
        return WebhookEvent(
            event_type=body.get("event", "push"),
            source="local",
            branch=body.get("branch", "unknown"),
            repo_name=body.get("repo_name", "unknown"),
            repo_path=body.get("repo_path"),
            repo_url=None,
            commit_sha=body.get("commit_sha"),
            commit_message=body.get("commit_message"),
            sender=body.get("sender", "local-hook"),
            raw=body,
        )

    def _parse_generic(self, body: dict) -> Optional[WebhookEvent]:
        """Parse a generic/manual webhook payload."""
        return WebhookEvent(
            event_type=body.get("event", "push"),
            source="generic",
            branch=body.get("branch", body.get("ref", "unknown")),
            repo_name=body.get("repo_name", body.get("repository", "unknown")),
            repo_path=body.get("repo_path"),
            repo_url=body.get("repo_url"),
            commit_sha=body.get("commit_sha", body.get("after")),
            commit_message=body.get("commit_message"),
            sender=body.get("sender"),
            raw=body,
        )


# ─── Deployment Executor ────────────────────────────────────────────────────

class DeploymentExecutor:
    """Executes deployments triggered by webhook events."""

    def __init__(self, domain_template: Optional[str] = None):
        self.logger = logging.getLogger("Sovereign.Executor")
        self.deployer = SovereignDeployer()
        self.auditor = SEPTIPAuditor()
        self.domain_template = domain_template  # e.g., "{app}.example.com"
        self._active_deployments: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()
        self.history: list[DeploymentRecord] = []

    def trigger(self, event: WebhookEvent) -> DeploymentRecord:
        """Trigger a deployment from a webhook event.

        Runs the deployment in a background thread for non-blocking
        webhook response. Returns immediately with the record.
        """
        app_name = sanitize_app_name(event.repo_name)
        record = DeploymentRecord(
            event=event,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        self.logger.info(
            "╔══════════════════════════════════════════════════════════════════╗"
        )
        self.logger.info(
            "║  DEPLOYMENT TRIGGERED                                          ║"
        )
        self.logger.info(
            "╠══════════════════════════════════════════════════════════════════╣"
        )
        self.logger.info("║  Source:  %-55s║", event.source)
        self.logger.info("║  Event:   %-55s║", event.event_type)
        self.logger.info("║  Repo:    %-55s║", event.repo_name)
        self.logger.info("║  Branch:  %-55s║", event.branch)
        self.logger.info("║  Commit:  %-55s║", (event.commit_sha or "N/A")[:12])
        self.logger.info("║  Sender:  %-55s║", event.sender or "unknown")
        self.logger.info(
            "╚══════════════════════════════════════════════════════════════════╝"
        )

        # Launch deployment in a background thread
        thread = threading.Thread(
            target=self._execute_deployment,
            args=(event, app_name, record),
            name=f"deploy-{app_name}",
            daemon=True,
        )

        with self._lock:
            # Cancel any in-flight deployment for the same app
            existing = self._active_deployments.get(app_name)
            if existing and existing.is_alive():
                self.logger.warning(
                    "Deployment already in-flight for '%s' — superseding", app_name,
                )

            self._active_deployments[app_name] = thread

        thread.start()
        return record

    def _execute_deployment(
        self,
        event: WebhookEvent,
        app_name: str,
        record: DeploymentRecord,
    ):
        """Execute the full deployment pipeline (runs in background thread)."""
        start_time = time.monotonic()

        try:
            # ── SEPTIP Overwatch Audit (The Ascension Gate) ──
            if not self.auditor.audit(record):
                record.error = "SEPTIP VETO: Compliance Failure (Audit Refused)"
                record.success = False
                self.logger.critical("[GATE] !!! PULSE TERMINATED BY OVERWATCH !!!")
                return

            # Resolve the repository path
            repo_path = self._resolve_repo_path(event)
            if not repo_path:
                record.error = f"Cannot resolve repository path for '{event.repo_name}'"
                record.success = False
                self.logger.error("  ✗ %s", record.error)
                return

            # Build the domain
            domain = None
            if self.domain_template:
                domain = self.domain_template.replace("{app}", app_name)

            # ── Zero-Downtime Strategy ───────────────────────────────
            # 1. Build the new image FIRST (old container still running)
            # 2. Start the new container on a new port
            # 3. Health check the new container
            # 4. Only THEN swap the proxy and tear down the old one
            # The deploy_core handles this — it tears down old AFTER build
            # by checking the manifest for existing deployments.

            config = DeployConfig(
                repo_path=repo_path,
                app_name=app_name,
                domain=domain,
            )

            self.logger.info("[PIPELINE] Starting deployment for '%s'...", app_name)
            result = self.deployer.deploy(config)

            record.success = result.success
            record.container_id = result.container_id
            record.url = result.url
            record.error = result.error
            record.duration_ms = result.duration_ms

            if result.success:
                self.logger.info(
                    "  ✓ DEPLOYED: %s → %s (%dms)",
                    app_name, result.url, result.duration_ms,
                )
            else:
                self.logger.error(
                    "  ✗ FAILED: %s — %s", app_name, result.error,
                )

        except Exception as e:
            record.success = False
            record.error = str(e)
            self.logger.exception("  ✗ Unhandled error during deployment: %s", e)

        finally:
            elapsed = int((time.monotonic() - start_time) * 1000)
            record.completed_at = datetime.now(timezone.utc).isoformat()
            record.duration_ms = record.duration_ms or elapsed
            self.history.append(record)

            with self._lock:
                self._active_deployments.pop(app_name, None)

    def _resolve_repo_path(self, event: WebhookEvent) -> Optional[Path]:
        """Resolve the local filesystem path for a repository."""

        # Local hook: path is provided directly
        if event.repo_path:
            path = Path(event.repo_path).resolve()
            if path.is_dir():
                return path
            self.logger.warning("Provided repo_path is not a directory: %s", path)

        # Remote: check if we have a local clone already
        # Look in common locations
        search_dirs = [
            Path(__file__).parent.parent,        # ../
            Path.home() / "repos",               # ~/repos/
            Path.home() / "projects",             # ~/projects/
            Path("/opt/sovereign/repos"),         # /opt/sovereign/repos/
        ]

        for search_dir in search_dirs:
            candidate = search_dir / event.repo_name
            if candidate.is_dir():
                self.logger.info("Found local repo: %s", candidate)
                return candidate

        # TODO: Auto-clone from repo_url if not found locally
        self.logger.warning(
            "No local clone found for '%s'. "
            "Clone it first or provide repo_path in the payload.",
            event.repo_name,
        )
        return None


# ─── HTTP Request Handler ───────────────────────────────────────────────────

class WebhookHandler(BaseHTTPRequestHandler):
    """HTTP handler for incoming webhook requests."""

    # Class-level references set by the server
    authenticator: HMACAuthenticator = None
    parser: EventParser = None
    executor: DeploymentExecutor = None
    rate_limiter: RateLimiter = None
    require_auth: bool = True

    def log_message(self, fmt, *args):
        """Route HTTP server logs through our logger."""
        logger = logging.getLogger("Sovereign.HTTP")
        logger.debug(fmt, *args)

    def do_GET(self):
        """Health check and status endpoint."""
        if self.path == "/health":
            self._respond(200, {"status": "ok", "service": "sovereign-listener"})
            return

        if self.path == "/status":
            history = [
                {
                    "app": r.event.repo_name,
                    "branch": r.event.branch,
                    "success": r.success,
                    "url": r.url,
                    "duration_ms": r.duration_ms,
                    "started_at": r.started_at,
                }
                for r in (self.executor.history[-20:] if self.executor else [])
            ]
            self._respond(200, {
                "status": "ok",
                "deployments": len(history),
                "recent": history,
            })
            return

        self._respond(404, {"error": "Not found. POST to /deploy"})

    def do_POST(self):
        """Handle incoming webhook POST requests."""
        logger = logging.getLogger("Sovereign.HTTP")

        # ── Rate limiting ────────────────────────────────────────────
        client_ip = self.client_address[0]
        if self.rate_limiter and not self.rate_limiter.is_allowed(client_ip):
            logger.warning("Rate limit exceeded for %s", client_ip)
            self._respond(429, {"error": "Rate limit exceeded"})
            return

        # ── Route check ──────────────────────────────────────────────
        if self.path not in ("/deploy", "/webhook", "/"):
            self._respond(404, {"error": "Not found. POST to /deploy"})
            return

        # ── Read payload ─────────────────────────────────────────────
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > MAX_PAYLOAD_BYTES:
            logger.warning("Payload too large: %d bytes", content_length)
            self._respond(413, {"error": "Payload too large"})
            return

        if content_length == 0:
            self._respond(400, {"error": "Empty payload"})
            return

        raw_body = self.rfile.read(content_length)

        # ── HMAC verification ────────────────────────────────────────
        if self.require_auth and self.authenticator:
            signature = (
                self.headers.get("X-Hub-Signature-256")      # GitHub
                or self.headers.get("X-Gitlab-Token")         # GitLab
                or self.headers.get("X-Sovereign-Signature")  # Local/generic
            )
            if not self.authenticator.verify(raw_body, signature):
                logger.warning("HMAC verification FAILED from %s", client_ip)
                self._respond(403, {"error": "Invalid signature"})
                return

        # ── Parse JSON ───────────────────────────────────────────────
        try:
            body = json.loads(raw_body)
        except json.JSONDecodeError as e:
            logger.warning("Invalid JSON: %s", e)
            self._respond(400, {"error": "Invalid JSON"})
            return

        # ── Parse event ──────────────────────────────────────────────
        headers_dict = {k: v for k, v in self.headers.items()}
        event = self.parser.parse(headers_dict, body)

        if not event:
            logger.info("Event ignored (not actionable)")
            self._respond(200, {"status": "ignored", "reason": "not actionable"})
            return

        logger.info(
            "Received %s event: %s/%s [%s] from %s",
            event.source, event.repo_name, event.branch,
            event.event_type, client_ip,
        )

        # ── Branch check ─────────────────────────────────────────────
        if not event.is_deploy_target:
            logger.info(
                "Branch '%s' is not a deploy target — skipping", event.branch,
            )
            self._respond(200, {
                "status": "skipped",
                "reason": f"Branch '{event.branch}' not in deploy targets",
            })
            return

        # ── Trigger deployment ───────────────────────────────────────
        record = self.executor.trigger(event)

        self._respond(202, {
            "status": "accepted",
            "app": event.repo_name,
            "branch": event.branch,
            "message": "Deployment triggered",
        })

    def _respond(self, status: int, body: dict):
        """Send a JSON response."""
        payload = json.dumps(body, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Powered-By", "Sovereign-PaaS/1.0")
        self.end_headers()
        self.wfile.write(payload)


# ─── The Sovereign Listener Server ──────────────────────────────────────────

class SovereignListener:
    """
    The webhook listener daemon.

    Starts an HTTP server that:
    1. Receives Git webhook payloads
    2. Authenticates via HMAC
    3. Parses events from GitHub, GitLab, or local hooks
    4. Triggers zero-downtime deployments
    """

    def __init__(
        self,
        port: int = DEFAULT_PORT,
        secret: Optional[str] = None,
        domain_template: Optional[str] = None,
        require_auth: bool = True,
    ):
        self.logger = logging.getLogger("Sovereign.Listener")
        self.port = port
        self.require_auth = require_auth

        # Generate a random secret if none provided
        if secret:
            self.secret = secret
        else:
            self.secret = secrets.token_hex(32)
            self.logger.warning(
                "No --secret provided. Generated random secret:\n"
                "  %s\n"
                "  Set this in your webhook configuration or .env file.",
                self.secret,
            )

        # Initialize components
        self.authenticator = HMACAuthenticator(self.secret)
        self.parser = EventParser()
        self.executor = DeploymentExecutor(domain_template=domain_template)
        self.rate_limiter = RateLimiter()

        # Wire up the handler class
        WebhookHandler.authenticator = self.authenticator
        WebhookHandler.parser = self.parser
        WebhookHandler.executor = self.executor
        WebhookHandler.rate_limiter = self.rate_limiter
        WebhookHandler.require_auth = self.require_auth

    def start(self):
        """Start the listener daemon."""
        server = HTTPServer(("0.0.0.0", self.port), WebhookHandler)

        self.logger.info("=" * 70)
        self.logger.info("  SOVEREIGN LISTENER — Webhook Deployment Daemon")
        self.logger.info("  Port:     %d", self.port)
        self.logger.info("  Auth:     %s", "HMAC-SHA256" if self.require_auth else "DISABLED")
        self.logger.info("  Endpoint: http://0.0.0.0:%d/deploy", self.port)
        self.logger.info("  Health:   http://0.0.0.0:%d/health", self.port)
        self.logger.info("  Status:   http://0.0.0.0:%d/status", self.port)
        self.logger.info("=" * 70)
        self.logger.info("Listening for webhook events... (Ctrl+C to stop)")

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            self.logger.info("Shutdown signal received.")
            server.shutdown()
            self.logger.info("Sovereign Listener stopped.")


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Sovereign PaaS — Webhook Deployment Daemon",
    )
    parser.add_argument(
        "--port", type=int, default=int(os.environ.get("SOVEREIGN_PORT", DEFAULT_PORT)),
        help=f"Port to listen on (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--secret", type=str,
        default=os.environ.get("SOVEREIGN_WEBHOOK_SECRET"),
        help="HMAC secret for webhook authentication (or set SOVEREIGN_WEBHOOK_SECRET env var)",
    )
    parser.add_argument(
        "--domain-template", type=str,
        default=os.environ.get("SOVEREIGN_DOMAIN_TEMPLATE"),
        help='Domain template, e.g., "{app}.example.com"',
    )
    parser.add_argument(
        "--no-auth", action="store_true",
        help="Disable HMAC authentication (DEVELOPMENT ONLY)",
    )
    parser.add_argument(
        "--log-level", type=str, default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )

    args = parser.parse_args()

    # ── Logging ──────────────────────────────────────────────────────
    log_level = getattr(logging, args.log_level)
    console = logging.StreamHandler()
    console.setLevel(log_level)
    console.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))

    file_handler = logging.FileHandler(
        Path(__file__).parent / "sovereign_listener.log",
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(console)
    root.addHandler(file_handler)

    if args.no_auth:
        logging.getLogger("Sovereign.Listener").warning(
            "⚠ HMAC authentication DISABLED — development mode only!"
        )

    # ── Start ────────────────────────────────────────────────────────
    listener = SovereignListener(
        port=args.port,
        secret=args.secret,
        domain_template=args.domain_template,
        require_auth=not args.no_auth,
    )
    listener.start()


if __name__ == "__main__":
    main()
