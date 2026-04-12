# =====================================================================
# FILE: custom_components/llm_orchestrator/__init__.py
# =====================================================================

"""The LLM Orchestrator integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .api import OrchestratorApiClient
from .const import CONF_HOST, CONF_PORT, DOMAIN
from .services import async_register_services, async_unregister_services


async def async_setup(_hass: HomeAssistant, _config: dict[str, Any]) -> bool:
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

    await async_register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    domain_data = hass.data.get(DOMAIN, {})
    domain_data.pop(entry.entry_id, None)

    if not domain_data:
        await async_unregister_services(hass)
        hass.data.pop(DOMAIN, None)

    return True
