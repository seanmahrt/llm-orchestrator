"""Service handlers for the LLM Orchestrator integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .api import OrchestratorApiClient
from .const import DEFAULT_AGENT, DOMAIN, EVENT_RESPONSE, SERVICE_SEND

SERVICE_SEND_SCHEMA = vol.Schema(
    {
        vol.Required("message"): cv.string,
        vol.Optional("agent", default=DEFAULT_AGENT): cv.string,
    }
)


async def async_register_services(hass: HomeAssistant) -> None:
    """Register domain services."""
    if hass.services.has_service(DOMAIN, SERVICE_SEND):
        return

    async def _handle_send(call: ServiceCall) -> dict[str, Any]:
        domain_data = hass.data.get(DOMAIN)
        if not domain_data:
            raise HomeAssistantError(
                "No configured LLM Orchestrator entry found"
            )

        client: OrchestratorApiClient = next(iter(domain_data.values()))
        agent = call.data["agent"]
        message = call.data["message"]

        result = await client.async_send(agent=agent, message=message)

        hass.bus.async_fire(
            EVENT_RESPONSE,
            {
                "agent": agent,
                "message": message,
                "result": result,
            },
        )

        return result

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND,
        _handle_send,
        schema=SERVICE_SEND_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


async def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister domain services."""
    if hass.services.has_service(DOMAIN, SERVICE_SEND):
        hass.services.async_remove(DOMAIN, SERVICE_SEND)
