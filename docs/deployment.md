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
