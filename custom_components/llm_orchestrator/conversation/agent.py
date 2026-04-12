import logging
import aiohttp
import inspect

from homeassistant.components.conversation import (
    AbstractConversationAgent,
    ConversationInput,
    ConversationResult,
)
from homeassistant.components.conversation import models as conv_models

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from ..const import CONF_HOST, CONF_PORT

_LOGGER = logging.getLogger(__name__)


class LLMOrchestratorConversationAgent(AbstractConversationAgent):
    """Conversation agent that routes all messages through the orchestrator router."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry

        # ⭐ Log available conversation model classes at startup
        try:
            model_attrs = dir(conv_models)
            _LOGGER.warning("Conversation models module attributes: %s", model_attrs)

            classes = [
                (name, getattr(conv_models, name))
                for name in model_attrs
                if isinstance(getattr(conv_models, name), type)
            ]
            for name, cls in classes:
                _LOGGER.warning("Conversation model class: %s -> %s", name, cls)

                # Try to inspect constructor signature
                try:
                    sig = inspect.signature(cls)
                    _LOGGER.warning("Constructor for %s: %s", name, sig)
                except Exception:
                    pass

        except Exception as e:
            _LOGGER.error("Error introspecting conversation models: %s", e)

    @property
    def attribution(self):
        return {"name": "LLM Orchestrator"}

    @property
    def supported_languages(self) -> list[str]:
        return ["en"]

    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
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
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status != 200:
                        _LOGGER.error("Orchestrator returned HTTP %s", resp.status)

                        result = ConversationResult(
                            response={
                                "speech": {
                                    "plain": {
                                        "speech": "I had trouble contacting the orchestrator.",
                                        "extra_data": {},
                                    }
                                }
                            }
                        )

                        _LOGGER.warning("ConversationResult object (error case): %s", result)
                        return result

                    data = await resp.json()
                    _LOGGER.debug("Received from orchestrator: %s", data)

                    response_text = (
                        data.get("result", {}).get("response")
                        or "I didn't get a response from the orchestrator."
                    )

                    result = ConversationResult(
                        response={
                            "speech": {
                                "plain": {
                                    "speech": response_text,
                                    "extra_data": {},
                                }
                            }
                        }
                    )

                    # ⭐ Log the actual ConversationResult object HA will receive
                    _LOGGER.warning("ConversationResult object (normal case): %s", result)

                    return result

        except Exception as e:
            _LOGGER.exception("Error calling orchestrator: %s", e)

            result = ConversationResult(
                response={
                    "speech": {
                        "plain": {
                            "speech": "Something went wrong talking to the orchestrator.",
                            "extra_data": {},
                        }
                    }
                }
            )

            _LOGGER.warning("ConversationResult object (exception case): %s", result)
            return result
