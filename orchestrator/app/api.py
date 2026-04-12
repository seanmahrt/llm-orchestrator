from fastapi import APIRouter
from .models import RunAgentRequest, RunAgentResponse
from .utils import load_agent_config, run_agent_logic

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])

@router.post("/run-agent", response_model=RunAgentResponse)
def run_agent(request: RunAgentRequest):
    agent_cfg = load_agent_config(request.agent_name)
    result = run_agent_logic(agent_cfg, request.payload)
    return RunAgentResponse(agent_name=request.agent_name, result=result)
