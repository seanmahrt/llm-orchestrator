from fastapi import APIRouter
from pydantic import BaseModel
from .utils import load_agent, run_agent_logic

router = APIRouter()


class AgentPayload(BaseModel):
    message: str
    conversation_id: str


class RunAgentRequest(BaseModel):
    agent_name: str
    payload: AgentPayload


@router.post("/orchestrator/run-agent")
async def run_agent(request: RunAgentRequest):
    """
    Modular Smart Orchestrator entrypoint.
    Loads the agent from YAML and executes it.
    Wraps the result in Home Assistant–compatible format.
    """

    agent_name = request.agent_name
    message = request.payload.message
    conv_id = request.payload.conversation_id

    # Load agent definition from agents/agent_<name>.yaml
    agent = load_agent(agent_name)

    # Run the agent logic (your modular architecture)
    agent_output = await run_agent_logic(agent, message, conv_id)

    # Wrap for Home Assistant
    return {
        "agent_name": agent_name,
        "result": {
            "response": agent_output.get("response", "Agent returned no response.")
        }
    }
