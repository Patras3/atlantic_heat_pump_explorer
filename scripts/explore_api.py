#!/usr/bin/env python3
"""
Atlantic Heat Pump API Explorer

Standalone script to explore all available data from the Overkiz/Cozytouch API
for Atlantic heat pumps and water heaters.

Usage:
    python explore_api.py --email your@email.com --password yourpassword

This will generate a detailed JSON report of all available devices, states,
commands, and raw API responses.
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from pyoverkiz.client import OverkizClient
    from pyoverkiz.const import SUPPORTED_SERVERS
    from pyoverkiz.exceptions import BadCredentialsException
except ImportError:
    print("Error: pyoverkiz is not installed.")
    print("Install it with: pip install pyoverkiz")
    sys.exit(1)

import aiohttp


def extract_all_attributes(obj: Any, depth: int = 0, max_depth: int = 5) -> Any:
    """Extract all attributes from an object via reflection."""
    if depth > max_depth:
        return str(obj)

    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj

    if isinstance(obj, (list, tuple)):
        return [extract_all_attributes(item, depth + 1, max_depth) for item in obj]

    if isinstance(obj, dict):
        return {k: extract_all_attributes(v, depth + 1, max_depth) for k, v in obj.items()}

    # Try to extract attributes from object
    result = {}
    for attr_name in dir(obj):
        if attr_name.startswith('_'):
            continue
        try:
            value = getattr(obj, attr_name)
            if callable(value):
                continue
            result[attr_name] = extract_all_attributes(value, depth + 1, max_depth)
        except Exception as e:
            result[attr_name] = f"<error: {e}>"

    return result if result else str(obj)


async def explore_api(email: str, password: str, server: str = "atlantic_cozytouch") -> dict:
    """Connect to the API and explore all available data."""
    print(f"\n{'='*80}")
    print("ATLANTIC HEAT PUMP API EXPLORER")
    print(f"{'='*80}")
    print(f"Server: {server}")
    print(f"Email: {email}")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"{'='*80}\n")

    server_config = SUPPORTED_SERVERS.get(server)
    if not server_config:
        print(f"Error: Unknown server '{server}'")
        print(f"Available servers: {list(SUPPORTED_SERVERS.keys())}")
        return {}

    report = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "server": server,
            "email": email,
        },
        "gateways": [],
        "devices": [],
        "scenarios": [],
        "action_groups": [],
        "places": [],
        "errors": [],
    }

    async with aiohttp.ClientSession() as session:
        client = OverkizClient(
            username=email,
            password=password,
            session=session,
            server=server_config,
        )

        try:
            print("Logging in...")
            await client.login()
            print("Login successful!\n")
        except BadCredentialsException:
            print("Error: Invalid credentials")
            return {"error": "Invalid credentials"}
        except Exception as e:
            print(f"Error during login: {e}")
            return {"error": str(e)}

        # Get setup data
        print("Fetching setup data...")
        try:
            setup = await client.get_setup()
            print(f"  Found {len(setup.gateways)} gateway(s)")
            print(f"  Found {len(setup.devices)} device(s)")
        except Exception as e:
            print(f"Error fetching setup: {e}")
            report["errors"].append({"context": "setup", "error": str(e)})
            return report

        # Process gateways
        print("\n--- GATEWAYS ---")
        for gateway in setup.gateways:
            print(f"\nGateway: {gateway.id}")
            gateway_data = extract_all_attributes(gateway)
            report["gateways"].append(gateway_data)

            for key, value in gateway_data.items():
                if key not in ['id'] and not isinstance(value, (dict, list)):
                    print(f"  {key}: {value}")

        # Process devices
        print("\n--- DEVICES ---")
        for device in setup.devices:
            print(f"\n{'='*60}")
            print(f"Device: {device.label}")
            print(f"  URL: {device.device_url}")
            print(f"  Widget: {device.widget}")
            print(f"  UI Class: {device.ui_class}")
            print(f"  Controllable Name: {device.controllable_name}")
            print(f"  Protocol: {device.protocol}")
            print(f"  Available: {device.available}")

            device_data = {
                "device_url": device.device_url,
                "label": device.label,
                "widget": str(device.widget),
                "ui_class": str(device.ui_class),
                "controllable_name": device.controllable_name,
                "protocol": str(device.protocol) if device.protocol else None,
                "type": str(device.type) if device.type else None,
                "available": device.available,
                "enabled": device.enabled,
                "states": {},
                "attributes": {},
                "commands": [],
                "state_definitions": [],
                "raw": extract_all_attributes(device),
            }

            # Extract states
            if device.states:
                print(f"\n  STATES ({len(device.states)}):")
                for state in device.states:
                    print(f"    {state.name}: {state.value} ({type(state.value).__name__})")
                    device_data["states"][state.name] = {
                        "value": state.value if isinstance(state.value, (str, int, float, bool, type(None), list, dict)) else str(state.value),
                        "type": type(state.value).__name__,
                    }

            # Extract attributes
            if device.attributes:
                print(f"\n  ATTRIBUTES ({len(device.attributes)}):")
                for attr in device.attributes:
                    print(f"    {attr.name}: {attr.value}")
                    device_data["attributes"][attr.name] = {
                        "value": attr.value if isinstance(attr.value, (str, int, float, bool, type(None), list, dict)) else str(attr.value),
                        "type": type(attr.value).__name__,
                    }

            # Extract commands
            if device.definition and device.definition.commands:
                print(f"\n  COMMANDS ({len(device.definition.commands)}):")
                for cmd in device.definition.commands:
                    params = []
                    if cmd.parameters:
                        params = [{"name": p.name, "type": p.type} for p in cmd.parameters]
                    print(f"    {cmd.command_name}")
                    if params:
                        for p in params:
                            print(f"      - {p['name']}: {p['type']}")
                    device_data["commands"].append({
                        "name": cmd.command_name,
                        "parameters": params,
                    })

            # Extract state definitions
            if device.definition and device.definition.states:
                print(f"\n  STATE DEFINITIONS ({len(device.definition.states)}):")
                for state_def in device.definition.states:
                    print(f"    {state_def.qualified_name} ({state_def.type})")
                    device_data["state_definitions"].append({
                        "name": state_def.qualified_name,
                        "type": state_def.type,
                    })

            report["devices"].append(device_data)

        # Get scenarios
        print("\n--- SCENARIOS ---")
        try:
            scenarios = await client.get_scenarios()
            print(f"Found {len(scenarios)} scenario(s)")
            for scenario in scenarios:
                print(f"  {scenario.label} (OID: {scenario.oid})")
                report["scenarios"].append({
                    "oid": scenario.oid,
                    "label": scenario.label,
                    "raw": extract_all_attributes(scenario),
                })
        except Exception as e:
            print(f"Error fetching scenarios: {e}")
            report["errors"].append({"context": "scenarios", "error": str(e)})

        # Get action groups
        print("\n--- ACTION GROUPS ---")
        try:
            action_groups = await client.get_action_groups()
            print(f"Found {len(action_groups)} action group(s)")
            for ag in action_groups:
                print(f"  {ag.label}")
                report["action_groups"].append({
                    "label": ag.label,
                    "raw": extract_all_attributes(ag),
                })
        except Exception as e:
            print(f"Error fetching action groups: {e}")
            report["errors"].append({"context": "action_groups", "error": str(e)})

        # Get places
        print("\n--- PLACES ---")
        if setup.root_place:
            def process_place(place, depth=0):
                prefix = "  " * depth
                print(f"{prefix}{place.label} (OID: {place.oid}, Type: {place.type})")
                place_data = {
                    "oid": place.oid,
                    "label": place.label,
                    "type": str(place.type) if place.type else None,
                    "sub_places": [],
                }
                for sub in place.sub_places:
                    place_data["sub_places"].append(process_place(sub, depth + 1))
                return place_data

            report["places"].append(process_place(setup.root_place))

        # Try to fetch events
        print("\n--- EVENTS ---")
        try:
            events = await client.fetch_events()
            print(f"Found {len(events)} event(s)")
            report["recent_events"] = []
            for event in events[:10]:  # Only first 10
                event_data = extract_all_attributes(event)
                report["recent_events"].append(event_data)
                print(f"  Event: {event.name}")
        except Exception as e:
            print(f"Error fetching events: {e}")
            report["errors"].append({"context": "events", "error": str(e)})

        await client.close()

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Explore Atlantic Heat Pump API data"
    )
    parser.add_argument(
        "--email", "-e",
        required=True,
        help="Cozytouch account email"
    )
    parser.add_argument(
        "--password", "-p",
        required=True,
        help="Cozytouch account password"
    )
    parser.add_argument(
        "--server", "-s",
        default="atlantic_cozytouch",
        help="Server to connect to (default: atlantic_cozytouch)"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output file path (default: atlantic_api_dump_<timestamp>.json)"
    )
    parser.add_argument(
        "--list-servers",
        action="store_true",
        help="List available servers and exit"
    )

    args = parser.parse_args()

    if args.list_servers:
        print("Available servers:")
        for server in SUPPORTED_SERVERS:
            print(f"  - {server}")
        return

    # Run the exploration
    report = asyncio.run(explore_api(args.email, args.password, args.server))

    # Save report
    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(f"atlantic_api_dump_{timestamp}.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n{'='*80}")
    print(f"Report saved to: {output_path}")
    print(f"{'='*80}")

    # Summary
    if "devices" in report:
        print(f"\nSUMMARY:")
        print(f"  Gateways: {len(report.get('gateways', []))}")
        print(f"  Devices: {len(report.get('devices', []))}")

        total_states = sum(len(d.get("states", {})) for d in report["devices"])
        total_commands = sum(len(d.get("commands", [])) for d in report["devices"])
        print(f"  Total States: {total_states}")
        print(f"  Total Commands: {total_commands}")

        if report.get("errors"):
            print(f"  Errors: {len(report['errors'])}")
            for error in report["errors"]:
                print(f"    - {error['context']}: {error['error']}")


if __name__ == "__main__":
    main()
