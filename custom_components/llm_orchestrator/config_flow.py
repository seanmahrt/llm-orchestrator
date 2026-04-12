"""Config flow for the LLM Orchestrator integration."""

from __future__ import annotations

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_HOST, CONF_PORT, DEFAULT_PORT, DOMAIN


class LlmOrchestratorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for LLM Orchestrator."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = int(user_input[CONF_PORT])

            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            can_connect = await self._async_validate_connectivity(host, port)
            if not can_connect:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"{host}:{port}",
                    data={CONF_HOST: host, CONF_PORT: port},
                )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def _async_validate_connectivity(self, host: str, port: int) -> bool:
        """Validate that the configured host/port is reachable."""
        url = f"http://{host}:{port}"
        timeout = aiohttp.ClientTimeout(total=5)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    return response.status < 500
        except aiohttp.ClientError:
            return False
