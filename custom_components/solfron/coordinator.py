"""Data update coordinators for the Solar Frontier integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import logging

from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CLOCK_CHECK_INTERVAL,
    DEFAULT_CLOCK_CHECK_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    SolfronConfigEntry,
)
from .pysolfron import Device, SolfronClient
from .pysolfron.exceptions import SolfronError
from .pysolfron.screen import clock_to_datetime

_LOGGER = logging.getLogger(__name__)


# The LCD alternates the bottom-left field between date and IP roughly every
# 5 seconds, so retry a few times to catch the date; the time is always shown.
_CLOCK_ATTEMPTS = 5
_CLOCK_RETRY_DELAY = 2.0  # seconds


@dataclass
class ClockStatus:
    """Result of a clock (time-difference) check."""

    inverter_time: datetime  # naive, inverter local time
    offset: timedelta  # inverter_time - Home Assistant local time
    inverter_date: date | None  # decoded date, if captured this run
    date_ok: bool | None  # whether the decoded date matches HA's date
    reported_ip: str | None  # IP shown on the LCD, if any


@dataclass
class SolfronRuntimeData:
    """Runtime data stored on the config entry."""

    data: SolfronDataUpdateCoordinator
    clock: SolfronClockCoordinator


class SolfronDataUpdateCoordinator(DataUpdateCoordinator[Device]):
    """Coordinator for the inverter measurements and yields."""

    config_entry: SolfronConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SolfronConfigEntry,
        client: SolfronClient,
    ) -> None:
        """Initialize the coordinator."""

        self.client = client

        scan_interval = entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self) -> Device:
        """Fetch data from the inverter."""

        try:
            return await self.hass.async_add_executor_job(self.client.get_device)
        except SolfronError as err:
            raise UpdateFailed(
                f"Error communicating with inverter: {err}"
            ) from err


class SolfronClockCoordinator(DataUpdateCoordinator[ClockStatus]):
    """Coordinator that checks the inverter clock against Home Assistant.

    A large offset (e.g. after a DST transition) can put the inverter into a
    fault state, so this is polled slowly (daily by default).
    """

    config_entry: SolfronConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: SolfronConfigEntry,
        client: SolfronClient,
    ) -> None:
        """Initialize the clock coordinator."""

        self.client = client

        interval = entry.options.get(
            CONF_CLOCK_CHECK_INTERVAL, DEFAULT_CLOCK_CHECK_INTERVAL
        )

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_clock",
            config_entry=entry,
            update_interval=timedelta(seconds=interval),
        )

    async def _async_update_data(self) -> ClockStatus:
        """Read and evaluate the inverter clock.

        The time is always shown; the date is only shown part of the time (it
        alternates with the IP), so retry until a date is captured.
        """

        latest = None  # most recent read (for the time)
        dated = None  # a read that included the date
        for attempt in range(_CLOCK_ATTEMPTS):
            try:
                clock = await self.hass.async_add_executor_job(
                    self.client.get_screen_clock
                )
            except SolfronError as err:
                if latest is None:
                    raise UpdateFailed(
                        f"Error reading inverter clock: {err}"
                    ) from err
                break

            latest = clock
            if clock.day:
                dated = clock
                break
            if attempt < _CLOCK_ATTEMPTS - 1:
                await asyncio.sleep(_CLOCK_RETRY_DELAY)

        chosen = dated or latest
        now = dt_util.now().replace(tzinfo=None)
        inverter_time = clock_to_datetime(chosen, now)

        inverter_date = None
        date_ok = None
        if dated is not None:
            inverter_date = date(dated.year, dated.month, dated.day)
            date_ok = inverter_date == now.date()

        return ClockStatus(
            inverter_time=inverter_time,
            offset=inverter_time - now,
            inverter_date=inverter_date,
            date_ok=date_ok,
            reported_ip=(latest.ip if latest else None),
        )
