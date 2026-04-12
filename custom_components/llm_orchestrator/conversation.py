import logging
import aiohttp

from homeassistant.components.conversation import (
    AbstractConversationAgent,
    ConversationInput,
    ConversationResult,
)
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

ORCHESTRATOR_URL = "http://localhost:8000/orchestrator/run-agent"


class LLMOrchestratorConversationAgent(AbstractConversationAgent):
    """Conversation agent that routes all messages through the orchestrator router."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass

    @property
    def attribution(self):
        return {"name": "LLM Orchestrator"}

    @property
    def supported_languages(self) -> list[str]:
        """Return the list of supported languages."""
        # You can expand this later if needed
        return ["en"]

    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        """Process a conversation request using the orchestrator router."""

        text = user_input.text
        conv_id = user_input.conversation_id or "default"

        payload = {
            "agent_name": "router",
            "payload": {
                "message": text,
                "conversation_id": conv_id,
            },
        }

        _LOGGER.debug("Sending to orchestrator: %s", payload)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(ORCHESTRATOR_URL, json=payload) as resp:
                    if resp.status != 200:
                        _LOGGER.error("Orchestrator returned HTTP %s", resp.status)
                        return ConversationResult(
                            response="I had trouble contacting the orchestrator."
                        )

                    data = await resp.json()
                    _LOGGER.debug("Received from orchestrator: %s", data)

                    response_text = (
                        data.get("result", {}).get("response")
                        or "I didn't get a response from the orchestrator."
                    )

                    return ConversationResult(response=response_text)

        except Exception as e:
            _LOGGER.exception("Error calling orchestrator: %s", e)
            return ConversationResult(
                response="Something went wrong talking to the orchestrator."
            )
