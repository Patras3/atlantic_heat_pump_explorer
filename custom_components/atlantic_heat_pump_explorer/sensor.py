"""Sensor platform for Atlantic Heat Pump Explorer."""
from __future__ import annotations

import json
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER
from .coordinator import AtlanticDataCoordinator, DeviceData

# Mapping of state names to sensor configurations
STATE_SENSOR_CONFIG: dict[str, dict[str, Any]] = {
    # Temperature states
    "core:TemperatureState": {
        "device_class": SensorDeviceClass.TEMPERATURE,
        "unit": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "core:TargetTemperatureState": {
        "device_class": SensorDeviceClass.TEMPERATURE,
        "unit": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "core:ComfortTargetDHWTemperatureState": {
        "device_class": SensorDeviceClass.TEMPERATURE,
        "unit": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "core:EcoTargetDHWTemperatureState": {
        "device_class": SensorDeviceClass.TEMPERATURE,
        "unit": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "core:TargetDHWTemperatureState": {
        "device_class": SensorDeviceClass.TEMPERATURE,
        "unit": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "core:WaterTemperatureState": {
        "device_class": SensorDeviceClass.TEMPERATURE,
        "unit": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "core:OutdoorTemperatureState": {
        "device_class": SensorDeviceClass.TEMPERATURE,
        "unit": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "io:MiddleWaterTemperatureState": {
        "device_class": SensorDeviceClass.TEMPERATURE,
        "unit": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "io:OutletWaterTemperatureState": {
        "device_class": SensorDeviceClass.TEMPERATURE,
        "unit": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "io:InletWaterTemperatureState": {
        "device_class": SensorDeviceClass.TEMPERATURE,
        "unit": UnitOfTemperature.CELSIUS,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    # Power/Energy states
    "core:ElectricPowerConsumptionState": {
        "device_class": SensorDeviceClass.POWER,
        "unit": UnitOfPower.WATT,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "core:ElectricEnergyConsumptionState": {
        "device_class": SensorDeviceClass.ENERGY,
        "unit": UnitOfEnergy.WATT_HOUR,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "io:ElectricBoosterOperatingTimeState": {
        "device_class": SensorDeviceClass.DURATION,
        "unit": UnitOfTime.HOURS,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "io:HeatPumpOperatingTimeState": {
        "device_class": SensorDeviceClass.DURATION,
        "unit": UnitOfTime.HOURS,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    # Percentage states
    "core:RelativeHumidityState": {
        "device_class": SensorDeviceClass.HUMIDITY,
        "unit": PERCENTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: AtlanticDataCoordinator = data["coordinator"]

    entities: list[SensorEntity] = []

    # Create sensors for all discovered device states
    for device_url, device_data in coordinator.get_all_devices().items():
        LOGGER.info(
            "Creating sensors for device: %s (%s)",
            device_data.label,
            device_url,
        )

        # Create a sensor for each state
        for state_name, state_info in device_data.states.items():
            entity = AtlanticStateSensor(
                coordinator=coordinator,
                device_url=device_url,
                state_name=state_name,
            )
            entities.append(entity)
            LOGGER.info(
                "  Created sensor: %s.%s = %s",
                device_data.label,
                state_name,
                state_info.get("value"),
            )

        # Create a raw data sensor for each device (for full exploration)
        entities.append(
            AtlanticRawDataSensor(
                coordinator=coordinator,
                device_url=device_url,
            )
        )

    # Create a global events sensor
    entities.append(AtlanticEventsSensor(coordinator=coordinator))

    # Create a full dump sensor
    entities.append(AtlanticFullDumpSensor(coordinator=coordinator))

    async_add_entities(entities)

    LOGGER.info("Created %d sensor entities", len(entities))


class AtlanticStateSensor(CoordinatorEntity[AtlanticDataCoordinator], SensorEntity):
    """Sensor for a specific device state."""

    def __init__(
        self,
        coordinator: AtlanticDataCoordinator,
        device_url: str,
        state_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_url = device_url
        self._state_name = state_name
        self._device_data = coordinator.get_device_data(device_url)

        # Create unique ID
        safe_url = device_url.replace("/", "_").replace(":", "_").replace("#", "_")
        safe_state = state_name.replace(":", "_")
        self._attr_unique_id = f"{safe_url}_{safe_state}"

        # Set name
        device_label = self._device_data.label if self._device_data else "Unknown"
        self._attr_name = f"{device_label} {self._format_state_name(state_name)}"

        # Apply configuration if known state type
        config = STATE_SENSOR_CONFIG.get(state_name, {})
        if "device_class" in config:
            self._attr_device_class = config["device_class"]
        if "unit" in config:
            self._attr_native_unit_of_measurement = config["unit"]
        if "state_class" in config:
            self._attr_state_class = config["state_class"]

    def _format_state_name(self, state_name: str) -> str:
        """Format state name for display."""
        # Remove prefix like "core:" or "io:"
        if ":" in state_name:
            state_name = state_name.split(":")[-1]
        # Convert camelCase to Title Case with spaces
        result = []
        for char in state_name:
            if char.isupper() and result:
                result.append(" ")
            result.append(char)
        return "".join(result).replace("State", "").strip()

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info."""
        if not self._device_data:
            return None
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_url)},
            name=self._device_data.label,
            manufacturer="Atlantic",
            model=f"{self._device_data.widget} ({self._device_data.ui_class})",
            sw_version=self._device_data.controllable_name,
        )

    @property
    def native_value(self) -> Any:
        """Return the state value."""
        device_data = self.coordinator.get_device_data(self._device_url)
        if device_data and self._state_name in device_data.states:
            return device_data.states[self._state_name].get("value")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        device_data = self.coordinator.get_device_data(self._device_url)
        if not device_data:
            return {}

        state_info = device_data.states.get(self._state_name, {})
        return {
            "state_name": self._state_name,
            "value_type": state_info.get("type"),
            "raw": state_info.get("raw"),
            "device_url": self._device_url,
            "widget": device_data.widget,
            "ui_class": device_data.ui_class,
            "last_updated": device_data.last_updated.isoformat(),
        }


class AtlanticRawDataSensor(CoordinatorEntity[AtlanticDataCoordinator], SensorEntity):
    """Sensor showing raw data for a device."""

    def __init__(
        self,
        coordinator: AtlanticDataCoordinator,
        device_url: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._device_url = device_url
        self._device_data = coordinator.get_device_data(device_url)

        safe_url = device_url.replace("/", "_").replace(":", "_").replace("#", "_")
        self._attr_unique_id = f"{safe_url}_raw_data"

        device_label = self._device_data.label if self._device_data else "Unknown"
        self._attr_name = f"{device_label} Raw Data"
        self._attr_icon = "mdi:code-json"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return device info."""
        if not self._device_data:
            return None
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_url)},
            name=self._device_data.label,
            manufacturer="Atlantic",
            model=f"{self._device_data.widget} ({self._device_data.ui_class})",
        )

    @property
    def native_value(self) -> str:
        """Return number of states as the value."""
        device_data = self.coordinator.get_device_data(self._device_url)
        if device_data:
            return f"{len(device_data.states)} states, {len(device_data.commands)} commands"
        return "No data"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return all device data as attributes."""
        device_data = self.coordinator.get_device_data(self._device_url)
        if not device_data:
            return {}

        return {
            "device_url": device_data.device_url,
            "label": device_data.label,
            "widget": device_data.widget,
            "ui_class": device_data.ui_class,
            "controllable_name": device_data.controllable_name,
            "protocol": device_data.protocol,
            "device_type": device_data.device_type,
            "available": device_data.available,
            "states": device_data.states,
            "attributes": device_data.attributes,
            "commands": device_data.commands,
            "state_definitions": device_data.state_definitions,
            "raw_data": device_data.raw_data,
            "last_updated": device_data.last_updated.isoformat(),
        }


class AtlanticEventsSensor(CoordinatorEntity[AtlanticDataCoordinator], SensorEntity):
    """Sensor showing recent events."""

    def __init__(self, coordinator: AtlanticDataCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = "atlantic_explorer_events"
        self._attr_name = "Atlantic Explorer Events"
        self._attr_icon = "mdi:history"

    @property
    def native_value(self) -> int:
        """Return number of events."""
        return len(self.coordinator.get_events_log())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return recent events."""
        events = self.coordinator.get_events_log()
        return {
            "total_events": len(events),
            "recent_events": events[-20:] if events else [],
        }


class AtlanticFullDumpSensor(CoordinatorEntity[AtlanticDataCoordinator], SensorEntity):
    """Sensor with full data dump for diagnostics."""

    def __init__(self, coordinator: AtlanticDataCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = "atlantic_explorer_full_dump"
        self._attr_name = "Atlantic Explorer Full Dump"
        self._attr_icon = "mdi:database-export"

    @property
    def native_value(self) -> str:
        """Return summary."""
        data = self.coordinator.get_full_data_dump()
        return f"{len(data.get('devices', {}))} devices, {len(data.get('gateways', []))} gateways"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return full data dump."""
        return self.coordinator.get_full_data_dump()
