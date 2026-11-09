"""Config flow for net4home integration."""
import logging
import os
import socket

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    DOMAIN,
    N4H_IP_PORT,
    DEFAULT_MI,
    DEFAULT_OBJADR,
    CONF_MI,
    CONF_OBJADR,
    CONF_AUTO_DISCOVERY,
    CONF_READ_GROUPS_ON_STARTUP,
    CONF_READ_MODULE_INFO_ON_STARTUP,
)
from .api import Net4HomeApi
from .local_discovery import endpoint_from_config, local_endpoint_from_discovery

_LOGGER = logging.getLogger(__name__)

_REMOTE_SCHEMA = vol.Schema({
    vol.Required("host"): str,
    vol.Required("port", default=N4H_IP_PORT): int,
    vol.Required("password"): str,
    vol.Required(CONF_MI, default=DEFAULT_MI): int,
    vol.Required(CONF_OBJADR, default=DEFAULT_OBJADR): int,
    vol.Optional(CONF_AUTO_DISCOVERY, default=True): bool,
})


def _on_hassio() -> bool:
    """Return True when this Home Assistant runs under Supervisor."""
    return bool(
        os.environ.get("SUPERVISOR")
        or os.environ.get("SUPERVISOR_TOKEN")
        or os.environ.get("SUPERVISOR_SOCKET")
    )


async def async_local_service(hass) -> dict | None:
    """Return the local add-on endpoint, if it has announced itself."""
    if not _on_hassio():
        return None
    try:
        from homeassistant.components.hassio.handler import get_supervisor_client

        items = await get_supervisor_client(hass).discovery.list()
    except Exception as err:
        _LOGGER.debug("Local net4home service is not available: %s", err)
        return None
    return local_endpoint_from_discovery(items)


