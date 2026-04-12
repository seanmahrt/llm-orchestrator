from fastapi import APIRouter
from fastapi import HTTPException

from .models import RunAgentRequest, RunAgentResponse
from .utils import load_all_agent_configs, run_agent_logic

router = APIRouter()


@router.post("/orchestrator/run-agent", response_model=RunAgentResponse)
async def run_agent(request: RunAgentRequest) -> RunAgentResponse:
    """
    Main orchestrator entrypoint.
    Loads agent YAML and executes it.
    Returns Home Assistant–compatible response.
    """
    all_agents = load_all_agent_configs()
    agent_cfg = all_agents.get(request.agent_name)
    if not agent_cfg:
        raise HTTPException(
            status_code=404,
            detail=f"Agent config not found: {request.agent_name}",
        )

    result = run_agent_logic(agent_cfg, request.payload, all_agents=all_agents)
    return RunAgentResponse(agent_name=request.agent_name, result=result)
