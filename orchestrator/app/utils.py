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


def load_all_agent_configs() -> Dict[str, Dict[str, Any]]:
    """Load all agent YAML files in the agents directory."""
    configs: Dict[str, Dict[str, Any]] = {}

    for path in sorted(AGENTS_DIR.glob("agent_*.yaml")):
        with path.open("r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

        name = cfg.get("name")
        if isinstance(name, str) and name.strip():
            configs[name.strip()] = cfg

    return configs


def _payload_message(payload: Dict[str, Any]) -> str:
    raw = payload.get("message")
    if raw is None:
        raw = payload.get("input")
    if raw is None:
        return ""
    return str(raw)


def _render_agent_response(
    agent_cfg: Dict[str, Any],
    payload: Dict[str, Any],
) -> str:
    """Render a user-facing response for non-router agents."""
    name = str(agent_cfg.get("name", "unknown"))
    agent_type = str(agent_cfg.get("type", "generic"))
    message = _payload_message(payload)

    if agent_type == "language_model":
        return f"LLM agent received: {message}"

    if agent_type == "http_api":
        return f"{name.capitalize()} agent received: {message}"

    if agent_type == "scheduler":
        return f"Scheduler received: {message}"

    return f"Agent '{name}' received: {message}"


def _route_message(
    router_cfg: Dict[str, Any],
    message: str,
    agents: Dict[str, Dict[str, Any]],
) -> str:
    """Choose an agent based on router rules and fallback logic."""
    lowered = message.lower()

    for route in router_cfg.get("routes", []):
        match = str(route.get("match", "")).strip().lower()
        target = str(route.get("agent", "")).strip()

        if not match or not target:
            continue

        if match in lowered and target in agents:
            return target

    fallback = str(router_cfg.get("fallback_agent", "")).strip()
    if fallback and fallback in agents:
        return fallback

    for candidate in ("llm", "scheduler", "weather"):
        if candidate in agents:
            return candidate

    return "router"


def run_agent_logic(
    agent_cfg: Dict[str, Any],
    payload: Dict[str, Any],
    all_agents: Dict[str, Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    message = _payload_message(payload)
    agents = all_agents or {}
    agent_name = str(agent_cfg.get("name", "unknown"))
    agent_type = str(agent_cfg.get("type", "generic"))

    selected_agent = agent_name
    selected_cfg = agent_cfg

    if agent_type == "router":
        selected_agent = _route_message(agent_cfg, message, agents)
        selected_cfg = agents.get(selected_agent, agent_cfg)

    response = _render_agent_response(selected_cfg, payload)

    return {
        "description": f"Ran agent '{agent_name}'",
        "response": response,
        "selected_agent": selected_agent,
        "available_agents": sorted(agents.keys()) if agents else [agent_name],
        "config": agent_cfg,
        "input": payload,
    }
