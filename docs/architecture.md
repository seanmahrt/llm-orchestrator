# Architecture

The orchestrator exposes a FastAPI service that coordinates multiple agents.

- API layer: orchestrator/app/api.py
- Models: orchestrator/app/models.py
- Agent utilities: orchestrator/app/utils.py
- Agent configs: agents/*.yaml
- Checkpoints: checkpoints/*.md
