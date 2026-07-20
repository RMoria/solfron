"""
Solfron client.
"""

from __future__ import annotations

from datetime import datetime
from urllib.error import URLError
from urllib.request import urlopen

from .exceptions import SolfronConnectionError
from .models import Device, DeviceInfo, Measurements, YieldData
from .parser import (
    parse_device_info,
    parse_measurements,
    parse_month_yield,
    parse_today_yield,
    parse_total_yield,
    parse_year_yield,
)
from .screen import ScreenClock, decode_screen, screen_datetime


MEASUREMENTS_FILE = "gen.measurements.table.js"
DEVICE_INFO_FILE = "gen.info.table.sys.js"
TODAY_YIELD_FILE = "gen.yield.day.chart.js"
MONTH_YIELD_FILE = "gen.yield.month.table.js"
YEAR_YIELD_FILE = "gen.yield.year.table.js"
TOTAL_YIELD_FILE = "gen.yield.total.table.js"
SCREENSHOT_FILE = "gen.screenshot.bmp"


class SolfronClient:
    """Client for communicating with a Solar Frontier inverter."""

    def __init__(self, host: str, timeout: int = 10):
        self._host = host
        self._timeout = timeout

    @property
    def host(self) -> str:
        """Return the configured inverter hostname or IP address."""
        return self._host

    def _download_bytes(self, filename: str) -> bytes:
        """Download a file from the inverter as raw bytes."""

        url = f"http://{self._host}/{filename}"

        try:
            with urlopen(url, timeout=self._timeout) as response:
                return response.read()

        except URLError as err:
            raise SolfronConnectionError(
                f"Unable to download '{filename}' from {self._host}"
            ) from err

    def _download(self, filename: str) -> str:
        """Download a text file from the inverter."""

        return self._download_bytes(filename).decode("utf-8", errors="ignore")

    def download(self, filename: str) -> str:
        """
        Download a raw file.

        Mainly intended for testing/debugging.
        """
        return self._download(filename)

    def get_measurements(self) -> Measurements:
        """Return current inverter measurements."""
        return parse_measurements(self._download(MEASUREMENTS_FILE))

    def get_device_info(self) -> DeviceInfo:
        """Return device information."""
        return parse_device_info(self._download(DEVICE_INFO_FILE))

    def get_today_yield(self) -> float:
        """Return today's energy yield."""
        return parse_today_yield(self._download(TODAY_YIELD_FILE))

    def get_month_yield(self) -> float:
        """Return this month's energy yield."""
        return parse_month_yield(self._download(MONTH_YIELD_FILE))

    def get_year_yield(self) -> float:
        """Return this year's energy yield."""
        return parse_year_yield(self._download(YEAR_YIELD_FILE))

    def get_total_yield(self) -> float:
        """Return lifetime energy yield."""
        return parse_total_yield(self._download(TOTAL_YIELD_FILE))

    def get_screen_clock(self) -> ScreenClock:
        """Decode the clock shown on the inverter's LCD screenshot."""
        return decode_screen(self._download_bytes(SCREENSHOT_FILE))

    def get_screen_datetime(self, reference: datetime) -> datetime:
        """Return the inverter's clock as a naive local datetime.

        ``reference`` is the current local time, used to supply the date when
        the screenshot happens to show the IP address instead of the date.
        """
        return screen_datetime(
            self._download_bytes(SCREENSHOT_FILE), reference
        )

    def get_device(self) -> Device:
        """
        Download and parse all inverter information.
        """

        return Device(
            ip=self._host,
            online=True,
            measurements=self.get_measurements(),
            info=self.get_device_info(),
            yield_data=YieldData(
                today=self.get_today_yield(),
                month=self.get_month_yield(),
                year=self.get_year_yield(),
                total=self.get_total_yield(),
            ),
        )
