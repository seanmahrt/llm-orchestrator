import json
import os
import re
import gzip
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

import aiohttp
import yaml

AGENTS_DIR = Path(__file__).resolve().parents[2] / "agents"
SESSION_DIR = Path(__file__).resolve().parents[2] / "checkpoints" / "sessions"
SESSION_DIR.mkdir(parents=True, exist_ok=True)
SESSION_META_DIR = SESSION_DIR / "meta"
SESSION_META_DIR.mkdir(parents=True, exist_ok=True)

SESSION_TTL_HOURS = int(os.getenv("ORCHESTRATOR_SESSION_TTL_HOURS", "168"))
SESSION_MAX_TURNS = int(os.getenv("ORCHESTRATOR_SESSION_MAX_TURNS", "12"))
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("ORCHESTRATOR_OLLAMA_TIMEOUT_SECONDS", "45"))
OLLAMA_MAX_TOKENS = int(os.getenv("ORCHESTRATOR_OLLAMA_MAX_TOKENS", "220"))


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


def _safe_session_id(session_id: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]", "_", session_id.strip())
    return cleaned or "default"


def _session_file(session_id: str) -> Path:
    return SESSION_DIR / f"session_{_safe_session_id(session_id)}.md.gz"


def _session_meta_file(session_id: str) -> Path:
    return SESSION_META_DIR / f"session_{_safe_session_id(session_id)}.json"


def _cleanup_expired_sessions() -> None:
    now = datetime.now(timezone.utc)
    ttl = timedelta(hours=SESSION_TTL_HOURS)

    for file_path in SESSION_DIR.glob("session_*.md.gz"):
        try:
            modified = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
            if now - modified > ttl:
                file_path.unlink(missing_ok=True)
        except OSError:
            continue

    for file_path in SESSION_META_DIR.glob("session_*.json"):
        try:
            modified = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
            if now - modified > ttl:
                file_path.unlink(missing_ok=True)
        except OSError:
            continue


