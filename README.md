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
