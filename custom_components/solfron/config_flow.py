"""Config flow for the Solar Frontier integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_SCAN_INTERVAL
from homeassistant.core import callback

from .const import (
    CONF_CLOCK_CHECK_INTERVAL,
    CONF_IP_CHECK_INTERVAL,
    DEFAULT_CLOCK_CHECK_INTERVAL,
    DEFAULT_IP_CHECK_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SolfronConfigEntry,
)
from .pysolfron import SolfronClient
from .pysolfron.discovery import find_mac
from .pysolfron.exceptions import DiscoveryError, SolfronError

_LOGGER = logging.getLogger(__name__)


class SolfronConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Solar Frontier."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            client = SolfronClient(host)

            try:
                await self.hass.async_add_executor_job(client.get_device)
            except SolfronError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error connecting to inverter")
                errors["base"] = "unknown"
            else:
                # MAC is the leading identifier. Resolve it from the ARP table
                # now that we have just contacted the inverter (best effort).
                mac = ""
                try:
                    mac = await self.hass.async_add_executor_job(find_mac, host)
                except DiscoveryError:
                    _LOGGER.warning(
                        "Could not determine MAC for %s via ARP; "
                        "falling back to host as identifier",
                        host,
                    )

                await self.async_set_unique_id(mac or host)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data={CONF_HOST: host, CONF_MAC: mac},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: SolfronConfigEntry,
    ) -> SolfronOptionsFlow:
        """Return the options flow."""
        return SolfronOptionsFlow()


class SolfronOptionsFlow(OptionsFlow):
    """Handle Solar Frontier options.

    No ``__init__`` and no ``self.config_entry`` assignment: the base class
    provides ``self.config_entry`` (required since HA 2025.12).
    """

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Manage the options."""

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
                vol.Optional(
                    CONF_IP_CHECK_INTERVAL,
                    default=options.get(
                        CONF_IP_CHECK_INTERVAL, DEFAULT_IP_CHECK_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=300, max=86400)),
                vol.Optional(
                    CONF_CLOCK_CHECK_INTERVAL,
                    default=options.get(
                        CONF_CLOCK_CHECK_INTERVAL, DEFAULT_CLOCK_CHECK_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=3600, max=604800)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
