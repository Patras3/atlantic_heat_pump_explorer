"""Config flow for Atlantic Heat Pump Explorer."""
from __future__ import annotations

from typing import Any

from pyoverkiz.client import OverkizClient
from pyoverkiz.const import SUPPORTED_SERVERS
from pyoverkiz.exceptions import (
    BadCredentialsException,
    MaintenanceException,
    TooManyRequestsException,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import CONF_HUB, DEFAULT_SERVER, DOMAIN, LOGGER

# Server options for Atlantic/Cozytouch
SERVER_OPTIONS = {
    "atlantic_cozytouch": "Atlantic Cozytouch",
    "somfy_europe": "Somfy Europe (TaHoma)",
    "hi_kumo_europe": "Hitachi Hi Kumo Europe",
    "hi_kumo_asia": "Hitachi Hi Kumo Asia",
    "rexel": "Rexel Energeasy Connect",
    "nexity": "Nexity Eugénie",
    "somfy_oceania": "Somfy Oceania",
    "somfy_north_america": "Somfy North America",
}

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_HUB, default=DEFAULT_SERVER): vol.In(SERVER_OPTIONS),
    }
)


class AtlanticExplorerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Atlantic Heat Pump Explorer."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate credentials
            try:
                await self._validate_credentials(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    user_input[CONF_HUB],
                )
            except BadCredentialsException:
                errors["base"] = "invalid_auth"
            except TooManyRequestsException:
                errors["base"] = "too_many_requests"
            except MaintenanceException:
                errors["base"] = "server_maintenance"
            except Exception as exc:
                LOGGER.exception("Unexpected exception during validation")
                errors["base"] = "unknown"
            else:
                # Create unique ID based on username and server
                await self.async_set_unique_id(
                    f"{user_input[CONF_USERNAME]}_{user_input[CONF_HUB]}"
                )
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"Atlantic Explorer ({user_input[CONF_USERNAME]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def _validate_credentials(
        self, username: str, password: str, server: str
    ) -> None:
        """Validate the user credentials."""
        server_config = SUPPORTED_SERVERS.get(server)
        if not server_config:
            raise ValueError(f"Unknown server: {server}")

        session = async_create_clientsession(self.hass)
        client = OverkizClient(
            username=username,
            password=password,
            session=session,
            server=server_config,
        )

        try:
            await client.login()
            LOGGER.info("Credentials validated successfully for %s on %s", username, server)
        finally:
            await client.close()

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> FlowResult:
        """Handle reauthorization."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reauthorization confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
            if entry:
                try:
                    await self._validate_credentials(
                        entry.data[CONF_USERNAME],
                        user_input[CONF_PASSWORD],
                        entry.data.get(CONF_HUB, DEFAULT_SERVER),
                    )
                except BadCredentialsException:
                    errors["base"] = "invalid_auth"
                except Exception:
                    LOGGER.exception("Unexpected exception during reauth")
                    errors["base"] = "unknown"
                else:
                    self.hass.config_entries.async_update_entry(
                        entry,
                        data={**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]},
                    )
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )
