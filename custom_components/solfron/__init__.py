"""The Solar Frontier integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.const import CONF_HOST, CONF_MAC, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    CONF_IP_CHECK_INTERVAL,
    DEFAULT_IP_CHECK_INTERVAL,
    SolfronConfigEntry,
)
from .coordinator import (
    SolfronClockCoordinator,
    SolfronDataUpdateCoordinator,
    SolfronRuntimeData,
)
from .pysolfron import SolfronClient
from .pysolfron.discovery import find_ip, verify_ip
from .pysolfron.exceptions import DiscoveryError

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolfronConfigEntry,
) -> bool:
    """Set up Solar Frontier from a config entry."""

    client = SolfronClient(entry.data[CONF_HOST])

    data_coordinator = SolfronDataUpdateCoordinator(hass, entry, client)
    clock_coordinator = SolfronClockCoordinator(hass, entry, client)

    await data_coordinator.async_config_entry_first_refresh()
    # The clock check is optional; don't block setup if it can't be read.
    await clock_coordinator.async_refresh()

    entry.runtime_data = SolfronRuntimeData(
        data=data_coordinator,
        clock=clock_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload the entry when its options (or data, e.g. a refreshed IP) change.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Periodically re-check that the stored IP still belongs to the stored MAC,
    # and recover a new IP from the ARP table if it changed (non-static DHCP).
    if entry.data.get(CONF_MAC):
        ip_check_interval = timedelta(
            seconds=entry.options.get(
                CONF_IP_CHECK_INTERVAL, DEFAULT_IP_CHECK_INTERVAL
            )
        )
        entry.async_on_unload(
            async_track_time_interval(
                hass,
                _make_ip_check(hass, entry),
                ip_check_interval,
            )
        )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: SolfronConfigEntry,
) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant,
    entry: SolfronConfigEntry,
) -> None:
    """Reload the entry when options or data change."""

    await hass.config_entries.async_reload(entry.entry_id)


def _make_ip_check(hass: HomeAssistant, entry: SolfronConfigEntry):
    """Build the periodic ARP-based IP/MAC verification callback."""

    async def _check(now: datetime) -> None:
        mac = entry.data[CONF_MAC]
        current_ip = entry.data[CONF_HOST]

        try:
            if await hass.async_add_executor_job(verify_ip, current_ip, mac):
                return
            new_ip = await hass.async_add_executor_job(find_ip, mac)
        except DiscoveryError:
            _LOGGER.debug(
                "Could not verify/resolve inverter IP for MAC %s via ARP", mac
            )
            return

        if new_ip and new_ip != current_ip:
            _LOGGER.info(
                "Solar Frontier inverter IP changed %s -> %s (MAC %s)",
                current_ip,
                new_ip,
                mac,
            )
            # Updating the entry data triggers _async_update_listener, which
            # reloads the entry so the coordinator reconnects to the new IP.
            hass.config_entries.async_update_entry(
                entry,
                data={**entry.data, CONF_HOST: new_ip},
            )

    return _check
