import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv
from homeassistant.core import callback

from .const import (
    DOMAIN, CONF_API_KEY, CONF_SYSTEMS, CONF_SYSTEM_ID,
    CONF_ENTITY_ID, CONF_FREQUENCY, DEFAULT_FREQUENCY
)

class PVOutputPusherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._api_key = None
        self._systems = []

    async def async_step_user(self, user_input=None):
        """Step 1: Get the API Key."""
        if user_input is not None:
            self._api_key = user_input[CONF_API_KEY]
            return await self.async_step_add_system()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_API_KEY): str,
            })
        )

    async def async_step_add_system(self, user_input=None):
        """Step 2: Add a System ID and map it to a sensor."""
        if user_input is not None:
            self._systems.append({
                CONF_SYSTEM_ID: user_input[CONF_SYSTEM_ID],
                CONF_ENTITY_ID: user_input[CONF_ENTITY_ID],
                CONF_FREQUENCY: user_input[CONF_FREQUENCY]
            })
            return await self.async_step_add_another()

        return self.async_show_form(
            step_id="add_system",
            data_schema=vol.Schema({
                vol.Required(CONF_SYSTEM_ID): str,
                vol.Required(CONF_ENTITY_ID): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_FREQUENCY, default=DEFAULT_FREQUENCY): vol.All(vol.Coerce(int), vol.Range(min=1, max=60))
            })
        )

    async def async_step_add_another(self, user_input=None):
        """Step 3: Ask to loop back or finish."""
        if user_input is not None:
            if user_input["add_another"]:
                return await self.async_step_add_system()

            return self.async_create_entry(
                title="PVOutput Publisher",
                data={
                    CONF_API_KEY: self._api_key,
                    CONF_SYSTEMS: self._systems
                }
            )

        return self.async_show_form(
            step_id="add_another",
            data_schema=vol.Schema({
                vol.Required("add_another", default=False): bool
            })
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Tell Home Assistant we have an Options Flow."""
        return PVOutputPusherOptionsFlowHandler(config_entry)


class PVOutputPusherOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle the Options Flow (the 'Configure' button)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry
        self._systems = list(config_entry.data.get(CONF_SYSTEMS, []))
        self._api_key = config_entry.data.get(CONF_API_KEY)

    async def async_step_init(self, user_input=None):
        """Step 1: Show a menu of configuration options."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_system", "remove_system", "edit_api"]
        )

    async def async_step_edit_api(self, user_input=None):
        """Option A: Edit the global API key."""
        if user_input is not None:
            self._api_key = user_input[CONF_API_KEY]
            return await self._update_entry()

        return self.async_show_form(
            step_id="edit_api",
            data_schema=vol.Schema({
                vol.Required(CONF_API_KEY, default=self._api_key): str,
            })
        )

    async def async_step_add_system(self, user_input=None):
        """Option B: Add a new system to the list."""
        if user_input is not None:
            self._systems.append({
                CONF_SYSTEM_ID: user_input[CONF_SYSTEM_ID],
                CONF_ENTITY_ID: user_input[CONF_ENTITY_ID],
                CONF_FREQUENCY: user_input[CONF_FREQUENCY]
            })
            return await self._update_entry()

        return self.async_show_form(
            step_id="add_system",
            data_schema=vol.Schema({
                vol.Required(CONF_SYSTEM_ID): str,
                vol.Required(CONF_ENTITY_ID): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_FREQUENCY, default=DEFAULT_FREQUENCY): vol.All(vol.Coerce(int), vol.Range(min=1, max=60))
            })
        )

    async def async_step_remove_system(self, user_input=None):
        """Option C: Remove an existing system via a multi-select dropdown."""
        if user_input is not None:
            selected = user_input.get("systems_to_remove", [])
            self._systems = [s for s in self._systems if s[CONF_SYSTEM_ID] not in selected]
            return await self._update_entry()

        systems_list = {s[CONF_SYSTEM_ID]: f"System {s[CONF_SYSTEM_ID]} ({s[CONF_ENTITY_ID]})" for s in self._systems}

        return self.async_show_form(
            step_id="remove_system",
            data_schema=vol.Schema({
                vol.Optional("systems_to_remove"): cv.multi_select(systems_list)
            })
        )

    async def _update_entry(self):
        """Save the new data and tell Home Assistant we are done."""
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data={CONF_API_KEY: self._api_key, CONF_SYSTEMS: self._systems}
        )
        return self.async_create_entry(title="", data={})
