"""Data models for pysolfron."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class Measurements:
    # Single-phase / aggregate values (present on single-phase inverters such
    # as the SF-WR-3000).
    dc_power: float = 0.0
    dc_voltage: float = 0.0
    dc_current: float = 0.0
    ac_power: float = 0.0
    ac_voltage: float = 0.0
    ac_current: float = 0.0
    frequency: float = 0.0

    # Per-phase values (present on three-phase inverters, e.g. the SF-WR-5503x
    # series). Left as None when the inverter does not report them, so the
    # integration can auto-detect single- vs three-phase.
    ac_voltage_l1: float | None = None
    ac_voltage_l2: float | None = None
    ac_voltage_l3: float | None = None
    ac_current_l1: float | None = None
    ac_current_l2: float | None = None
    ac_current_l3: float | None = None
    ac_power_l1: float | None = None
    ac_power_l2: float | None = None
    ac_power_l3: float | None = None
    frequency_l1: float | None = None
    frequency_l2: float | None = None
    frequency_l3: float | None = None


@dataclass(slots=True)
class YieldData:
    today: float = 0.0
    month: float = 0.0
    year: float = 0.0
    total: float = 0.0


@dataclass(slots=True)
class DeviceInfo:
    model: str = ""
    serial: str = ""
    firmware: str = ""
    hardware: str = ""
    mac: str = ""


@dataclass(slots=True)
class Device:
    ip: str = ""
    online: bool = False

    measurements: Measurements = field(default_factory=Measurements)
    yield_data: YieldData = field(default_factory=YieldData)
    info: DeviceInfo = field(default_factory=DeviceInfo)
