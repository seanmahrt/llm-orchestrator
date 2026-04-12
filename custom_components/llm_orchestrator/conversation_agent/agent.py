import logging
import asyncio
import aiohttp

from homeassistant.components.conversation import (
    AbstractConversationAgent,
    ConversationInput,
    ConversationResult,
)
from homeassistant.helpers.intent import IntentResponse

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from ..const import CONF_HOST, CONF_PORT

_LOGGER = logging.getLogger(__name__)


class LLMOrchestratorConversationAgent(AbstractConversationAgent):
    """Conversation agent that routes all messages through the orchestrator router."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry

    @property
    def attribution(self):
        return {"name": "LLM Orchestrator"}

    @property
    def supported_languages(self) -> list[str]:
        return ["en"]

    @staticmethod
    def _extract_response_text(data: dict) -> str | None:
        """Extract user-facing response text from orchestrator payloads."""
        result = data.get("result")

        if isinstance(result, str):
            return result

        if isinstance(result, dict):
            for key in (
                "response",
                "output",
                "text",
                "message",
                "description",
            ):
                value = result.get(key)
                if isinstance(value, str) and value.strip():
                    return value

        for key in ("response", "output", "text", "message", "description"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value

        return None

    async def async_process(
        self, user_input: ConversationInput
    ) -> ConversationResult:
        text = user_input.text
        conv_id = user_input.conversation_id or "default"

        host = self.entry.data[CONF_HOST]
        port = self.entry.data[CONF_PORT]
        url = f"http://{host}:{port}/orchestrator/run-agent"

        payload = {
            "agent_name": "router",
            "payload": {
                "message": text,
                "conversation_id": conv_id,
            },
        }

        _LOGGER.debug("Sending to orchestrator at %s: %s", url, payload)

        try:
            timeout = aiohttp.ClientTimeout(total=75)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status != 200:
                        _LOGGER.error(
                            "Orchestrator returned HTTP %s", resp.status
                        )

                        intent = IntentResponse(language="en")
                        intent.async_set_speech(
                            "I had trouble contacting the orchestrator."
                        )

                        return ConversationResult(
                            response=intent,
                            conversation_id=conv_id,
                        )

                    data = await resp.json()
                    _LOGGER.debug("Received from orchestrator: %s", data)

                    response_text = self._extract_response_text(data)
                    if response_text is None:
                        _LOGGER.debug(
                            "No conversational response text found in payload keys"
                        )
                        response_text = (
                            "I didn't get a response from the orchestrator."
                        )

                    intent = IntentResponse(language="en")
                    intent.async_set_speech(response_text)

                    return ConversationResult(
                        response=intent,
                        conversation_id=conv_id,
                    )

        except (TimeoutError, asyncio.TimeoutError):
            _LOGGER.error("Orchestrator request timed out")

            intent = IntentResponse(language="en")
            intent.async_set_speech(
                "The orchestrator is taking too long to respond. Please try again."
            )

            return ConversationResult(
                response=intent,
                conversation_id=conv_id,
            )

        except Exception as e:
            _LOGGER.exception("Error calling orchestrator: %s", e)

            intent = IntentResponse(language="en")
            intent.async_set_speech(
                "Something went wrong talking to the orchestrator."
            )

            return ConversationResult(
                response=intent,
                conversation_id=conv_id,
            )
