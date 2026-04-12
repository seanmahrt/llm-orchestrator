#!/usr/bin/env bash
set -euo pipefail

echo "Building orchestrator repo..."

mkdir -p orchestrator/app
mkdir -p agents
mkdir -p checkpoints
mkdir -p docs

############################################
# Root-level files
############################################

cat > README.md << 'EOF'
# Orchestrator Repository

This repository implements a modular orchestration layer for multi‑agent workflows.

## Structure

- orchestrator/ – FastAPI app and orchestration logic
- agents/ – agent configuration and behavior definitions
- checkpoints/ – human‑readable checkpoint logs
- docs/ – architecture and usage documentation

## Quick start

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn orchestrator.main:app --reload
EOF

cat > .gitignore << 'EOF'
__pycache__/
*.py[cod]
*.pyo
*.pyd
*.log
.venv/
env/
venv/
.vscode/
.idea/
.DS_Store
Thumbs.db
EOF

cat > requirements.txt << 'EOF'
fastapi
uvicorn[standard]
pydantic
pyyaml
EOF

cat > config.yaml << 'EOF'
orchestrator:
  host: 0.0.0.0
  port: 8000

logging:
  level: INFO

agents:
  - name: llm
    config: agents/agent_llm.yaml
  - name: weather
    config: agents/agent_weather.yaml
  - name: scheduler
    config: agents/agent_scheduler.yaml
EOF

cat > deploy.sh << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

python -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

uvicorn orchestrator.main:app --host 0.0.0.0 --port 8000
EOF

chmod +x deploy.sh

############################################
# Orchestrator files
############################################

cat > orchestrator/main.py << 'EOF'
from fastapi import FastAPI
from .app.api import router as api_router

app = FastAPI(title="Orchestrator")

app.include_router(api_router)

@app.get("/health")
def health():
    return {"status": "ok"}
EOF

cat > orchestrator/.gitignore << 'EOF'
__pycache__/
*.py[cod]
EOF

cat > orchestrator/requirements.txt << 'EOF'
# Local override if needed; root requirements.txt is primary.
EOF

cat > orchestrator/config.yaml << 'EOF'
service:
  name: orchestrator
  api_prefix: /orchestrator
EOF

cat > orchestrator/deploy.sh << 'EOF'
#!/usr/bin/env bash
set -euo pipefail

uvicorn orchestrator.main:app --host 0.0.0.0 --port 8000
EOF

chmod +x orchestrator/deploy.sh

cat > orchestrator/app/__init__.py << 'EOF'
# Package marker
EOF

cat > orchestrator/app/api.py << 'EOF'
from fastapi import APIRouter
from .models import RunAgentRequest, RunAgentResponse
from .utils import load_agent_config, run_agent_logic

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])

@router.post("/run-agent", response_model=RunAgentResponse)
def run_agent(request: RunAgentRequest):
    agent_cfg = load_agent_config(request.agent_name)
    result = run_agent_logic(agent_cfg, request.payload)
    return RunAgentResponse(agent_name=request.agent_name, result=result)
EOF

cat > orchestrator/app/models.py << 'EOF'
from pydantic import BaseModel
from typing import Any, Dict

class RunAgentRequest(BaseModel):
    agent_name: str
    payload: Dict[str, Any]

class RunAgentResponse(BaseModel):
    agent_name: str
    result: Dict[str, Any]
EOF

cat > orchestrator/app/utils.py << 'EOF'
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

def run_agent_logic(agent_cfg: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "description": f"Ran agent '{agent_cfg.get('name')}'",
        "config": agent_cfg,
        "input": payload,
    }
EOF

############################################
# Agents
############################################

cat > agents/agent_llm.yaml << 'EOF'
name: llm
type: language_model
model: gpt-4
description: >
  General-purpose LLM agent used for reasoning and text generation.
EOF

cat > agents/agent_weather.yaml << 'EOF'
name: weather
type: http_api
endpoint: https://api.openweathermap.org/data/2.5/weather
description: >
  Weather agent used for fetching current conditions and forecasts.
EOF

cat > agents/agent_scheduler.yaml << 'EOF'
name: scheduler
type: scheduler
description: >
  Schedules and sequences multi-step workflows across agents.
EOF

############################################
# Checkpoints
############################################

cat > checkpoints/checkpoint_001.md << 'EOF'
# Checkpoint 001

- Initialized orchestrator repo structure
- Defined core FastAPI entrypoint
- Added base agent configs
EOF

cat > checkpoints/checkpoint_002.md << 'EOF'
# Checkpoint 002

- Wired /orchestrator/run-agent endpoint
- Implemented config loading and basic agent execution stub
EOF

cat > checkpoints/checkpoint_003.md << 'EOF'
# Checkpoint 003

- Added documentation skeleton
- Ready for integration with real agent logic and external systems
EOF

############################################
# Docs
############################################

cat > docs/README.md << 'EOF'
# Orchestrator Documentation

See:

- architecture.md for high-level design
- agents.md for agent definitions
- checkpoints.md for process history
- deployment.md for running in different environments
EOF

cat > docs/architecture.md << 'EOF'
# Architecture

The orchestrator exposes a FastAPI service that coordinates multiple agents.

- API layer: orchestrator/app/api.py
- Models: orchestrator/app/models.py
- Agent utilities: orchestrator/app/utils.py
- Agent configs: agents/*.yaml
- Checkpoints: checkpoints/*.md
EOF

cat > docs/agents.md << 'EOF'
# Agents

## LLM Agent
- Config: agents/agent_llm.yaml
- Role: general reasoning and text generation

## Weather Agent
- Config: agents/agent_weather.yaml
- Role: fetch weather data

## Scheduler Agent
- Config: agents/agent_scheduler.yaml
- Role: orchestrate multi-step workflows
EOF

cat > docs/checkpoints.md << 'EOF'
# Checkpoints

Checkpoints document key milestones in the orchestration design and implementation.

See:

- checkpoint_001.md
- checkpoint_002.md
- checkpoint_003.md
EOF

cat > docs/deployment.md << 'EOF'
# Deployment

## Local

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn orchestrator.main:app --reload

## Production

- Use deploy.sh as a starting point
- Front with a reverse proxy (e.g., nginx)
- Configure logging and monitoring
EOF

echo "Repo build complete."
