"""
Parser functions for Solar Frontier inverter pages.
"""

from __future__ import annotations

import re

from .models import DeviceInfo, Measurements


_TABLE_RE = re.compile(r'document\.write\("(.*)"\);', re.DOTALL)
_ROW_RE = re.compile(r"<tr.*?>(.*?)</tr>", re.IGNORECASE)
_CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


MEASUREMENT_FIELDS = {
    # Single-phase / aggregate rows.
    "P DC": "dc_power",
    "U DC": "dc_voltage",
    "I DC": "dc_current",
    "P AC": "ac_power",
    "U AC": "ac_voltage",
    "I AC": "ac_current",
    "F AC": "frequency",
    # Per-phase rows (three-phase inverters). Only set when the row is present.
    "U AC1": "ac_voltage_l1",
    "U AC2": "ac_voltage_l2",
    "U AC3": "ac_voltage_l3",
    "I AC1": "ac_current_l1",
    "I AC2": "ac_current_l2",
    "I AC3": "ac_current_l3",
    "P AC1": "ac_power_l1",
    "P AC2": "ac_power_l2",
    "P AC3": "ac_power_l3",
    "F AC1": "frequency_l1",
    "F AC2": "frequency_l2",
    "F AC3": "frequency_l3",
}


DEVICE_FIELDS = {
    "Name": "model",
    "Serial": "serial",
    "Firmware": "firmware",
    "Hardware": "hardware",
    "MAC": "mac",
}


def _extract_html(js: str) -> str:
    """Extract HTML from document.write()."""

    match = _TABLE_RE.search(js)

    if not match:
        return js

    return match.group(1).replace(r"\"", '"').replace(r"\'", "'")


def _rows(js: str) -> list[list[str]]:
    """Return table rows."""

    html = _extract_html(js)
    rows: list[list[str]] = []

    for row in _ROW_RE.findall(html):
        cells = [
            _TAG_RE.sub("", cell).replace("&nbsp;", " ").strip()
            for cell in _CELL_RE.findall(row)
        ]

        if cells:
            rows.append(cells)

    return rows


def _to_float(value: str) -> float:
    """Convert string to float."""

    value = value.strip().replace(",", ".")

    if value in ("", "---"):
        return 0.0

    try:
        return float(value)
    except ValueError:
        return 0.0


def _sum_table(js: str) -> float:
    """Return the sum of the second column."""

    return round(
        sum(_to_float(row[1]) for row in _rows(js) if len(row) >= 2),
        3,
    )


def parse_measurements(js: str) -> Measurements:
    """Parse measurement table."""

    data = Measurements()

    for row in _rows(js):
        if len(row) < 2:
            continue

        field = MEASUREMENT_FIELDS.get(row[0])
        if field:
            setattr(data, field, _to_float(row[1]))

    return data


def parse_device_info(js: str) -> DeviceInfo:
    """Parse device information."""

    info = DeviceInfo()

    for row in _rows(js):
        if len(row) < 2:
            continue

        field = DEVICE_FIELDS.get(row[0])
        if field:
            setattr(info, field, row[1])

    return info


def parse_today_yield(js: str) -> float:
    """Return today's yield in kWh."""

    match = re.search(
        r'labelValueId"\)\.innerHTML\s*=\s*"\s*([0-9.]+)\s*kWh',
        js,
        re.IGNORECASE,
    )

    return _to_float(match.group(1)) if match else 0.0


def parse_month_yield(js: str) -> float:
    """Return this month's yield in kWh (sum of the daily values)."""

    return _sum_table(js)


def parse_year_yield(js: str) -> float:
    """Return this year's yield in kWh (sum of the monthly values)."""

    return _sum_table(js)


def parse_total_yield(js: str) -> float:
    """Return lifetime yield in kWh.

    The total table lists yearly totals in MWh, so the summed value is
    converted to kWh.
    """

    return round(_sum_table(js) * 1000.0, 3)
