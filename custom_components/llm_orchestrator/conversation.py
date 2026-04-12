# =====================================================================
# FILE: custom_components/llm_orchestrator/conversation.py
# =====================================================================

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.conversation import async_set_agent
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .conversation_agent import LLMOrchestratorConversationAgent

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    _async_add_entities: Any = None,
) -> bool:
    """Set up the conversation agent."""
    _LOGGER.debug(
        "Setting up conversation agent for entry %s (add_entities=%s)",
        entry.entry_id,
        _async_add_entities is not None,
    )

    agent = LLMOrchestratorConversationAgent(hass, entry)
    async_set_agent(hass, entry.entry_id, agent)

    _LOGGER.debug("LLM Orchestrator conversation agent registered")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the conversation agent."""
    _LOGGER.debug("Unloading conversation agent for entry %s", entry.entry_id)

    hass.components.conversation.async_unset_agent(entry.entry_id)

    _LOGGER.debug("LLM Orchestrator conversation agent unregistered")

    return True
