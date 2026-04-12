from fastapi import APIRouter
from pydantic import BaseModel
import yaml
import os

router = APIRouter()

AGENT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "agents")


class AgentPayload(BaseModel):
    message: str
    conversation_id: str


class RunAgentRequest(BaseModel):
    agent_name: str
    payload: AgentPayload


def load_agent(agent_name: str):
    """Load agent YAML definition."""
    path = os.path.join(AGENT_DIR, f"agent_{agent_name}.yaml")
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return yaml.safe_load(f)


async def run_agent_logic(agent: dict, message: str, conv_id: str):
    """
    Minimal agent executor.
    For now, just echo back the routing decision.
    """
    if not agent:
        return {"response": f"Agent '{agent}' not found."}

    # Basic router behavior for now
    return {
        "response": f"Agent '{agent.get('name')}' received: {message}"
    }


@router.post("/orchestrator/run-agent")
async def run_agent(request: RunAgentRequest):
    """
    Main orchestrator entrypoint.
    Loads agent YAML and executes it.
    Returns Home Assistant–compatible response.
    """

    agent_name = request.agent_name
    message = request.payload.message
    conv_id = request.payload.conversation_id

    agent = load_agent(agent_name)
    result = await run_agent_logic(agent, message, conv_id)

    return {
        "agent_name": agent_name,
        "result": {
            "response": result.get("response", "No response produced.")
        }
    }
