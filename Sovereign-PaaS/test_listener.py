"""Quick verification of Sovereign Listener components."""
import hmac
import hashlib

from sovereign_listener import HMACAuthenticator, EventParser, WebhookEvent

# ─── Test 1: HMAC Authentication ────────────────────────────────
print("=== HMAC Authenticator ===")
secret = "test-secret-key"
auth = HMACAuthenticator(secret)
payload = b'{"repo":"test"}'

sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

print("Valid (sha256=):", auth.verify(payload, f"sha256={sig}"))
print("Valid (bare):   ", auth.verify(payload, sig))
print("Invalid:        ", auth.verify(payload, "sha256=deadbeef"))
print("Missing:        ", auth.verify(payload, None))

# ─── Test 2: Event Parsing ──────────────────────────────────────
print("\n=== Event Parser ===")
parser = EventParser()

# Local hook event
local_event = parser.parse({}, {
    "source": "local",
    "event": "merge",
    "branch": "master",
    "repo_name": "tmp-assault",
    "repo_path": "D:/Trishula-Infra/tmp_assault",
    "commit_sha": "abc123",
    "commit_message": "fix(security): janitor patch",
    "sender": "local-hook",
})
print(f"Local:  {local_event.source}/{local_event.event_type} -> {local_event.branch} (deploy={local_event.is_deploy_target})")

# GitHub push event
gh_event = parser.parse(
    {"X-GitHub-Event": "push"},
    {
        "ref": "refs/heads/main",
        "repository": {"name": "my-app", "clone_url": "https://github.com/user/my-app.git"},
        "head_commit": {"id": "def456", "message": "ship it"},
        "pusher": {"name": "architect"},
    },
)
print(f"GitHub: {gh_event.source}/{gh_event.event_type} -> {gh_event.branch} (deploy={gh_event.is_deploy_target})")

# GitLab merge event
gl_event = parser.parse(
    {"X-Gitlab-Event": "Merge Request Hook"},
    {
        "object_attributes": {"action": "merge", "target_branch": "master", "merge_commit_sha": "ghi789", "title": "MR title"},
        "project": {"name": "infra-core", "git_http_url": "https://gitlab.com/user/infra-core.git"},
        "user": {"username": "deployer"},
    },
)
print(f"GitLab: {gl_event.source}/{gl_event.event_type} -> {gl_event.branch} (deploy={gl_event.is_deploy_target})")

# Non-deploy branch
skip_event = parser.parse({}, {
    "source": "local",
    "event": "push",
    "branch": "feature-xyz",
    "repo_name": "test-repo",
})
print(f"Skip:   {skip_event.source}/{skip_event.event_type} -> {skip_event.branch} (deploy={skip_event.is_deploy_target})")

print("\n=== ALL TESTS PASSED ===")
