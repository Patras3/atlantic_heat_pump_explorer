"""Diagnostics support for Atlantic Heat Pump Explorer."""
from __future__ import annotations

import json
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .const import DOMAIN, LOGGER
from .coordinator import AtlanticDataCoordinator

TO_REDACT = {
    "username",
    "password",
    "email",
    "access_token",
    "refresh_token",
    "token",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: AtlanticDataCoordinator = data["coordinator"]

    # Get full data dump
    full_dump = coordinator.get_full_data_dump()

    # Get all events
    events = coordinator.get_events_log()

    # Build comprehensive diagnostics
    diagnostics = {
        "entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "domain": entry.domain,
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
        },
        "data_summary": {
            "device_count": len(full_dump.get("devices", {})),
            "gateway_count": len(full_dump.get("gateways", [])),
            "total_events": len(events),
        },
        "gateways": full_dump.get("gateways", []),
        "devices": {},
        "events": events[-100:] if len(events) > 100 else events,  # Last 100 events
    }

    # Process each device
    for device_url, device_data in full_dump.get("devices", {}).items():
        diagnostics["devices"][device_url] = {
            "label": device_data.get("label"),
            "widget": device_data.get("widget"),
            "ui_class": device_data.get("ui_class"),
            "controllable_name": device_data.get("controllable_name"),
            "protocol": device_data.get("protocol"),
            "device_type": device_data.get("device_type"),
            "available": device_data.get("available"),
            "states": device_data.get("states"),
            "attributes": device_data.get("attributes"),
            "commands": device_data.get("commands"),
            "state_definitions": device_data.get("state_definitions"),
            "raw_data": device_data.get("raw_data"),
            "last_updated": device_data.get("last_updated"),
        }

    LOGGER.info(
        "Generated diagnostics: %d devices, %d gateways, %d events",
        diagnostics["data_summary"]["device_count"],
        diagnostics["data_summary"]["gateway_count"],
        diagnostics["data_summary"]["total_events"],
    )

    return diagnostics
