"""The Solar Frontier integration."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import ipaddress
import logging
import time

from homeassistant.const import CONF_HOST, CONF_MAC, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
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
from .pysolfron.discovery import find_ips, prime_arp
from .pysolfron.exceptions import DiscoveryError

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]

# Wait after probing the subnet, so ARP replies can come in.
_PRIME_SETTLE_SECONDS = 3
# Minimum time between IP recovery attempts triggered by failed updates.
_RECOVERY_COOLDOWN_SECONDS = 600


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolfronConfigEntry,
) -> bool:
    """Set up Solar Frontier from a config entry."""

    # If the inverter got a new IP (non-static DHCP), find it before the first
    # read; otherwise setup would keep failing on the old address.
    if new_host := await _async_find_new_host(hass, entry, probe=False):
        _apply_new_host(hass, entry, new_host)

    client = SolfronClient(entry.data[CONF_HOST])

    data_coordinator = SolfronDataUpdateCoordinator(hass, entry, client)
    clock_coordinator = SolfronClockCoordinator(hass, entry, client)

    try:
        await data_coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        # Not reachable: actively look for the MAC on the subnet. If it moved,
        # store the new IP; Home Assistant retries setup with it shortly.
        if new_host := await _async_find_new_host(hass, entry, probe=True):
            _apply_new_host(hass, entry, new_host)
        raise

    # The clock check is optional; don't block setup if it can't be read.
    await clock_coordinator.async_refresh()

    entry.runtime_data = SolfronRuntimeData(
        data=data_coordinator,
        clock=clock_coordinator,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload the entry when its options (or data, e.g. a refreshed IP) change.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    if entry.data.get(CONF_MAC):
        # Periodic check (default hourly) that the IP still belongs to the MAC.
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
        # Also check right away when updates start failing.
        entry.async_on_unload(
            data_coordinator.async_add_listener(
                _make_failure_watcher(hass, entry, data_coordinator)
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


def _is_ipv4(host: str) -> bool:
    """Return True if host is an IPv4 address (not a hostname)."""

    try:
        ipaddress.IPv4Address(host)
    except ValueError:
        return False
    return True


async def _async_find_new_host(
    hass: HomeAssistant,
    entry: SolfronConfigEntry,
    *,
    probe: bool,
) -> str | None:
    """Return the inverter's new IP if its MAC moved to another address.

    Returns None when there is no MAC, the host is a hostname, the MAC is
    still at the stored IP, or the MAC can't be found.
    """

    mac = entry.data.get(CONF_MAC)
    host = entry.data[CONF_HOST]

    if not mac or not _is_ipv4(host):
        return None

    try:
        ips = await hass.async_add_executor_job(find_ips, mac)
        if host not in ips and probe:
            await hass.async_add_executor_job(prime_arp, host)
            await asyncio.sleep(_PRIME_SETTLE_SECONDS)
            ips = await hass.async_add_executor_job(find_ips, mac)
    except (DiscoveryError, OSError) as err:
        _LOGGER.debug("Could not look up inverter MAC %s via ARP: %s", mac, err)
        return None

    if not ips or host in ips:
        return None

    return ips[0]


@callback
def _apply_new_host(
    hass: HomeAssistant,
    entry: SolfronConfigEntry,
    new_host: str,
) -> None:
    """Store a new IP for the inverter."""

    _LOGGER.warning(
        "Solar Frontier inverter moved from %s to %s (MAC %s)",
        entry.data[CONF_HOST],
        new_host,
        entry.data.get(CONF_MAC),
    )
    # Once the entry is loaded, this triggers _async_update_listener, which
    # reloads the entry so the coordinators reconnect to the new IP.
    hass.config_entries.async_update_entry(
        entry,
        data={**entry.data, CONF_HOST: new_host},
    )


def _make_ip_check(hass: HomeAssistant, entry: SolfronConfigEntry):
    """Build the periodic ARP-based IP/MAC verification callback."""

    async def _check(now: datetime) -> None:
        if new_host := await _async_find_new_host(hass, entry, probe=True):
            _apply_new_host(hass, entry, new_host)

    return _check


def _make_failure_watcher(
    hass: HomeAssistant,
    entry: SolfronConfigEntry,
    coordinator: SolfronDataUpdateCoordinator,
):
    """Build a coordinator listener that looks for a new IP after failures."""

    last_attempt = 0.0
    running = False

    async def _recover() -> None:
        nonlocal running
        try:
            if new_host := await _async_find_new_host(hass, entry, probe=True):
                _apply_new_host(hass, entry, new_host)
        finally:
            running = False

    @callback
    def _on_update() -> None:
        nonlocal last_attempt, running
        if coordinator.last_update_success or running:
            return
        now = time.monotonic()
        if now - last_attempt < _RECOVERY_COOLDOWN_SECONDS:
            return
        last_attempt = now
        running = True
        entry.async_create_background_task(
            hass, _recover(), "solfron_ip_recovery"
        )

    return _on_update
