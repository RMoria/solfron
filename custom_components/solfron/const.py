"""Constants for the Solar Frontier integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import SolfronRuntimeData

DOMAIN = "solfron"

MANUFACTURER = "Solar Frontier"

DEFAULT_NAME = "Solar Frontier Inverter"

# Options keys (CONF_HOST, CONF_MAC and CONF_SCAN_INTERVAL come from
# homeassistant.const).
CONF_IP_CHECK_INTERVAL = "ip_check_interval"
CONF_CLOCK_CHECK_INTERVAL = "clock_check_interval"

# Defaults, in seconds.
DEFAULT_SCAN_INTERVAL = 60  # measurements / yields
DEFAULT_IP_CHECK_INTERVAL = 3600  # ARP-based IP<->MAC re-check
DEFAULT_CLOCK_CHECK_INTERVAL = 86400  # LCD clock / time-difference check

type SolfronConfigEntry = ConfigEntry[SolfronRuntimeData]
