#!/usr/bin/env bash
set -uo pipefail

# Non-blocking health probe for the deploy target.
# Env vars:
#   ORCH_HEALTH_URL (default: derived from ORCH_WEBHOOK_URL)
#   ORCH_WEBHOOK_URL (default: http://192.168.75.194:8000/webhook/github)
#   ORCH_HEALTH_TIMEOUT (default: 2)

ORCH_WEBHOOK_URL="${ORCH_WEBHOOK_URL:-http://192.168.75.194:8000/webhook/github}"
ORCH_HEALTH_URL="${ORCH_HEALTH_URL:-${ORCH_WEBHOOK_URL%/webhook/github}/health}"
ORCH_HEALTH_TIMEOUT="${ORCH_HEALTH_TIMEOUT:-2}"

if curl --silent --show-error --fail \
  --connect-timeout "${ORCH_HEALTH_TIMEOUT}" \
  --max-time "${ORCH_HEALTH_TIMEOUT}" \
  "${ORCH_HEALTH_URL}" >/dev/null 2>&1; then
  echo "post-commit: orchestrator reachable at ${ORCH_HEALTH_URL}"
else
  echo "post-commit: WARNING orchestrator unreachable at ${ORCH_HEALTH_URL}" >&2
  echo "post-commit: auto-deploy may fail; you may need manual pull/restart" >&2
fi

exit 0
