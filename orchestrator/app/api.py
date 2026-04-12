from fastapi import APIRouter
from fastapi import HTTPException

from .models import RunAgentRequest, RunAgentResponse
from .utils import load_agent_config, run_agent_logic

router = APIRouter()


@router.post("/orchestrator/run-agent", response_model=RunAgentResponse)
async def run_agent(request: RunAgentRequest) -> RunAgentResponse:
    """
    Main orchestrator entrypoint.
    Loads agent YAML and executes it.
    Returns Home Assistant–compatible response.
    """
    try:
        agent_cfg = load_agent_config(request.agent_name)
    except ValueError as err:
        raise HTTPException(status_code=404, detail=str(err)) from err

    result = run_agent_logic(agent_cfg, request.payload)
    return RunAgentResponse(agent_name=request.agent_name, result=result)
