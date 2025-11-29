"""Atlantic Heat Pump Explorer - Custom integration to discover all available data from Atlantic heat pumps."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

from pyoverkiz.client import OverkizClient
from pyoverkiz.const import SUPPORTED_SERVERS
from pyoverkiz.exceptions import (
    BadCredentialsException,
    MaintenanceException,
    TooManyRequestsException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import CONF_HUB, DEFAULT_SERVER, DOMAIN, LOGGER
from .coordinator import AtlanticDataCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Atlantic Heat Pump Explorer from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    server = entry.data.get(CONF_HUB, DEFAULT_SERVER)

    # Get server configuration
    server_config = SUPPORTED_SERVERS.get(server)
    if not server_config:
        LOGGER.error("Unknown server: %s", server)
        return False

    # Create client session
    session = async_create_clientsession(hass)

    # Create Overkiz client
    client = OverkizClient(
        username=username,
        password=password,
        session=session,
        server=server_config,
    )

    try:
        await client.login()
        LOGGER.info("Successfully logged in to %s as %s", server, username)
    except BadCredentialsException as exc:
        raise ConfigEntryAuthFailed("Invalid credentials") from exc
    except TooManyRequestsException as exc:
        raise ConfigEntryNotReady("Too many requests, try again later") from exc
    except MaintenanceException as exc:
        raise ConfigEntryNotReady("Server is under maintenance") from exc
    except Exception as exc:
        LOGGER.exception("Unexpected error during login")
        raise ConfigEntryNotReady(f"Unexpected error: {exc}") from exc

    # Get initial setup data and log everything
    try:
        setup = await client.get_setup()

        # Log all raw data for exploration
        await _log_full_setup_data(hass, setup, client)

    except Exception as exc:
        LOGGER.exception("Error fetching setup data")
        raise ConfigEntryNotReady(f"Error fetching data: {exc}") from exc

    # Create coordinator
    coordinator = AtlanticDataCoordinator(hass, client, setup)

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
        "setup": setup,
    }

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _log_full_setup_data(hass: HomeAssistant, setup: Any, client: OverkizClient) -> None:
    """Log all available data from the setup for exploration."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    LOGGER.info("=" * 80)
    LOGGER.info("ATLANTIC HEAT PUMP EXPLORER - FULL DATA DUMP")
    LOGGER.info("=" * 80)

    # Log gateways
    LOGGER.info("\n--- GATEWAYS ---")
    for gateway in setup.gateways:
        LOGGER.info("Gateway ID: %s", getattr(gateway, 'id', 'N/A'))
        LOGGER.info("  Gateway Type: %s", getattr(gateway, 'type', 'N/A'))
        LOGGER.info("  Is Alive: %s", getattr(gateway, 'alive', 'N/A'))
        LOGGER.info("  Mode: %s", getattr(gateway, 'mode', 'N/A'))
        LOGGER.info("  Protocol Version: %s", getattr(gateway, 'protocol_version', 'N/A'))
        LOGGER.info("  Firmware Version: %s", getattr(gateway, 'firmware_version', 'N/A'))

        # Try to get all gateway attributes
        try:
            gateway_dict = {}
            for attr in dir(gateway):
                if not attr.startswith('_'):
                    try:
                        value = getattr(gateway, attr)
                        if not callable(value):
                            gateway_dict[attr] = str(value)
                    except Exception:
                        pass
            LOGGER.info("  All Gateway Attributes: %s", json.dumps(gateway_dict, indent=2))
        except Exception as e:
            LOGGER.warning("  Could not serialize gateway: %s", e)

    # Log all devices
    LOGGER.info("\n--- DEVICES ---")
    for device in setup.devices:
        LOGGER.info("\n" + "-" * 60)
        LOGGER.info("Device URL: %s", device.device_url)
        LOGGER.info("  Label: %s", device.label)
        LOGGER.info("  Widget: %s", device.widget)
        LOGGER.info("  UI Class: %s", device.ui_class)
        LOGGER.info("  Controllable Name: %s", device.controllable_name)
        LOGGER.info("  Protocol: %s", device.protocol)
        LOGGER.info("  Available: %s", device.available)
        LOGGER.info("  Enabled: %s", device.enabled)
        LOGGER.info("  Type: %s", device.type)

        # Log all states
        if device.states:
            LOGGER.info("  --- STATES ---")
            for state in device.states:
                LOGGER.info("    State: %s = %s (type: %s)",
                           state.name, state.value, type(state.value).__name__)

        # Log all attributes (additional device properties)
        if device.attributes:
            LOGGER.info("  --- ATTRIBUTES ---")
            for attr in device.attributes:
                LOGGER.info("    Attribute: %s = %s", attr.name, attr.value)

        # Log available commands
        if device.definition:
            if device.definition.commands:
                LOGGER.info("  --- AVAILABLE COMMANDS ---")
                for cmd in device.definition.commands:
                    LOGGER.info("    Command: %s", cmd.command_name)
                    if cmd.parameters:
                        for param in cmd.parameters:
                            LOGGER.info("      Param: %s (type: %s)", param.name, param.type)

            # Log state definitions
            if device.definition.states:
                LOGGER.info("  --- STATE DEFINITIONS ---")
                for state_def in device.definition.states:
                    LOGGER.info("    State Definition: %s (type: %s)",
                               state_def.qualified_name, state_def.type)

        # Try to get all device attributes via reflection
        try:
            device_dict = {}
            for attr_name in dir(device):
                if not attr_name.startswith('_'):
                    try:
                        value = getattr(device, attr_name)
                        if not callable(value):
                            if hasattr(value, '__dict__'):
                                device_dict[attr_name] = str(value)
                            else:
                                device_dict[attr_name] = value
                    except Exception:
                        pass
            LOGGER.info("  --- RAW DEVICE DATA ---")
            LOGGER.info("  %s", json.dumps(device_dict, default=str, indent=2))
        except Exception as e:
            LOGGER.warning("  Could not serialize device: %s", e)

    # Log places/areas
    LOGGER.info("\n--- PLACES ---")
    if setup.root_place:
        _log_place(setup.root_place, 0)

    # Try to get scenarios
    try:
        scenarios = await client.get_scenarios()
        LOGGER.info("\n--- SCENARIOS ---")
        for scenario in scenarios:
            LOGGER.info("  Scenario: %s (label: %s)", scenario.oid, scenario.label)
    except Exception as e:
        LOGGER.warning("Could not fetch scenarios: %s", e)

    # Try to get action groups
    try:
        action_groups = await client.get_action_groups()
        LOGGER.info("\n--- ACTION GROUPS ---")
        for ag in action_groups:
            LOGGER.info("  Action Group: %s", ag.label)
            for action in ag.actions:
                LOGGER.info("    Action: %s on %s", action.commands, action.device_url)
    except Exception as e:
        LOGGER.warning("Could not fetch action groups: %s", e)

    LOGGER.info("\n" + "=" * 80)
    LOGGER.info("END OF DATA DUMP - Check Home Assistant logs for full details")
    LOGGER.info("=" * 80)


def _log_place(place: Any, indent: int) -> None:
    """Recursively log place hierarchy."""
    prefix = "  " * indent
    LOGGER.info("%sPlace: %s (OID: %s, Type: %s)", prefix, place.label, place.oid, place.type)

    for sub_place in place.sub_places:
        _log_place(sub_place, indent + 1)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        # Close client session
        if "client" in data:
            await data["client"].close()

    return unload_ok
