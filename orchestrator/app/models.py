from pydantic import BaseModel
from typing import Any, Dict

class RunAgentRequest(BaseModel):
    agent_name: str
    payload: Dict[str, Any]

class RunAgentResponse(BaseModel):
    agent_name: str
    result: Dict[str, Any]