class Net4HomeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._local: dict | None = None

    async def async_step_user(self, user_input=None):
        """Offer local when the add-on is present, otherwise ask for an IP address."""
        self._local = await async_local_service(self.hass)
        if self._local:
            return self.async_show_menu(
                step_id="user",
                menu_options=["local", "remote"],
            )
        return await self.async_step_remote()

    async def async_step_hassio(self, discovery_info):
        """Confirm the service announced by the local add-on."""
        config = getattr(discovery_info, "config", None)
        if config is None and isinstance(discovery_info, dict):
            config = discovery_info
        self._local = endpoint_from_config(config if isinstance(config, dict) else None)
        await self.async_set_unique_id(f"{self._local['host']}:{self._local['port']}")
        self._abort_if_unique_id_configured()
        return self.async_show_form(step_id="local", data_schema=vol.Schema({}))

    async def async_step_local(self, user_input=None):
        """Use the local add-on. Host, port and password stay hidden."""
        if self._local is None:
            self._local = await async_local_service(self.hass)
        if not self._local:
            return self.async_abort(reason="no_local_service")
        errors = await self._async_test_connection(
            self._local["host"],
            self._local["port"],
            "",
            DEFAULT_MI,
            DEFAULT_OBJADR,
        )
        if not errors:
            await self.async_set_unique_id(f"{self._local['host']}:{self._local['port']}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="net4home",
                data=self._entry_data(
                    self._local["host"],
                    self._local["port"],
                    "",
                    DEFAULT_MI,
                    DEFAULT_OBJADR,
                    True,
                    local=True,
                ),
            )
        return self.async_show_form(
            step_id="local",
            data_schema=vol.Schema({}),
            errors=errors,
        )

    async def async_step_remote(self, user_input=None):
        """Ask for a remote bus connector."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(f"{user_input['host']}:{user_input['port']}")
            self._abort_if_unique_id_configured()
            errors = await self._async_test_connection(
                user_input["host"],
                user_input["port"],
                user_input["password"],
                user_input.get(CONF_MI),
                user_input.get(CONF_OBJADR),
            )
            if not errors:
                return self.async_create_entry(
                    title=user_input["host"],
                    data=self._entry_data(
                        user_input["host"],
                        user_input["port"],
                        user_input["password"],
                        user_input[CONF_MI],
                        user_input[CONF_OBJADR],
                        user_input.get(CONF_AUTO_DISCOVERY, True),
                    ),
                )

        return self.async_show_form(
            step_id="remote",
            data_schema=_REMOTE_SCHEMA,
            errors=errors,
        )

    async def _async_test_connection(self, host, port, password, mi, objadr) -> dict:
        """Connect once and return a form error map. Empty means success."""
        client = Net4HomeApi(
            hass=self.hass,
            host=host,
            port=port,
            password=password,
            mi=mi,
            objadr=objadr,
        )
        errors = {}
        try:
            await client.async_connect()
        except socket.gaierror:
            errors["host"] = "host_not_found"
        except TimeoutError:
            errors["base"] = "timeout"
        except OSError:
            errors["base"] = "cannot_connect"
        except Exception as ex:
            _LOGGER.exception("Unknown error in ConfigFlow", exc_info=ex)
            errors["base"] = "unknown"
        finally:
            await client.async_disconnect()
        return errors

    @staticmethod
    def _entry_data(host, port, password, mi, objadr, auto_discovery, local=False) -> dict:
        """Build the stored config entry."""
        data = {
            "host": host,
            "port": port,
            "password": password,
            CONF_MI: mi,
            CONF_OBJADR: objadr,
            CONF_AUTO_DISCOVERY: auto_discovery,
            CONF_READ_GROUPS_ON_STARTUP: True,
            CONF_READ_MODULE_INFO_ON_STARTUP: True,
        }
        if local:
            data["local"] = True
        return data

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        # In Home Assistant 2025.12+, config_entry is automatically available
        # as a property in OptionsFlow - don't pass it to __init__
        return Net4HomeOptionsFlowHandler()


class Net4HomeOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for net4home integration."""

    def __init__(self):
        """Initialize the options flow handler."""
        # In Home Assistant 2025.12+, config_entry is automatically available
        # as a read-only property via self.config_entry
        # No need to accept it as a parameter or set it manually
        super().__init__()

    async def async_step_init(self, user_input=None):
        """Single step for options including ENUM_ALL trigger settings."""
        errors = {}
        
        # Load existing devices from options
        devices = dict(self.config_entry.options.get("devices", {}))
        
        # Get MI and OBJADR from config.data
        current_mi = self.config_entry.data.get(CONF_MI, DEFAULT_MI)
        current_objadr = self.config_entry.data.get(CONF_OBJADR, DEFAULT_OBJADR)

        # Build dynamic schema: ENUM_ALL option with MI and OBJADR
        schema_dict = {
            vol.Optional(CONF_MI, default=current_mi): int,
            vol.Optional(CONF_OBJADR, default=current_objadr): int,
            vol.Optional("trigger_enum_all", default=False): bool,
            vol.Optional(CONF_AUTO_DISCOVERY, default=self.config_entry.data.get(CONF_AUTO_DISCOVERY, True)): bool,
            vol.Optional(
                CONF_READ_GROUPS_ON_STARTUP,
                default=self.config_entry.data.get(CONF_READ_GROUPS_ON_STARTUP, True),
            ): bool,
            vol.Optional(
                CONF_READ_MODULE_INFO_ON_STARTUP,
                default=self.config_entry.data.get(CONF_READ_MODULE_INFO_ON_STARTUP, True),
            ): bool,
        }
        
        schema = vol.Schema(schema_dict)
        
        if user_input is not None:
            # If MI, OBJADR, or AUTO_DISCOVERY were changed, update config.data
            if (
                CONF_MI in user_input
                or CONF_OBJADR in user_input
                or CONF_AUTO_DISCOVERY in user_input
                or CONF_READ_GROUPS_ON_STARTUP in user_input
                or CONF_READ_MODULE_INFO_ON_STARTUP in user_input
            ):
                new_data = dict(self.config_entry.data)
                if CONF_MI in user_input:
                    new_data[CONF_MI] = user_input[CONF_MI]
                if CONF_OBJADR in user_input:
                    new_data[CONF_OBJADR] = user_input[CONF_OBJADR]
                if CONF_AUTO_DISCOVERY in user_input:
                    new_data[CONF_AUTO_DISCOVERY] = user_input[CONF_AUTO_DISCOVERY]
                if CONF_READ_GROUPS_ON_STARTUP in user_input:
                    new_data[CONF_READ_GROUPS_ON_STARTUP] = user_input[CONF_READ_GROUPS_ON_STARTUP]
                if CONF_READ_MODULE_INFO_ON_STARTUP in user_input:
                    new_data[CONF_READ_MODULE_INFO_ON_STARTUP] = user_input[CONF_READ_MODULE_INFO_ON_STARTUP]
                self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
                _LOGGER.info(
                    "[net4home] Configuration updated: MI=%s, OBJADR=%s, AUTO_DISCOVERY=%s, groups=%s, module_info=%s",
                    new_data.get(CONF_MI),
                    new_data.get(CONF_OBJADR),
                    new_data.get(CONF_AUTO_DISCOVERY),
                    new_data.get(CONF_READ_GROUPS_ON_STARTUP),
                    new_data.get(CONF_READ_MODULE_INFO_ON_STARTUP),
                )
            
            # If ENUM_ALL should be triggered
            if user_input.get("trigger_enum_all"):
                # Get the API instance
                api = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
                if api:
                    try:
                        await api.send_enum_all()
                        _LOGGER.info(f"[net4home] ENUM_ALL manually triggered (entry_id {self.config_entry.entry_id})")
                    except Exception as e:
                        _LOGGER.error(f"[net4home] Error during manual ENUM_ALL: {e}", exc_info=True)
                        errors["base"] = "enum_all_failed"
                else:
                    errors["base"] = "api_not_available"
                    _LOGGER.warning(f"[net4home] API not available for entry_id {self.config_entry.entry_id}")

            # Write options back to config (only if no errors)
            if not errors:
                new_options = dict(self.config_entry.options)
                new_options["devices"] = devices
                self.hass.config_entries.async_update_entry(self.config_entry, options=new_options)
                return self.async_create_entry(title="", data=new_options)
        
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "entry_id": self.config_entry.entry_id,
            }
        )
