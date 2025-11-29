# Atlantic Heat Pump Explorer

A Home Assistant custom integration to explore and log all available data from Atlantic heat pumps and water heaters via the Overkiz/Cozytouch API.

## Purpose

This integration is designed for **data exploration and discovery**. It will:

1. **Log ALL available data** from your Atlantic devices to Home Assistant logs
2. **Create sensors** for every discovered state (temperatures, modes, energy consumption, etc.)
3. **Track events** to see what changes over time
4. **Export diagnostics** with complete device information for analysis

The goal is to discover what data is actually available from your Atlantic heat pump and water heater, beyond what the standard Overkiz integration exposes.

## Installation via HACS

### Adding the Repository

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots menu (top right) and select "Custom repositories"
4. Add this repository URL: `https://github.com/Patras3/atlantic_heat_pump_explorer`
5. Select category: "Integration"
6. Click "Add"

### Installing the Integration

1. Search for "Atlantic Heat Pump Explorer" in HACS
2. Click "Download"
3. Restart Home Assistant

### Configuration

1. Go to Settings > Devices & Services
2. Click "Add Integration"
3. Search for "Atlantic Heat Pump Explorer"
4. Enter your Cozytouch credentials (email and password)
5. Select your server (usually "Atlantic Cozytouch")

## What Data is Collected

### Devices Discovered

The integration will log and create sensors for all devices found, including:
- Heat pumps
- Water heaters (DHW - Domestic Hot Water)
- Thermostats
- Sensors
- Any other Overkiz-compatible devices

### Data Points

For each device, the integration captures:

- **States**: All current state values (temperatures, modes, on/off status, etc.)
- **Attributes**: Device configuration and properties
- **Commands**: Available commands that can be sent to the device
- **State Definitions**: All possible states the device can report
- **Raw Data**: Complete device object for analysis

### Example States You Might Find

- `core:TemperatureState` - Current temperature
- `core:TargetTemperatureState` - Target temperature
- `core:ComfortTargetDHWTemperatureState` - Comfort mode target temperature
- `core:EcoTargetDHWTemperatureState` - Eco mode target temperature
- `io:MiddleWaterTemperatureState` - Middle tank water temperature
- `io:OutletWaterTemperatureState` - Outlet water temperature
- `io:ElectricBoosterOperatingTimeState` - Immersion heater operating time
- `io:HeatPumpOperatingTimeState` - Heat pump operating time
- `core:ElectricPowerConsumptionState` - Power consumption
- `core:BoostOnOffState` - Boost mode status
- And many more...

## Viewing the Data

### Home Assistant Logs

The integration logs extensive information at startup and during operation:

```
Settings > System > Logs
```

Filter by "atlantic_heat_pump_explorer" to see all logged data.

### Sensors

Each discovered state becomes a sensor entity:
- Navigate to Settings > Devices & Services > Atlantic Heat Pump Explorer
- Click on a device to see all its sensors
- Each sensor has attributes with additional metadata

### Special Sensors

- **[Device] Raw Data** - Contains all states, attributes, and commands as JSON
- **Atlantic Explorer Events** - Recent events from the API
- **Atlantic Explorer Full Dump** - Complete data dump for diagnostics

### Diagnostics

For a complete export:

1. Go to Settings > Devices & Services
2. Click on Atlantic Heat Pump Explorer
3. Click the three dots menu
4. Select "Download diagnostics"

This gives you a JSON file with all discovered data.

## Standalone Exploration Script

For deeper API exploration without Home Assistant, use the included script:

```bash
cd scripts
pip install pyoverkiz
python explore_api.py --email your@email.com --password yourpassword
```

This will generate a detailed JSON report of all available data.

## Development

### Structure

```
custom_components/atlantic_heat_pump_explorer/
├── __init__.py          # Main integration setup
├── config_flow.py       # UI configuration
├── const.py             # Constants
├── coordinator.py       # Data coordination and logging
├── diagnostics.py       # Diagnostics export
├── manifest.json        # Integration manifest
├── sensor.py            # Sensor entities
├── binary_sensor.py     # Binary sensor entities
└── translations/
    └── en.json          # English translations
```

### Extending

Once you've discovered what data is available, you can:

1. Fork this repository
2. Add specific entity types (climate, water_heater, etc.)
3. Implement proper state mapping and controls
4. Create a full-featured integration

## Known Limitations

- This is an **exploration tool**, not a production integration
- No control functionality (only reads data)
- Logs may be verbose - check your log retention settings
- Event polling is set to 30 seconds

## Contributing

Found interesting data? Please open an issue with:

1. Your device type (heat pump model, water heater model)
2. Discovered states and their meanings
3. Any undocumented commands or features

This helps build knowledge for a proper Atlantic integration!

## License

MIT License - see LICENSE file

## Disclaimer

This integration is not affiliated with Atlantic or Overkiz. Use at your own risk.
