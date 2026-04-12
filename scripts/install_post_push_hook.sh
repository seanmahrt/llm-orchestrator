#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK_PATH="${REPO_ROOT}/.git/hooks/post-push"
TRIGGER_SCRIPT="${REPO_ROOT}/scripts/trigger_orchestrator_webhook.sh"

if [[ ! -d "${REPO_ROOT}/.git/hooks" ]]; then
  echo "Could not find .git/hooks in ${REPO_ROOT}" >&2
  exit 1
fi

cat > "${HOOK_PATH}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
TRIGGER_SCRIPT="${REPO_ROOT}/scripts/trigger_orchestrator_webhook.sh"

# post-push receives refs on stdin; keep first line for branch context if present
FIRST_REF_LINE=""
if IFS= read -r FIRST_REF_LINE; then
  :
fi

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
LOCAL_SHA="$(git rev-parse HEAD)"

if [[ -x "${TRIGGER_SCRIPT}" ]]; then
  if ! "${TRIGGER_SCRIPT}" "${BRANCH}" "${LOCAL_SHA}"; then
    echo "post-push: webhook trigger failed" >&2
  fi
else
  echo "post-push: missing trigger script at ${TRIGGER_SCRIPT}" >&2
fi
EOF

chmod +x "${HOOK_PATH}"
chmod +x "${TRIGGER_SCRIPT}"

echo "Installed git post-push hook at ${HOOK_PATH}"
echo "Set ORCH_WEBHOOK_URL and ORCH_WEBHOOK_SECRET in your shell/profile for signing."
echo "Hook is non-blocking: push succeeds even if webhook is unreachable."
