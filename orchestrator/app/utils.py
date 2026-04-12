import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

import aiohttp
import yaml

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


async def _run_llm_agent(
    agent_cfg: Dict[str, Any], payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Run language model agent through a local Ollama endpoint with streaming."""
    message = _payload_message(payload)
    model = str(agent_cfg.get("model") or "llama3.2")
    endpoint = str(
        agent_cfg.get("endpoint")
        or os.getenv("OLLAMA_BASE_URL")
        or "http://127.0.0.1:11434"
    ).rstrip("/")
    url = f"{endpoint}/api/generate"

    request_payload = {
        "model": model,
        "prompt": message,
        "stream": True,  # Enable streaming for responsive UI
    }

    timeout = aiohttp.ClientTimeout(total=60)
    accumulated_response = ""
    chunk_count = 0

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=request_payload) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    return {
                        "response": (
                            "I could not reach the local Ollama service. "
                            f"HTTP {resp.status}."
                        ),
                        "provider": "ollama",
                        "model": model,
                        "endpoint": endpoint,
                        "error": body,
                    }

                # Stream response chunks line-by-line
                async for line in resp.content:
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        chunk_text = str(chunk.get("response") or "")
                        if chunk_text:
                            accumulated_response += chunk_text
                            chunk_count += 1
                    except (ValueError, KeyError):
                        pass

    except (aiohttp.ClientError, TimeoutError) as err:
        return {
            "response": (
                "I could not connect to Ollama. "
                "Check that the Ollama service is reachable "
                "from the orchestrator."
            ),
            "provider": "ollama",
            "model": model,
            "endpoint": endpoint,
            "error": str(err),
        }

    response = accumulated_response.strip()
    if not response:
        response = "Ollama returned an empty response."

    return {
        "response": response,
        "provider": "ollama",
        "model": model,
        "endpoint": endpoint,
        "streaming_enabled": True,
        "chunks_received": chunk_count,
    }


async def _run_weather_agent(
    agent_cfg: Dict[str, Any], payload: Dict[str, Any]
) -> Dict[str, Any]:
    """Run weather agent using OpenWeather if configured."""
    endpoint = str(agent_cfg.get("endpoint") or "").rstrip("/")
    api_key = os.getenv("OPENWEATHER_API_KEY", "").strip()
    query = str(payload.get("location") or "Boston,US")

    if not api_key:
        return {
            "response": (
                "Weather agent is configured but "
                "OPENWEATHER_API_KEY is missing."
            ),
            "endpoint": endpoint,
        }

    params = {
        "q": query,
        "appid": api_key,
        "units": "metric",
    }

    timeout = aiohttp.ClientTimeout(total=15)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(endpoint, params=params) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    return {
                        "response": (
                            f"Weather API request failed with {resp.status}."
                        ),
                        "endpoint": endpoint,
                        "error": body,
                    }
                data = await resp.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError) as err:
        return {
            "response": "Weather API is unreachable right now.",
            "endpoint": endpoint,
            "error": str(err),
        }

    main = data.get("main", {})
    weather = data.get("weather", [{}])
    description = str(weather[0].get("description") or "unknown").strip()
    temp = main.get("temp")

    return {
        "response": (
            "Current weather for "
            f"{query}: {description}, {temp} degrees Celsius."
        ),
        "endpoint": endpoint,
        "query": query,
    }


async def _run_scheduler_agent(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Parse simple schedule requests from natural language."""
    message = _payload_message(payload)
    lowered = message.lower()

    minutes_match = re.search(r"in\s+(\d+)\s+minute", lowered)
    hours_match = re.search(r"in\s+(\d+)\s+hour", lowered)

    if minutes_match:
        delta = timedelta(minutes=int(minutes_match.group(1)))
    elif hours_match:
        delta = timedelta(hours=int(hours_match.group(1)))
    else:
        return {
            "response": (
                "Scheduler can parse phrases like "
                "'in 15 minutes' or 'in 2 hours'."
            )
        }

    due = datetime.now(timezone.utc) + delta
    due_utc = due.isoformat().replace("+00:00", "Z")
    return {
        "response": f"Scheduled request acknowledged for {due_utc}.",
        "scheduled_for": due_utc,
    }


def _route_message(
    router_cfg: Dict[str, Any],
    message: str,
    agents: Dict[str, Dict[str, Any]],
) -> str:
    """Choose an agent based on router rules, intelligent LLM selection, and fallback logic."""
    lowered = message.lower()

    # Traditional route matching (weather, scheduler, etc.)
    for route in router_cfg.get("routes", []):
        match = str(route.get("match", "")).strip().lower()
        target = str(route.get("agent", "")).strip()

        if not match or not target:
            continue

        if match in lowered and target in agents:
            return target

    # Intelligent LLM routing based on task complexity
    if router_cfg.get("intelligent_model_selection"):
        llm_routes = router_cfg.get("llm_routes", [])
        for llm_route in llm_routes:
            patterns = llm_route.get("patterns", [])
            target_agent = str(llm_route.get("agent", "")).strip()

            # Check if any pattern keyword appears in the message
            for pattern in patterns:
                if pattern in lowered and target_agent in agents:
                    return target_agent

    # Fallback agent
    fallback = str(router_cfg.get("fallback_agent", "")).strip()
    if fallback and fallback in agents:
        return fallback

    # Final fallback: check for any LLM agents
    for candidate in ("llm_fast", "llm_capable", "llm"):
        if candidate in agents:
            return candidate

    return "router"


async def run_agent_logic(
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

    selected_type = str(selected_cfg.get("type", "generic"))

    if selected_agent == "router":
        response_data = {
            "response": _render_agent_response(selected_cfg, payload),
        }
    elif selected_type == "language_model":
        response_data = await _run_llm_agent(selected_cfg, payload)
    elif selected_type == "http_api":
        response_data = await _run_weather_agent(selected_cfg, payload)
    elif selected_type == "scheduler":
        response_data = await _run_scheduler_agent(payload)
    else:
        response_data = {
            "response": _render_agent_response(selected_cfg, payload),
        }

    response = str(response_data.get("response") or "").strip()
    if not response:
        response = "No response produced."

    return {
        "description": f"Ran agent '{agent_name}'",
        "response": response,
        "selected_agent": selected_agent,
        "available_agents": sorted(agents.keys()) if agents else [agent_name],
        "config": agent_cfg,
        "input": payload,
        "agent_result": response_data,
    }
