"""Async API client for the external orchestrator service."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_TIMEOUT


class OrchestratorApiClient:
    """Client for communicating with the external orchestrator API."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self._session = async_get_clientsession(hass)
        self._base_url = f"http://{host}:{port}"
        self._timeout = timeout

    async def async_send(self, agent: str, message: str) -> dict[str, Any]:
        """Send a message to the orchestrator and return JSON response."""
        url = f"{self._base_url}/orchestrator/run-agent"
        payload = {
            "agent_name": agent,
            "payload": {"input": message},
        }

        try:
            timeout = aiohttp.ClientTimeout(total=self._timeout)
            async with self._session.post(
                url,
                json=payload,
                timeout=timeout,
            ) as response:
                if response.status >= 400:
                    body = await response.text()
                    raise HomeAssistantError(f"Request failed: {response.status} {body}")

                data = await response.json(content_type=None)

                if isinstance(data, dict):
                    return data

                return {"result": data}
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise HomeAssistantError(
                f"Unable to reach orchestrator at {self._base_url}"
            ) from err
