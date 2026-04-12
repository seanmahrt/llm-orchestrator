"""The LLM Orchestrator integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.conversation import async_set_agent

from .api import OrchestratorApiClient
from .const import CONF_HOST, CONF_PORT, DOMAIN
from .services import async_register_services, async_unregister_services
from .conversation import LLMOrchestratorConversationAgent


async def async_setup(_hass: HomeAssistant, _config: dict) -> bool:
    """Set up the integration from YAML (not used)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LLM Orchestrator from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    client = OrchestratorApiClient(
        hass=hass,
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
    )
    hass.data[DOMAIN][entry.entry_id] = client

    # Register HA services (unchanged)
    await async_register_services(hass)

    # ⭐ Register the Conversation Agent
    agent = LLMOrchestratorConversationAgent(hass)
    async_set_agent(hass, agent)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    domain_data = hass.data.get(DOMAIN, {})
    domain_data.pop(entry.entry_id, None)

    if not domain_data:
        await async_unregister_services(hass)
        hass.data.pop(DOMAIN, None)

    return True
