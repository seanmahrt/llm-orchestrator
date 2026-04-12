# =====================================================================
# FILE: custom_components/llm_orchestrator/conversation.py
# =====================================================================

from __future__ import annotations

import logging

from homeassistant.components.conversation import async_set_agent
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .conversation.agent import LLMOrchestratorConversationAgent
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the conversation agent."""
    agent = LLMOrchestratorConversationAgent(hass, entry)
    async_set_agent(hass, entry.entry_id, agent)

    _LOGGER.debug("LLM Orchestrator conversation agent registered")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the conversation agent."""
    hass.components.conversation.async_unset_agent(entry.entry_id)

    _LOGGER.debug("LLM Orchestrator conversation agent unregistered")

    return True
