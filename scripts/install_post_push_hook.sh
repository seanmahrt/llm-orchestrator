#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK_PATH="${REPO_ROOT}/.git/hooks/pre-push"
TRIGGER_SCRIPT="${REPO_ROOT}/scripts/trigger_orchestrator_webhook.sh"
POST_COMMIT_HOOK_PATH="${REPO_ROOT}/.git/hooks/post-commit"
HEALTH_SCRIPT="${REPO_ROOT}/scripts/check_orchestrator_health.sh"

if [[ ! -d "${REPO_ROOT}/.git/hooks" ]]; then
  echo "Could not find .git/hooks in ${REPO_ROOT}" >&2
  exit 1
fi

cat > "${HOOK_PATH}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
TRIGGER_SCRIPT="${REPO_ROOT}/scripts/trigger_orchestrator_webhook.sh"

REMOTE_NAME="${1:-origin}"

# pre-push stdin format: <local_ref> <local_sha> <remote_ref> <remote_sha>
BRANCH=""
LOCAL_SHA=""
if IFS=' ' read -r local_ref local_sha remote_ref remote_sha; then
  BRANCH="${local_ref#refs/heads/}"
  LOCAL_SHA="${local_sha}"
fi

if [[ -z "${BRANCH}" || "${BRANCH}" == "${local_ref}" ]]; then
  BRANCH="$(git rev-parse --abbrev-ref HEAD)"
fi
if [[ -z "${LOCAL_SHA}" ]]; then
  LOCAL_SHA="$(git rev-parse HEAD)"
fi

if [[ ! -x "${TRIGGER_SCRIPT}" ]]; then
  echo "pre-push: missing trigger script at ${TRIGGER_SCRIPT}" >&2
  exit 0
fi

# Fire-and-forget worker: wait until origin shows the pushed SHA, then trigger deploy webhook.
(
  for _ in $(seq 1 20); do
    REMOTE_SHA="$(git ls-remote --heads "${REMOTE_NAME}" "refs/heads/${BRANCH}" | awk '{print $1}')"
    if [[ "${REMOTE_SHA}" == "${LOCAL_SHA}" ]]; then
      "${TRIGGER_SCRIPT}" "${BRANCH}" "${LOCAL_SHA}" >/tmp/llm_orchestrator_hook.log 2>&1 || true
      exit 0
    fi
    sleep 1
  done
  echo "push-hook: commit ${LOCAL_SHA} not visible on ${REMOTE_NAME}/${BRANCH} within timeout" >> /tmp/llm_orchestrator_hook.log
) >/dev/null 2>&1 &

exit 0
EOF

cat > "${POST_COMMIT_HOOK_PATH}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
HEALTH_SCRIPT="${REPO_ROOT}/scripts/check_orchestrator_health.sh"

if [[ -x "${HEALTH_SCRIPT}" ]]; then
  "${HEALTH_SCRIPT}" || true
else
  echo "post-commit: missing health script at ${HEALTH_SCRIPT}" >&2
fi

exit 0
EOF

chmod +x "${HOOK_PATH}"
chmod +x "${TRIGGER_SCRIPT}"
chmod +x "${POST_COMMIT_HOOK_PATH}"
chmod +x "${HEALTH_SCRIPT}"

echo "Installed git pre-push hook at ${HOOK_PATH}"
echo "Installed git post-commit hook at ${POST_COMMIT_HOOK_PATH}"
echo "Set ORCH_WEBHOOK_URL and ORCH_WEBHOOK_SECRET in your shell/profile for signing."
echo "Hook is non-blocking: push continues even if webhook is unreachable."
