#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# SETUP LOCAL HOOK — The Vault Connector
# Part of the Trishula Sovereign PaaS (Gap 1 — Phase 2)
#
# Installs a Git post-merge hook into a target repository that fires a
# webhook payload to the Sovereign Listener whenever a branch is merged.
#
# This simulates a standard GitHub/GitLab webhook for local development,
# closing the loop:  git merge → webhook → deploy pipeline
#
# Usage:
#   chmod +x setup_local_hook.sh
#   ./setup_local_hook.sh /path/to/your/repo
#   ./setup_local_hook.sh /path/to/your/repo --secret my-webhook-secret
#   ./setup_local_hook.sh /path/to/your/repo --port 9090
#   ./setup_local_hook.sh /path/to/your/repo --remove   # Uninstall
#
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ─── Configuration ─────────────────────────────────────────────────────────

LISTENER_HOST="${SOVEREIGN_HOST:-localhost}"
LISTENER_PORT="${SOVEREIGN_PORT:-8080}"
WEBHOOK_SECRET="${SOVEREIGN_WEBHOOK_SECRET:-}"
ENDPOINT="/deploy"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ─── Argument Parsing ─────────────────────────────────────────────────────

REPO_PATH=""
REMOVE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --secret)
            WEBHOOK_SECRET="$2"
            shift 2
            ;;
        --port)
            LISTENER_PORT="$2"
            shift 2
            ;;
        --host)
            LISTENER_HOST="$2"
            shift 2
            ;;
        --remove|--uninstall)
            REMOVE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 <repo-path> [options]"
            echo ""
            echo "Options:"
            echo "  --secret <secret>   HMAC webhook secret"
            echo "  --port <port>       Listener port (default: 8080)"
            echo "  --host <host>       Listener host (default: localhost)"
            echo "  --remove            Remove the hook"
            echo "  --help              Show this help"
            exit 0
            ;;
        *)
            if [[ -z "$REPO_PATH" ]]; then
                REPO_PATH="$1"
            else
                echo -e "${RED}ERROR: Unknown argument: $1${NC}"
                exit 1
            fi
            shift
            ;;
    esac
done

# ─── Validation ────────────────────────────────────────────────────────────

if [[ -z "$REPO_PATH" ]]; then
    echo -e "${RED}ERROR: Repository path required.${NC}"
    echo "Usage: $0 <repo-path> [--secret <secret>] [--port <port>]"
    exit 1
fi

# Resolve to absolute path
REPO_PATH="$(cd "$REPO_PATH" 2>/dev/null && pwd)" || {
    echo -e "${RED}ERROR: Directory not found: $REPO_PATH${NC}"
    exit 1
}

# Verify it's a git repository
if [[ ! -d "$REPO_PATH/.git" ]]; then
    echo -e "${RED}ERROR: Not a git repository: $REPO_PATH${NC}"
    exit 1
fi

HOOK_PATH="$REPO_PATH/.git/hooks/post-merge"

# ─── Remove Mode ──────────────────────────────────────────────────────────

if $REMOVE; then
    if [[ -f "$HOOK_PATH" ]] && grep -q "SOVEREIGN-PAAS-HOOK" "$HOOK_PATH"; then
        rm -f "$HOOK_PATH"
        echo -e "${GREEN}✓ Sovereign PaaS hook removed from: $REPO_PATH${NC}"
    else
        echo -e "${YELLOW}No Sovereign PaaS hook found in: $REPO_PATH${NC}"
    fi
    exit 0
fi

# ─── Generate the Hook Script ─────────────────────────────────────────────

WEBHOOK_URL="http://${LISTENER_HOST}:${LISTENER_PORT}${ENDPOINT}"

cat > "$HOOK_PATH" << 'HOOKEOF'
#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
# SOVEREIGN-PAAS-HOOK — Auto-generated post-merge deployment trigger
# Installed by setup_local_hook.sh
# DO NOT EDIT — reinstall with setup_local_hook.sh to update config
# ═══════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Configuration (injected at install time) ──────────────────────
HOOKEOF

# Inject dynamic values (not part of the heredoc to allow variable expansion)
cat >> "$HOOK_PATH" << EOF
WEBHOOK_URL="${WEBHOOK_URL}"
WEBHOOK_SECRET="${WEBHOOK_SECRET}"
EOF

# Continue with the static hook body
cat >> "$HOOK_PATH" << 'HOOKEOF'

