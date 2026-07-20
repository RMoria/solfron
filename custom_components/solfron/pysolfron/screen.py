"""
Decode the date/time shown on the inverter's LCD screenshot.

The inverter serves ``gen.screenshot.bmp``: a 128x64, 1-bit, uncompressed
Windows bitmap that mirrors the physical LCD. The status bar at the bottom
renders a clock:

* bottom-right: the current time ``HH:MM`` (24-hour) -- always present;
* bottom-left: alternates between the date (``DD.MM.YYYY``) and the IP address
  (e.g. ``192.168.1.50``, preceded by a small network icon).

This module parses the bitmap and decodes that clock using pure Python (no
Pillow / OCR dependency), so it is safe to ship in a custom integration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import struct

from .exceptions import InvalidResponseError

# Canonical 3-wide x 5-tall templates for the LCD digit font. "1" is rendered
# two columns wide and is left-aligned into the 3-wide grid.
_DIGIT_TEMPLATES: dict[str, tuple[str, ...]] = {
    "0": ("###", "#.#", "#.#", "#.#", "###"),
    "1": (".#.", "##.", ".#.", ".#.", ".#."),
    "2": ("###", "..#", "###", "#..", "###"),
    "3": ("###", "..#", "###", "..#", "###"),
    "4": ("#.#", "#.#", "###", "..#", "..#"),
    "5": ("###", "#..", "###", "..#", "###"),
    "6": ("###", "#..", "###", "#.#", "###"),
    "7": ("###", "..#", "..#", "..#", "..#"),
    "8": ("###", "#.#", "###", "#.#", "###"),
    "9": ("###", "#.#", "###", "..#", "###"),
}

# Text band (rows) of the bottom status bar and the x-ranges of the left
# (date / IP) and right (time) fields.
_BAND_TOP = 57
_BAND_BOTTOM = 61  # inclusive
_LEFT_X = (0, 60)
_TIME_X = (100, 127)


@dataclass(frozen=True)
class ScreenClock:
    """The clock decoded from the inverter's LCD screenshot."""

    hour: int
    minute: int
    day: int | None = None
    month: int | None = None
    year: int | None = None
    ip: str | None = None


