import yaml
from pathlib import Path
from typing import Any, Dict

AGENTS_DIR = Path(__file__).resolve().parents[2] / "agents"


def load_agent_config(agent_name: str) -> Dict[str, Any]:
    path = AGENTS_DIR / f"agent_{agent_name}.yaml"
    if not path.exists():
        raise ValueError(f"Agent config not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def run_agent_logic(
    agent_cfg: Dict[str, Any], payload: Dict[str, Any]
) -> Dict[str, Any]:
    message = str(payload.get("message") or payload.get("input") or "")

    return {
        "description": f"Ran agent '{agent_cfg.get('name')}'",
        "response": f"Agent '{agent_cfg.get('name')}' received: {message}",
        "config": agent_cfg,
        "input": payload,
    }
