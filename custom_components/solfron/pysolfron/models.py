"""Data models for pysolfron."""

from dataclasses import dataclass, field


@dataclass(slots=True)
class Measurements:
    dc_power: float = 0.0
    dc_voltage: float = 0.0
    dc_current: float = 0.0
    ac_power: float = 0.0
    ac_voltage: float = 0.0
    ac_current: float = 0.0
    frequency: float = 0.0


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
