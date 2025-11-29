"""Constants for Atlantic Heat Pump Explorer integration."""
from __future__ import annotations

from datetime import timedelta
import logging

DOMAIN = "atlantic_heat_pump_explorer"
LOGGER = logging.getLogger(__package__)

# Configuration keys
CONF_HUB = "hub"

# Update interval - more frequent for data discovery
UPDATE_INTERVAL = timedelta(seconds=30)

# Supported Overkiz servers for Atlantic devices
ATLANTIC_SERVERS = {
    "atlantic_cozytouch": "Atlantic Cozytouch",
}

# Default server
DEFAULT_SERVER = "atlantic_cozytouch"
