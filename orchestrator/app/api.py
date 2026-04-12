import hashlib
import hmac
import os
import subprocess

from fastapi import APIRouter, Header, HTTPException, Request

from .models import RunAgentRequest, RunAgentResponse
from .utils import load_all_agent_configs, run_agent_logic
from .model_manager import get_model_manager

router = APIRouter()


@router.post("/orchestrator/run-agent", response_model=RunAgentResponse)
async def run_agent(request: RunAgentRequest) -> RunAgentResponse:
    """
    Main orchestrator entrypoint.
    Loads agent YAML and executes it.
    Returns Home Assistant–compatible response.
    """
    all_agents = load_all_agent_configs()
    agent_cfg = all_agents.get(request.agent_name)
    if not agent_cfg:
        raise HTTPException(
            status_code=404,
            detail=f"Agent config not found: {request.agent_name}",
        )

    result = await run_agent_logic(
        agent_cfg,
        request.payload,
        all_agents=all_agents,
    )
    return RunAgentResponse(agent_name=request.agent_name, result=result)


@router.get("/orchestrator/status")
async def get_status():
    """Get memory and model status for monitoring and debugging."""
    manager = get_model_manager()
    return manager.get_status()


@router.get("/orchestrator/memory")
async def get_memory():
    """Get memory utilization details."""
    manager = get_model_manager()
    return manager.get_memory_utilization()


# ---------------------------------------------------------------------------
# GitHub webhook — auto-deploy on push
# ---------------------------------------------------------------------------
_REPO_DIR = str(os.getenv("REPO_DIR", "/opt/llm-orchestrator"))
_SERVICE_NAME = str(os.getenv("ORCHESTRATOR_SERVICE", "llm-orchestrator"))
_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")


def _verify_github_signature(secret: str, body: bytes, sig_header: str) -> bool:
    """Validate the GitHub HMAC-SHA256 X-Hub-Signature-256 header."""
    if not sig_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, sig_header)


def _git_head_short(repo_dir: str) -> str | None:
    """Return short commit hash for HEAD, or None if unavailable."""
    head = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if head.returncode != 0:
        return None
    value = head.stdout.strip()
    return value or None


@router.post("/webhook/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(default=""),
    x_github_event: str = Header(default=""),
):
    """Receives GitHub push webhooks, pulls latest code, and restarts the service."""
    body = await request.body()

    if _WEBHOOK_SECRET:
        if not _verify_github_signature(_WEBHOOK_SECRET, body, x_hub_signature_256):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    if x_github_event not in ("push", ""):
        return {"status": "ignored", "event": x_github_event}

    commit_before = _git_head_short(_REPO_DIR)

    try:
        pull = subprocess.run(
            ["git", "pull", "--ff-only"],
            cwd=_REPO_DIR,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="git pull timed out")

    if pull.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"git pull failed: {pull.stderr.strip()}",
        )

    # Restart the systemd service so new code is loaded
    restart = subprocess.run(
        ["systemctl", "restart", _SERVICE_NAME],
        capture_output=True,
        text=True,
        timeout=15,
    )

    commit_after = _git_head_short(_REPO_DIR)

    return {
        "status": "ok",
        "commit_before": commit_before,
        "commit_after": commit_after,
        "git_output": pull.stdout.strip(),
        "service_restart": restart.returncode == 0,
        "service_restart_error": restart.stderr.strip(),
    }