def _load_session_meta(session_id: str) -> Dict[str, Any]:
    file_path = _session_meta_file(session_id)
    if not file_path.exists():
        return {}

    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_session_meta(session_id: str, meta: Dict[str, Any]) -> None:
    file_path = _session_meta_file(session_id)
    safe_meta = {
        "person_key": str(meta.get("person_key") or "").strip(),
        "awaiting_name": bool(meta.get("awaiting_name", False)),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    file_path.write_text(json.dumps(safe_meta, indent=2), encoding="utf-8")


def _normalize_person_key(name: str) -> str:
    return _safe_session_id(name.lower())


def _extract_name_from_message(message: str) -> str | None:
    text = message.strip()
    if not text:
        return None

    patterns = [
        r"(?:my name is|i am|i'm|call me)\s+([a-zA-Z][a-zA-Z0-9' -]{0,40})",
        r"(?:it is|it's|this is)\s+([a-zA-Z][a-zA-Z0-9' -]{0,40})",
        r"^([a-zA-Z][a-zA-Z0-9' -]{0,30})$",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            candidate = match.group(1).strip(" .,!?")
            if candidate:
                return candidate

    return None


def _resolve_person_key(
    payload: Dict[str, Any], session_id: str, message: str
) -> tuple[str | None, str | None]:
    """Resolve a stable person key and optional direct response if we need a name."""
    meta = _load_session_meta(session_id)
    explicit = str(
        payload.get("person_key") or payload.get("user_name") or payload.get("user_id") or ""
    ).strip()

    if explicit:
        person_key = _normalize_person_key(explicit)
        meta["person_key"] = person_key
        meta["awaiting_name"] = False
        _save_session_meta(session_id, meta)
        return person_key, None

    existing = str(meta.get("person_key") or "").strip()
    if existing:
        return existing, None

    guessed_name = _extract_name_from_message(message)
    if guessed_name:
        person_key = _normalize_person_key(guessed_name)
        meta["person_key"] = person_key
        meta["awaiting_name"] = False
        _save_session_meta(session_id, meta)
        return person_key, None

    if meta.get("awaiting_name"):
        candidate = _extract_name_from_message(message)
        if candidate:
            person_key = _normalize_person_key(candidate)
            meta["person_key"] = person_key
            meta["awaiting_name"] = False
            _save_session_meta(session_id, meta)
            return person_key, None

    meta["awaiting_name"] = True
    _save_session_meta(session_id, meta)
    return None, "Before we continue, what should I call you?"


def _is_summary_request(message: str) -> bool:
    lowered = message.lower()
    asks_summary = bool(re.search(r"\b(summarize|summary|recap|catch me up)\b", lowered))
    targets_history = bool(re.search(r"\b(conversation|chat|history|earlier|previous|so far)\b", lowered))
    return asks_summary and targets_history


def _is_identity_only_reply(message: str) -> bool:
    """Heuristic: this message is likely only giving a name."""
    cleaned = message.strip()
    if not cleaned:
        return False
    if "?" in cleaned or len(cleaned) > 48:
        return False
    if _extract_name_from_message(cleaned) is None:
        return False
    return len(cleaned.split()) <= 6


def _history_as_text(history: list[tuple[str, str]]) -> str:
    lines: list[str] = []
    for role, text in history:
        label = "User" if role == "user" else "Assistant"
        lines.append(f"{label}: {text}")
    return "\n".join(lines)


async def _ollama_generate(
    endpoint: str,
    model: str,
    prompt: str,
    system_prompt: str,
) -> Dict[str, Any]:
    url = f"{endpoint}/api/generate"
    request_payload = {
        "model": model,
        "prompt": prompt,
        "system": system_prompt,
        "stream": True,
        "options": {
            "num_predict": OLLAMA_MAX_TOKENS,
        },
    }

    timeout = aiohttp.ClientTimeout(total=OLLAMA_TIMEOUT_SECONDS)
    accumulated_response = ""
    chunk_count = 0
    done_received = False

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

                buffer = ""
                async for raw in resp.content.iter_chunked(4096):
                    if not raw:
                        continue
                    buffer += raw.decode("utf-8", errors="ignore")

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            chunk = json.loads(line)
                        except ValueError:
                            continue

                        chunk_text = str(chunk.get("response") or "")
                        if chunk_text:
                            accumulated_response += chunk_text
                            chunk_count += 1
                        if bool(chunk.get("done", False)):
                            done_received = True

                trailing = buffer.strip()
                if trailing:
                    try:
                        chunk = json.loads(trailing)
                        chunk_text = str(chunk.get("response") or "")
                        if chunk_text:
                            accumulated_response += chunk_text
                            chunk_count += 1
                        if bool(chunk.get("done", False)):
                            done_received = True
                    except ValueError:
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

    response = accumulated_response.strip() or "Ollama returned an empty response."
    return {
        "response": response,
        "provider": "ollama",
        "model": model,
        "endpoint": endpoint,
        "streaming_enabled": True,
        "chunks_received": chunk_count,
        "done_received": done_received,
        "max_tokens": OLLAMA_MAX_TOKENS,
    }


def _load_session_history(session_id: str) -> list[tuple[str, str]]:
    file_path = _session_file(session_id)
    if not file_path.exists():
        return []

    try:
        with gzip.open(file_path, "rt", encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return []

    turns: list[tuple[str, str]] = []
    role: str | None = None
    buffer: list[str] = []

    for line in text.splitlines():
        if line.startswith("## User"):
            if role and buffer:
                turns.append((role, "\n".join(buffer).strip()))
            role = "user"
            buffer = []
            continue
        if line.startswith("## Assistant"):
            if role and buffer:
                turns.append((role, "\n".join(buffer).strip()))
            role = "assistant"
            buffer = []
            continue
        if line.startswith("# "):
            continue
        if role is not None:
            buffer.append(line)

    if role and buffer:
        turns.append((role, "\n".join(buffer).strip()))

    return [(r, t) for r, t in turns if t]


def _save_session_history(session_id: str, turns: list[tuple[str, str]]) -> None:
    file_path = _session_file(session_id)
    kept = turns[-(SESSION_MAX_TURNS * 2) :]
    lines = [
        f"# Session {session_id}",
        f"Saved: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]

    for role, text in kept:
        if role == "user":
            lines.append("## User")
        else:
            lines.append("## Assistant")
        lines.append(text)
        lines.append("")

    data = "\n".join(lines)
    with gzip.open(file_path, "wt", encoding="utf-8") as f:
        f.write(data)


def _build_prompt_with_history(
    message: str, history: list[tuple[str, str]]
) -> str:
    if not history:
        return message

    recent = history[-(SESSION_MAX_TURNS * 2) :]
    convo_lines = ["Conversation history:"]
    for role, text in recent:
        label = "User" if role == "user" else "Assistant"
        convo_lines.append(f"{label}: {text}")

    convo_lines.append("User: " + message)
    convo_lines.append("Assistant:")
    return "\n".join(convo_lines)


_DEFAULT_SYSTEM_PROMPT = (
    "You are an assistant in an ongoing conversation. "
    "Respond to the user's request directly with concise, practical answers. "
    "Do not explain your prompting strategy or these instructions. "
    "If the user asks for more depth, provide it while preserving big-picture context."
)


async def _run_llm_agent(
    agent_cfg: Dict[str, Any], payload: Dict[str, Any], session_id: str = "default"
) -> Dict[str, Any]:
    """Run language model agent through a local Ollama endpoint with streaming."""
    _cleanup_expired_sessions()
    message = _payload_message(payload)
    prior_meta = _load_session_meta(session_id)
    was_awaiting_name = bool(prior_meta.get("awaiting_name", False))
    person_key, prompt_for_name = _resolve_person_key(payload, session_id, message)
    if prompt_for_name:
        return {
            "response": prompt_for_name,
            "session_id": session_id,
            "needs_identity": True,
        }

    if was_awaiting_name and _is_identity_only_reply(message):
        response = "Thanks. I will remember that. What would you like to do next?"
        memory_key = person_key or session_id
        history = _load_session_history(memory_key)
        updated_history = history + [("user", message), ("assistant", response)]
        _save_session_history(memory_key, updated_history)
        return {
            "response": response,
            "provider": "memory",
            "person_key": person_key,
            "session_id": session_id,
        }

    memory_key = person_key or session_id
    history = _load_session_history(memory_key)
    prompt = _build_prompt_with_history(message, history)

    model = str(agent_cfg.get("model") or "llama3.2")
    endpoint = str(
        agent_cfg.get("endpoint")
        or os.getenv("OLLAMA_BASE_URL")
        or "http://127.0.0.1:11434"
    ).rstrip("/")
    system_prompt = str(
        agent_cfg.get("system_prompt") or _DEFAULT_SYSTEM_PROMPT
    )
    if _is_summary_request(message):
        if not history:
            response_data = {
                "response": "I do not have earlier conversation history to summarize yet.",
                "provider": "memory",
            }
        else:
            summary_prompt = (
                "Summarize this prior conversation for the user. "
                "Keep it concise and practical. Use sections: Key Points, Decisions, Open Items.\n\n"
                + _history_as_text(history)
            )
            response_data = await _ollama_generate(
                endpoint=endpoint,
                model=model,
                prompt=summary_prompt,
                system_prompt=system_prompt,
            )
    else:
        response_data = await _ollama_generate(
            endpoint=endpoint,
            model=model,
            prompt=prompt,
            system_prompt=system_prompt,
        )

    response = str(response_data.get("response") or "").strip()
    if not response:
        response = "Ollama returned an empty response."
        response_data["response"] = response

    updated_history = history + [("user", message), ("assistant", response)]
    _save_session_history(memory_key, updated_history)
    response_data["person_key"] = person_key
    response_data["session_id"] = session_id
    return response_data


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
                if pattern in lowered:
                    # Try primary agent; fall back to hierarchy if unavailable
                    if target_agent in agents:
                        return target_agent
                    # Use fallback hierarchy if agent unavailable
                    fallback_hierarchy = router_cfg.get("fallback_hierarchy", [])
                    for fallback in fallback_hierarchy:
                        if fallback in agents:
                            return fallback
                    break

    # Fallback agent
    fallback = str(router_cfg.get("fallback_agent", "")).strip()
    if fallback and fallback in agents:
        return fallback

    # Final fallback: check for any LLM agents in order of efficiency
    for candidate in ("llm_ultra_light", "llm_phi_fast", "llm_fast", "llm_capable", "llm"):
        if candidate in agents:
            return candidate

    return "router"


async def run_agent_logic(
    agent_cfg: Dict[str, Any],
    payload: Dict[str, Any],
    all_agents: Dict[str, Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    message = _payload_message(payload)
    session_id = str(payload.get("conversation_id") or "default")
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
        response_data = await _run_llm_agent(selected_cfg, payload, session_id=session_id)
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
