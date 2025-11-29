"""Data coordinator for Atlantic Heat Pump Explorer."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pyoverkiz.client import OverkizClient
from pyoverkiz.enums import EventName
from pyoverkiz.models import Device, Event, Setup

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER, UPDATE_INTERVAL


@dataclass
class DeviceData:
    """Container for all discovered data about a device."""

    device_url: str
    label: str
    widget: str
    ui_class: str
    controllable_name: str
    protocol: str
    device_type: str
    available: bool
    states: dict[str, Any] = field(default_factory=dict)
    attributes: dict[str, Any] = field(default_factory=dict)
    commands: list[str] = field(default_factory=list)
    state_definitions: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class ExplorerData:
    """All data collected by the explorer."""

    devices: dict[str, DeviceData] = field(default_factory=dict)
    gateways: list[dict[str, Any]] = field(default_factory=list)
    events_log: list[dict[str, Any]] = field(default_factory=list)
    raw_api_responses: list[dict[str, Any]] = field(default_factory=list)
    last_full_refresh: datetime | None = None


class AtlanticDataCoordinator(DataUpdateCoordinator[ExplorerData]):
    """Coordinator to fetch and log all Atlantic heat pump data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: OverkizClient,
        setup: Setup,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.setup = setup
        self._data = ExplorerData()
        self._event_count = 0

        # Process initial setup
        self._process_setup(setup)

    def _process_setup(self, setup: Setup) -> None:
        """Process setup data and extract all information."""
        # Process gateways
        for gateway in setup.gateways:
            gateway_data = self._extract_all_attributes(gateway)
            self._data.gateways.append(gateway_data)
            LOGGER.debug("Processed gateway: %s", gateway_data)

        # Process devices
        for device in setup.devices:
            device_data = self._process_device(device)
            self._data.devices[device.device_url] = device_data

        self._data.last_full_refresh = datetime.now()

    def _process_device(self, device: Device) -> DeviceData:
        """Process a single device and extract all available data."""
        # Extract states
        states = {}
        if device.states:
            for state in device.states:
                states[state.name] = {
                    "value": state.value,
                    "type": type(state.value).__name__,
                    "raw": str(state),
                }

        # Extract attributes
        attributes = {}
        if device.attributes:
            for attr in device.attributes:
                attributes[attr.name] = {
                    "value": attr.value,
                    "type": type(attr.value).__name__,
                }

        # Extract available commands
        commands = []
        state_definitions = []
        if device.definition:
            if device.definition.commands:
                for cmd in device.definition.commands:
                    cmd_info = {
                        "name": getattr(cmd, 'command_name', str(cmd)),
                        "parameters": [],
                    }
                    params = getattr(cmd, 'parameters', None)
                    if params:
                        for param in params:
                            cmd_info["parameters"].append({
                                "name": getattr(param, 'name', 'N/A'),
                                "type": getattr(param, 'type', 'N/A'),
                            })
                    commands.append(cmd_info)

            if device.definition.states:
                for state_def in device.definition.states:
                    state_definitions.append({
                        "name": getattr(state_def, 'qualified_name', str(state_def)),
                        "type": getattr(state_def, 'type', 'N/A'),
                    })

        # Get all raw attributes via reflection
        raw_data = self._extract_all_attributes(device)

        return DeviceData(
            device_url=device.device_url,
            label=device.label,
            widget=str(device.widget),
            ui_class=str(device.ui_class),
            controllable_name=device.controllable_name or "",
            protocol=str(device.protocol) if device.protocol else "",
            device_type=str(device.type) if device.type else "",
            available=device.available,
            states=states,
            attributes=attributes,
            commands=commands,
            state_definitions=state_definitions,
            raw_data=raw_data,
            last_updated=datetime.now(),
        )

    def _extract_all_attributes(self, obj: Any) -> dict[str, Any]:
        """Extract all attributes from an object via reflection."""
        result = {}
        for attr_name in dir(obj):
            if attr_name.startswith('_'):
                continue
            try:
                value = getattr(obj, attr_name)
                if callable(value):
                    continue

                # Try to serialize the value
                if isinstance(value, (str, int, float, bool, type(None))):
                    result[attr_name] = value
                elif isinstance(value, (list, tuple)):
                    result[attr_name] = [self._safe_serialize(v) for v in value]
                elif isinstance(value, dict):
                    result[attr_name] = {k: self._safe_serialize(v) for k, v in value.items()}
                else:
                    result[attr_name] = str(value)
            except Exception as e:
                result[attr_name] = f"<error: {e}>"
        return result

    def _safe_serialize(self, value: Any) -> Any:
        """Safely serialize a value to JSON-compatible type."""
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        return str(value)

    async def _async_update_data(self) -> ExplorerData:
        """Fetch data from API and process events."""
        try:
            # Fetch events
            events = await self.client.fetch_events()

            for event in events:
                self._process_event(event)

            # Periodically do a full refresh to capture any missed changes
            if (
                self._data.last_full_refresh is None
                or (datetime.now() - self._data.last_full_refresh).seconds > 300
            ):
                LOGGER.info("Performing full setup refresh...")
                new_setup = await self.client.get_setup()
                self._process_setup(new_setup)

            return self._data

        except Exception as exc:
            LOGGER.exception("Error fetching data from API")
            raise UpdateFailed(f"Error communicating with API: {exc}") from exc

    def _process_event(self, event: Event) -> None:
        """Process an event and log all details."""
        self._event_count += 1

        event_data = {
            "timestamp": datetime.now().isoformat(),
            "event_number": self._event_count,
            "name": str(event.name),
            "raw": self._extract_all_attributes(event),
        }

        self._data.events_log.append(event_data)

        # Keep only last 1000 events
        if len(self._data.events_log) > 1000:
            self._data.events_log = self._data.events_log[-1000:]

        LOGGER.info("Event #%d: %s", self._event_count, event.name)
        LOGGER.debug("Event details: %s", json.dumps(event_data, default=str))

        # Handle specific event types
        if event.name == EventName.DEVICE_STATE_CHANGED:
            self._handle_state_change(event)
        elif event.name == EventName.DEVICE_AVAILABLE:
            self._handle_availability_change(event, True)
        elif event.name == EventName.DEVICE_UNAVAILABLE:
            self._handle_availability_change(event, False)
        elif event.name == EventName.DEVICE_CREATED:
            LOGGER.info("New device created: %s", getattr(event, 'device_url', 'unknown'))
        elif event.name == EventName.DEVICE_UPDATED:
            LOGGER.info("Device updated: %s", getattr(event, 'device_url', 'unknown'))

    def _handle_state_change(self, event: Event) -> None:
        """Handle device state change event."""
        if not hasattr(event, 'device_states') or not event.device_states:
            return

        for device_state in event.device_states:
            device_url = device_state.device_url
            if device_url in self._data.devices:
                for state in device_state.states:
                    old_value = self._data.devices[device_url].states.get(state.name, {}).get('value')
                    new_value = state.value

                    self._data.devices[device_url].states[state.name] = {
                        "value": new_value,
                        "type": type(new_value).__name__,
                        "raw": str(state),
                    }
                    self._data.devices[device_url].last_updated = datetime.now()

                    if old_value != new_value:
                        LOGGER.info(
                            "STATE CHANGE: %s.%s: %s -> %s",
                            self._data.devices[device_url].label,
                            state.name,
                            old_value,
                            new_value,
                        )

    def _handle_availability_change(self, event: Event, available: bool) -> None:
        """Handle device availability change."""
        device_url = getattr(event, 'device_url', None)
        if device_url and device_url in self._data.devices:
            self._data.devices[device_url].available = available
            LOGGER.info(
                "AVAILABILITY CHANGE: %s is now %s",
                self._data.devices[device_url].label,
                "available" if available else "unavailable",
            )

    def get_device_data(self, device_url: str) -> DeviceData | None:
        """Get data for a specific device."""
        return self._data.devices.get(device_url)

    def get_all_devices(self) -> dict[str, DeviceData]:
        """Get all device data."""
        return self._data.devices

    def get_events_log(self) -> list[dict[str, Any]]:
        """Get the events log."""
        return self._data.events_log

    def get_full_data_dump(self) -> dict[str, Any]:
        """Get a full data dump for diagnostics."""
        return {
            "devices": {
                url: {
                    "device_url": d.device_url,
                    "label": d.label,
                    "widget": d.widget,
                    "ui_class": d.ui_class,
                    "controllable_name": d.controllable_name,
                    "protocol": d.protocol,
                    "device_type": d.device_type,
                    "available": d.available,
                    "states": d.states,
                    "attributes": d.attributes,
                    "commands": d.commands,
                    "state_definitions": d.state_definitions,
                    "raw_data": d.raw_data,
                    "last_updated": d.last_updated.isoformat(),
                }
                for url, d in self._data.devices.items()
            },
            "gateways": self._data.gateways,
            "events_log_count": len(self._data.events_log),
            "last_events": self._data.events_log[-10:] if self._data.events_log else [],
            "last_full_refresh": self._data.last_full_refresh.isoformat() if self._data.last_full_refresh else None,
        }
