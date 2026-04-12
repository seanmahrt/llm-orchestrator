from fastapi import FastAPI
from .app.api import router as api_router

app = FastAPI(title="Orchestrator")

app.include_router(api_router)

@app.get("/health")
def health():
    return {"status": "ok"}