# ── Gather Git Context ───────────────────────────────────────────
REPO_PATH="$(git rev-parse --show-toplevel)"
REPO_NAME="$(basename "$REPO_PATH")"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
COMMIT_SHA="$(git rev-parse HEAD)"
COMMIT_MSG="$(git log -1 --format='%s' HEAD)"
AUTHOR="$(git log -1 --format='%an' HEAD)"
TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

# ── Build Payload ────────────────────────────────────────────────
PAYLOAD=$(cat << JSONEOF
{
    "source": "local",
    "event": "merge",
    "branch": "${BRANCH}",
    "repo_name": "${REPO_NAME}",
    "repo_path": "${REPO_PATH}",
    "commit_sha": "${COMMIT_SHA}",
    "commit_message": "${COMMIT_MSG}",
    "sender": "${AUTHOR}",
    "timestamp": "${TIMESTAMP}"
}
JSONEOF
)

# ── Compute HMAC Signature ───────────────────────────────────────
SIGNATURE=""
if [[ -n "$WEBHOOK_SECRET" ]]; then
    SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | awk '{print $NF}')
fi

# ── Fire Webhook ─────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  SOVEREIGN PAAS — Post-Merge Deployment Trigger            ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  Repo:    ${REPO_NAME}"
echo "║  Branch:  ${BRANCH}"
echo "║  Commit:  ${COMMIT_SHA:0:12}"
echo "║  Message: ${COMMIT_MSG:0:50}"
echo "║  Target:  ${WEBHOOK_URL}"
echo "╚══════════════════════════════════════════════════════════════╝"

# Build curl command
CURL_ARGS=(
    -s
    -X POST
    "${WEBHOOK_URL}"
    -H "Content-Type: application/json"
)

if [[ -n "$SIGNATURE" ]]; then
    CURL_ARGS+=(-H "X-Sovereign-Signature: sha256=${SIGNATURE}")
fi

CURL_ARGS+=(-d "$PAYLOAD")

# Send the webhook (non-blocking — don't stall the merge)
RESPONSE=$(curl -w "\n%{http_code}" "${CURL_ARGS[@]}" 2>/dev/null) || {
    echo "⚠  Webhook delivery failed — is the Sovereign Listener running?"
    echo "   Start it with: python sovereign_listener.py --port ${WEBHOOK_URL##*:}"
    exit 0  # Don't fail the merge
}

# Parse response
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [[ "$HTTP_CODE" == "202" ]]; then
    echo "✓  Webhook accepted (HTTP ${HTTP_CODE}) — deployment triggered"
elif [[ "$HTTP_CODE" == "200" ]]; then
    echo "→  Webhook received (HTTP ${HTTP_CODE}) — event processed"
elif [[ "$HTTP_CODE" == "403" ]]; then
    echo "✗  Webhook rejected (HTTP ${HTTP_CODE}) — authentication failed"
    echo "   Check your HMAC secret matches the listener's --secret flag"
else
    echo "⚠  Unexpected response (HTTP ${HTTP_CODE})"
    echo "   Response: ${BODY:0:200}"
fi

echo ""
HOOKEOF

# Make the hook executable
chmod +x "$HOOK_PATH"

# ─── Output ───────────────────────────────────────────────────────────────

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║${GREEN}  SOVEREIGN PAAS — Local Hook Installed                          ${BOLD}║${NC}"
echo -e "${BOLD}╠══════════════════════════════════════════════════════════════════╣${NC}"
echo -e "${BOLD}║${NC}  Repository:  ${CYAN}${REPO_PATH}${NC}"
echo -e "${BOLD}║${NC}  Hook:        ${CYAN}${HOOK_PATH}${NC}"
echo -e "${BOLD}║${NC}  Webhook URL: ${CYAN}${WEBHOOK_URL}${NC}"
if [[ -n "$WEBHOOK_SECRET" ]]; then
echo -e "${BOLD}║${NC}  HMAC Secret: ${CYAN}${WEBHOOK_SECRET:0:8}...${NC}"
else
echo -e "${BOLD}║${NC}  HMAC Secret: ${YELLOW}(none — set with --secret)${NC}"
fi
echo -e "${BOLD}╚══════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}Done.${NC} The hook will fire whenever you run ${BOLD}git merge${NC} in this repo."
echo ""
echo -e "To test manually:"
echo -e "  ${CYAN}cd ${REPO_PATH}${NC}"
echo -e "  ${CYAN}git merge janitor-fix-xxxxxxxx${NC}"
echo ""
echo -e "To remove:"
echo -e "  ${CYAN}$0 ${REPO_PATH} --remove${NC}"
echo ""