def _parse_bmp(data: bytes) -> list[list[bool]]:
    """Parse a 1-bit uncompressed BMP into a top-down grid of ink booleans."""

    if data[:2] != b"BM":
        raise InvalidResponseError("Not a BMP file")

    pixel_offset = struct.unpack("<I", data[10:14])[0]
    width = struct.unpack("<i", data[18:22])[0]
    height = struct.unpack("<i", data[22:26])[0]
    bpp = struct.unpack("<H", data[28:30])[0]
    compression = struct.unpack("<I", data[30:34])[0]

    if bpp != 1 or compression != 0:
        raise InvalidResponseError(
            f"Unsupported BMP format (bpp={bpp}, compression={compression})"
        )

    # Two-entry palette (BGRA); decide which index is the darker "ink" colour.
    pal0 = data[54:57]
    pal1 = data[58:61]
    lum0 = sum(pal0) if len(pal0) == 3 else 0
    lum1 = sum(pal1) if len(pal1) == 3 else 765
    ink_index = 0 if lum0 <= lum1 else 1

    bottom_up = height > 0
    height = abs(height)
    row_bytes = ((width + 31) // 32) * 4  # rows padded to 4-byte boundary

    grid: list[list[bool]] = []
    for row in range(height):
        src = height - 1 - row if bottom_up else row
        start = pixel_offset + src * row_bytes
        line = data[start : start + row_bytes]
        pixels = [
            ((line[x // 8] >> (7 - (x % 8))) & 1) == ink_index
            for x in range(width)
        ]
        grid.append(pixels)

    return grid


def _segment(grid: list[list[bool]], x0: int, x1: int) -> list[tuple[int, int]]:
    """Return (start, end) column ranges containing ink within [x0, x1]."""

    width = len(grid[0])
    x1 = min(x1, width - 1)
    col_has_ink = [
        any(grid[y][x] for y in range(_BAND_TOP, _BAND_BOTTOM + 1))
        for x in range(width)
    ]

    groups: list[tuple[int, int]] = []
    x = x0
    while x <= x1:
        if col_has_ink[x]:
            start = x
            while x <= x1 and col_has_ink[x]:
                x += 1
            groups.append((start, x - 1))
        else:
            x += 1
    return groups


def _match_digit(grid: list[list[bool]], start: int, end: int) -> str | None:
    """Classify a glyph column-group as a digit, or None otherwise.

    Returns None for separators (".", ":") and non-digit glyphs (e.g. the
    network icon), which are wider or narrower than a digit or match no
    template closely enough.
    """

    glyph_w = end - start + 1
    if glyph_w < 2 or glyph_w > 3:
        return None

    rows: list[str] = []
    for y in range(_BAND_TOP, _BAND_BOTTOM + 1):
        cells = ["#" if grid[y][start + c] else "." for c in range(glyph_w)]
        while len(cells) < 3:
            cells.append(".")
        rows.append("".join(cells))
    candidate = tuple(rows)

    best_digit: str | None = None
    best_score = 99
    for digit, template in _DIGIT_TEMPLATES.items():
        score = sum(
            candidate[r][c] != template[r][c] for r in range(5) for c in range(3)
        )
        if score < best_score:
            best_score = score
            best_digit = digit

    return best_digit if best_score <= 3 else None


def _tokens(grid: list[list[bool]], x0: int, x1: int) -> list[str]:
    """Split a field into numeric tokens, separated by "." / ":" separators."""

    tokens: list[str] = []
    current = ""
    for start, end in _segment(grid, x0, x1):
        digit = _match_digit(grid, start, end)
        width = end - start + 1
        if digit is not None:
            current += digit
        elif width == 1:  # a separator: end the current token
            if current:
                tokens.append(current)
                current = ""
        # wider non-digit glyphs (icon) are ignored without splitting
    if current:
        tokens.append(current)
    return tokens


def decode_screen(data: bytes) -> ScreenClock:
    """Decode the clock (and any shown IP/date) from ``gen.screenshot.bmp``."""

    grid = _parse_bmp(data)
    if len(grid) <= _BAND_BOTTOM:
        raise InvalidResponseError("Screenshot smaller than expected")

    time_tokens = _tokens(grid, *_TIME_X)
    if len(time_tokens) != 2 or len(time_tokens[0]) != 2 or len(time_tokens[1]) != 2:
        raise InvalidResponseError(f"Could not read time (tokens={time_tokens})")

    try:
        hour = int(time_tokens[0])
        minute = int(time_tokens[1])
    except ValueError as err:
        raise InvalidResponseError(f"Invalid time: {err}") from err

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise InvalidResponseError(f"Time out of range: {hour}:{minute}")

    day = month = year = None
    ip = None
    left = _tokens(grid, *_LEFT_X)

    if len(left) == 3 and [len(t) for t in left] == [2, 2, 4]:
        # Date field: DD.MM.YYYY
        try:
            day, month, year = int(left[0]), int(left[1]), int(left[2])
        except ValueError:
            day = month = year = None
    elif len(left) == 4:
        # IP address field
        ip = ".".join(left)

    return ScreenClock(
        hour=hour, minute=minute, day=day, month=month, year=year, ip=ip
    )


def clock_to_datetime(clock: ScreenClock, reference: datetime) -> datetime:
    """Turn a decoded ``ScreenClock`` into a naive local datetime.

    ``reference`` is the current local time (naive). When the screenshot shows
    the date it is used directly; otherwise the reference date is combined with
    the decoded time, correcting for a midnight wrap so the result stays within
    +/- 12h of the reference.
    """

    if clock.day and clock.month and clock.year:
        try:
            return datetime(
                clock.year, clock.month, clock.day, clock.hour, clock.minute
            )
        except ValueError as err:
            raise InvalidResponseError(f"Invalid date/time: {err}") from err

    candidate = reference.replace(
        hour=clock.hour, minute=clock.minute, second=0, microsecond=0
    )

    # Correct for the case where inverter and reference straddle midnight.
    if candidate - reference > timedelta(hours=12):
        candidate -= timedelta(days=1)
    elif reference - candidate > timedelta(hours=12):
        candidate += timedelta(days=1)

    return candidate


def screen_datetime(data: bytes, reference: datetime) -> datetime:
    """Decode ``gen.screenshot.bmp`` and return the inverter clock as a
    naive local datetime (see :func:`clock_to_datetime`)."""

    return clock_to_datetime(decode_screen(data), reference)
