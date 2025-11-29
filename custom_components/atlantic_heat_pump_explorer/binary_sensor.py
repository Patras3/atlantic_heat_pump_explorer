"""Binary sensor platform for Atlantic Heat Pump Explorer."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, LOGGER
from .coordinator import AtlanticDataCoordinator

# States that should be binary sensors
BINARY_STATE_CONFIG: dict[str, dict[str, Any]] = {
    "core:OnOffState": {
        "device_class": BinarySensorDeviceClass.POWER,
        "on_values": ["on", True, 1, "1"],
    },
    "core:BoostOnOffState": {
        "device_class": BinarySensorDeviceClass.RUNNING,
        "on_values": ["on", True, 1, "1"],
    },
    "core:DHWOnOffState": {
        "device_class": BinarySensorDeviceClass.RUNNING,
        "on_values": ["on", True, 1, "1"],
    },
    "io:DHWBoostModeState": {
        "device_class": BinarySensorDeviceClass.RUNNING,
        "on_values": ["on", True, 1, "1"],
    },
    "core:HeatingOnOffState": {
        "device_class": BinarySensorDeviceClass.HEAT,
        "on_values": ["on", True, 1, "1"],
    },
    "core:CoolingOnOffState": {
        "device_class": BinarySensorDeviceClass.COLD,
        "on_values": ["on", True, 1, "1"],
    },
    "io:ElectricBoosterOperatingModeState": {
        "device_class": BinarySensorDeviceClass.RUNNING,
        "on_values": ["on", True, 1, "1", "active"],
    },
    "core:OperatingModeState": {
        "device_class": None,
        "on_values": ["on", True, 1, "1", "heating", "cooling"],
    },
    "core:StatusState": {
        "device_class": BinarySensorDeviceClass.RUNNING,
        "on_values": ["available", "on", True, 1, "1"],
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: AtlanticDataCoordinator = data["coordinator"]

    entities: list[BinarySensorEntity] = []

    for device_url, device_data in coordinator.get_all_devices().items():
        # Create device availability binary sensor
        entities.append(
            AtlanticAvailabilitySensor(
                coordinator=coordinator,
                device_url=device_url,
            )
        )

        # Create binary sensors for known binary states
        for state_name, state_info in device_data.states.items():
            # Check if this is a known binary state
            if state_name in BINARY_STATE_CONFIG:
                entities.append(
                    AtlanticBinaryStateSensor(
                        coordinator=coordinator,
                        device_url=device_url,
                        state_name=state_name,
                    )
                )
                LOGGER.info(
                    "  Created binary sensor: %s.%s = %s",
                    device_data.label,
                    state_name,
                    state_info.get("value"),
                )

            # Also check for states that look like boolean values
            elif isinstance(state_info.get("value"), bool) or str(state_info.get("value")).lower() in ["on", "off", "true", "false"]:
                entities.append(
                    AtlanticBinaryStateSensor(
                        coordinator=coordinator,
                        device_url=device_url,
                        state_name=state_name,
                    )
                )
                LOGGER.info(
                    "  Created inferred binary sensor: %s.%s = %s",
                    device_data.label,
                    state_name,
                    state_info.get("value"),
                )

    async_add_entities(entities)
    LOGGER.info("Created %d binary sensor entities", len(entities))


class AtlanticAvailabilitySensor(CoordinatorEntity[AtlanticDataCoordinator], BinarySensorEntity):
    """Binary sensor for device availability."""

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
        self._attr_unique_id = f"{safe_url}_availability"

        device_label = self._device_data.label if self._device_data else "Unknown"
        self._attr_name = f"{device_label} Available"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

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
    def is_on(self) -> bool:
        """Return True if device is available."""
        device_data = self.coordinator.get_device_data(self._device_url)
        return device_data.available if device_data else False


class AtlanticBinaryStateSensor(CoordinatorEntity[AtlanticDataCoordinator], BinarySensorEntity):
    """Binary sensor for a specific device state."""

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

        safe_url = device_url.replace("/", "_").replace(":", "_").replace("#", "_")
        safe_state = state_name.replace(":", "_")
        self._attr_unique_id = f"{safe_url}_{safe_state}_binary"

        device_label = self._device_data.label if self._device_data else "Unknown"
        self._attr_name = f"{device_label} {self._format_state_name(state_name)}"

        # Apply configuration if known state type
        config = BINARY_STATE_CONFIG.get(state_name, {})
        if config.get("device_class"):
            self._attr_device_class = config["device_class"]

        self._on_values = config.get("on_values", ["on", True, 1, "1"])

    def _format_state_name(self, state_name: str) -> str:
        """Format state name for display."""
        if ":" in state_name:
            state_name = state_name.split(":")[-1]
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
        )

    @property
    def is_on(self) -> bool:
        """Return True if the state indicates 'on'."""
        device_data = self.coordinator.get_device_data(self._device_url)
        if device_data and self._state_name in device_data.states:
            value = device_data.states[self._state_name].get("value")
            # Check against known on values
            if value in self._on_values:
                return True
            if str(value).lower() in [str(v).lower() for v in self._on_values]:
                return True
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        device_data = self.coordinator.get_device_data(self._device_url)
        if not device_data:
            return {}

        state_info = device_data.states.get(self._state_name, {})
        return {
            "state_name": self._state_name,
            "raw_value": state_info.get("value"),
            "value_type": state_info.get("type"),
            "device_url": self._device_url,
        }
