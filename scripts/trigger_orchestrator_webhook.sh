#!/usr/bin/env bash
set -uo pipefail

# Sends a signed LAN webhook request to the orchestrator deploy endpoint.
# Env vars:
#   ORCH_WEBHOOK_URL    (default: http://192.168.75.95:8000/webhook/github)
#   ORCH_WEBHOOK_SECRET (optional, but recommended)
#   ORCH_WEBHOOK_TIMEOUT (default: 8)
#   ORCH_WEBHOOK_CONNECT_TIMEOUT (default: 2)

ORCH_WEBHOOK_URL="${ORCH_WEBHOOK_URL:-http://192.168.75.95:8000/webhook/github}"
ORCH_WEBHOOK_SECRET="${ORCH_WEBHOOK_SECRET:-}"
ORCH_WEBHOOK_TIMEOUT="${ORCH_WEBHOOK_TIMEOUT:-8}"
ORCH_WEBHOOK_CONNECT_TIMEOUT="${ORCH_WEBHOOK_CONNECT_TIMEOUT:-2}"

BRANCH="${1:-$(git rev-parse --abbrev-ref HEAD)}"
LOCAL_SHA="${2:-$(git rev-parse HEAD)}"
UTC_NOW="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

PAYLOAD="{\"ref\":\"refs/heads/${BRANCH}\",\"after\":\"${LOCAL_SHA}\",\"source\":\"dev-post-push\",\"timestamp\":\"${UTC_NOW}\"}"

CURL_ARGS=(
  --silent
  --show-error
  --fail
  --connect-timeout "${ORCH_WEBHOOK_CONNECT_TIMEOUT}"
  --max-time "${ORCH_WEBHOOK_TIMEOUT}"
  -X POST
  -H "Content-Type: application/json"
  -H "X-GitHub-Event: push"
  --data "${PAYLOAD}"
  "${ORCH_WEBHOOK_URL}"
)

if [[ -n "${ORCH_WEBHOOK_SECRET}" ]]; then
  if ! command -v openssl >/dev/null 2>&1; then
    echo "push-hook: openssl not found; sending unsigned webhook" >&2
    ORCH_WEBHOOK_SECRET=""
  fi

  if [[ -n "${ORCH_WEBHOOK_SECRET}" ]]; then
    SIG_HEX="$(printf '%s' "${PAYLOAD}" | openssl dgst -sha256 -hmac "${ORCH_WEBHOOK_SECRET}" -hex | awk '{print $NF}')"
    CURL_ARGS=(
      --silent
      --show-error
      --fail
      --connect-timeout "${ORCH_WEBHOOK_CONNECT_TIMEOUT}"
      --max-time "${ORCH_WEBHOOK_TIMEOUT}"
      -X POST
      -H "Content-Type: application/json"
      -H "X-GitHub-Event: push"
      -H "X-Hub-Signature-256: sha256=${SIG_HEX}"
      --data "${PAYLOAD}"
      "${ORCH_WEBHOOK_URL}"
    )
  fi
fi

if RESPONSE="$(curl "${CURL_ARGS[@]}" 2>&1)"; then
  echo "push-hook: webhook triggered (${ORCH_WEBHOOK_URL})"
  echo "push-hook: ${RESPONSE}"
else
  echo "push-hook: webhook unavailable (${ORCH_WEBHOOK_URL}); continuing push" >&2
  echo "push-hook: ${RESPONSE}" >&2
fi

exit 0
