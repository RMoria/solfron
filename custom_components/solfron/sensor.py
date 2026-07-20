"""Sensor platform for the Solar Frontier integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_MAC,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
    format_mac,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, SolfronConfigEntry
from .coordinator import SolfronClockCoordinator, SolfronDataUpdateCoordinator
from .pysolfron import Device


def _device_info(
    coordinator: SolfronDataUpdateCoordinator,
) -> tuple[str, DeviceInfo]:
    """Build the shared device identity (serial-based) and DeviceInfo."""

    serial = coordinator.data.info.serial or coordinator.data.ip

    mac = coordinator.config_entry.data.get(CONF_MAC)
    connections = (
        {(CONNECTION_NETWORK_MAC, format_mac(mac))} if mac else set()
    )

    device_info = DeviceInfo(
        identifiers={(DOMAIN, serial)},
        connections=connections,
        manufacturer=MANUFACTURER,
        model=coordinator.data.info.model or None,
        serial_number=coordinator.data.info.serial or None,
        sw_version=coordinator.data.info.firmware or None,
        hw_version=coordinator.data.info.hardware or None,
        configuration_url=(
            f"http://{coordinator.data.ip}" if coordinator.data.ip else None
        ),
        name=coordinator.data.info.model
        or coordinator.data.info.serial
        or coordinator.data.ip,
    )
    return serial, device_info


@dataclass(frozen=True, kw_only=True)
class SolfronSensorDescription(SensorEntityDescription):
    """Solar Frontier sensor description."""

    value_fn: Callable[[Device], Any]


SENSORS: tuple[SolfronSensorDescription, ...] = (
    SolfronSensorDescription(
        key="dc_power",
        translation_key="dc_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda d: d.measurements.dc_power,
    ),
    SolfronSensorDescription(
        key="dc_voltage",
        translation_key="dc_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.measurements.dc_voltage,
    ),
    SolfronSensorDescription(
        key="dc_current",
        translation_key="dc_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda d: d.measurements.dc_current,
    ),
    SolfronSensorDescription(
        key="ac_power",
        translation_key="ac_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda d: d.measurements.ac_power,
    ),
    SolfronSensorDescription(
        key="ac_voltage",
        translation_key="ac_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.measurements.ac_voltage,
    ),
    SolfronSensorDescription(
        key="ac_current",
        translation_key="ac_current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda d: d.measurements.ac_current,
    ),
    SolfronSensorDescription(
        key="frequency",
        translation_key="frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda d: d.measurements.frequency,
    ),
    SolfronSensorDescription(
        key="yield_today",
        translation_key="yield_today",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        value_fn=lambda d: d.yield_data.today,
    ),
    SolfronSensorDescription(
        key="yield_month",
        translation_key="yield_month",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=3,
        value_fn=lambda d: d.yield_data.month,
    ),
    SolfronSensorDescription(
        key="yield_year",
        translation_key="yield_year",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=3,
        value_fn=lambda d: d.yield_data.year,
    ),
    SolfronSensorDescription(
        key="yield_total",
        translation_key="yield_total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=3,
        value_fn=lambda d: d.yield_data.total,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SolfronConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Solar Frontier sensors."""

    runtime = entry.runtime_data

    entities: list[SensorEntity] = [
        SolfronSensor(runtime.data, description) for description in SENSORS
    ]
    entities.append(SolfronClockOffsetSensor(runtime.clock, runtime.data))

    async_add_entities(entities)


class SolfronSensor(
    CoordinatorEntity[SolfronDataUpdateCoordinator],
    SensorEntity,
):
    """Representation of a Solar Frontier sensor."""

    entity_description: SolfronSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SolfronDataUpdateCoordinator,
        description: SolfronSensorDescription,
    ) -> None:
        """Initialize the sensor."""

        super().__init__(coordinator)

        self.entity_description = description

        serial, device_info = _device_info(coordinator)
        self._attr_unique_id = f"{serial}_{description.key}"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> Any:
        """Return the current sensor value."""

        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""

        info = self.coordinator.data.info

        attrs: dict[str, Any] = {}

        if info.mac:
            attrs["mac_address"] = info.mac

        if self.coordinator.data.ip:
            attrs["ip_address"] = self.coordinator.data.ip

        return attrs


class SolfronClockOffsetSensor(
    CoordinatorEntity[SolfronClockCoordinator],
    SensorEntity,
):
    """Difference between the inverter clock and Home Assistant time.

    A large offset (e.g. after a DST change) can put the inverter into a fault
    state, so this can be used to alert before that happens.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "clock_offset"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_suggested_display_precision = 0
    _attr_icon = "mdi:clock-alert-outline"

    def __init__(
        self,
        coordinator: SolfronClockCoordinator,
        data_coordinator: SolfronDataUpdateCoordinator,
    ) -> None:
        """Initialize the clock offset sensor."""

        super().__init__(coordinator)

        serial, device_info = _device_info(data_coordinator)
        self._attr_unique_id = f"{serial}_clock_offset"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> int | None:
        """Return the clock offset in seconds (inverter minus Home Assistant)."""

        if self.coordinator.data is None:
            return None
        return round(self.coordinator.data.offset.total_seconds())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return supporting details about the clock check."""

        status = self.coordinator.data
        if status is None:
            return {}

        attrs: dict[str, Any] = {
            "inverter_time": status.inverter_time.isoformat(),
        }
        if status.inverter_date is not None:
            attrs["inverter_date"] = status.inverter_date.isoformat()
            attrs["date_ok"] = status.date_ok
        if status.reported_ip:
            attrs["reported_ip"] = status.reported_ip

        return attrs
