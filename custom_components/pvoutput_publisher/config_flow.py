import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.core import callback

from .const import (
    DOMAIN, CONF_API_KEY, CONF_SYSTEMS, CONF_NAME, CONF_SYSTEM_ID,
    CONF_ENTITY_ID, CONF_CONSUMPTION_ENTITY_ID, CONF_TEMPERATURE_ENTITY_ID,
    CONF_FREQUENCY, DEFAULT_FREQUENCY
)

def _get_system_schema(existing_data=None):
    frequency_options = {
        "5": "5 minutes", "10": "10 minutes", "15": "15 minutes",
        "30": "30 minutes", "60": "1 hour", "180": "3 hours"
    }

    schema = {}

    if existing_data:
        schema[vol.Required(CONF_NAME, default=existing_data.get(CONF_NAME, existing_data.get(CONF_SYSTEM_ID)))] = str
        schema[vol.Required(CONF_SYSTEM_ID, default=existing_data.get(CONF_SYSTEM_ID))] = str
        schema[vol.Required(CONF_ENTITY_ID, default=existing_data.get(CONF_ENTITY_ID))] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class=["power", "energy"])
        )

        if existing_data.get(CONF_CONSUMPTION_ENTITY_ID):
            schema[vol.Optional(CONF_CONSUMPTION_ENTITY_ID, default=existing_data.get(CONF_CONSUMPTION_ENTITY_ID))] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class=["power", "energy"])
            )
        else:
            schema[vol.Optional(CONF_CONSUMPTION_ENTITY_ID)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class=["power", "energy"])
            )

        if existing_data.get(CONF_TEMPERATURE_ENTITY_ID):
            schema[vol.Optional(CONF_TEMPERATURE_ENTITY_ID, default=existing_data.get(CONF_TEMPERATURE_ENTITY_ID))] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
            )
        else:
            schema[vol.Optional(CONF_TEMPERATURE_ENTITY_ID)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
            )

        schema[vol.Required(CONF_FREQUENCY, default=str(existing_data.get(CONF_FREQUENCY, "5")))] = vol.In(frequency_options)

    else:
        schema[vol.Required(CONF_NAME)] = str
        schema[vol.Required(CONF_SYSTEM_ID)] = str
        schema[vol.Required(CONF_ENTITY_ID)] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class=["power", "energy"])
        )
        schema[vol.Optional(CONF_CONSUMPTION_ENTITY_ID)] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class=["power", "energy"])
        )
        schema[vol.Optional(CONF_TEMPERATURE_ENTITY_ID)] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
        )
        schema[vol.Required(CONF_FREQUENCY, default="5")] = vol.In(frequency_options)

    return vol.Schema(schema)

class PVOutputPusherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._api_key = None
        self._systems = []
        self._editing_index = None

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self._api_key = user_input[CONF_API_KEY]
            return await self.async_step_add_system()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str})
        )

    async def async_step_add_system(self, user_input=None):
        if user_input is not None:
            if self._editing_index is not None:
                self._systems[self._editing_index] = user_input
                self._editing_index = None
            else:
                self._systems.append(user_input)

            return await self.async_step_systems_manager()

        existing_data = self._systems[self._editing_index] if self._editing_index is not None else None
        return self.async_show_form(
            step_id="add_system",
            data_schema=_get_system_schema(existing_data)
        )

    async def async_step_systems_manager(self, user_input=None):
        if user_input is not None:
            action = user_input["action"]

            if action == "finish":
                return self.async_create_entry(
                    title="PVOutput Publisher",
                    data={CONF_API_KEY: self._api_key, CONF_SYSTEMS: self._systems}
                )
            elif action == "add_new":
                self._editing_index = None
                return await self.async_step_add_system()
            elif action.startswith("edit_"):
                self._editing_index = int(action.split("_")[1])
                return await self.async_step_add_system()
            elif action.startswith("remove_"):
                idx = int(action.split("_")[1])
                self._systems.pop(idx)
                return await self.async_step_systems_manager()

        options = [
            selector.SelectOptionDict(value="finish", label="Finish Setup"),
            selector.SelectOptionDict(value="add_new", label="Add New System")
        ]

        for idx, sys in enumerate(self._systems):
            display_name = sys.get(CONF_NAME, sys.get(CONF_SYSTEM_ID))
            options.append(selector.SelectOptionDict(
                value=f"edit_{idx}", label=f"Edit: {display_name}"
            ))
            options.append(selector.SelectOptionDict(
                value=f"remove_{idx}", label=f"Remove: {display_name}"
            ))

        return self.async_show_form(
            step_id="systems_manager",
            data_schema=vol.Schema({
                vol.Required("action", default="finish"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.LIST)
                )
            })
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return PVOutputPusherOptionsFlowHandler(config_entry)


class PVOutputPusherOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._systems = list(config_entry.data.get(CONF_SYSTEMS, []))
        self._api_key = config_entry.data.get(CONF_API_KEY)
        self._editing_index = None

    async def async_step_init(self, user_input=None):
        return await self.async_step_systems_manager()

    async def async_step_add_system(self, user_input=None):
        if user_input is not None:
            if self._editing_index is not None:
                self._systems[self._editing_index] = user_input
                self._editing_index = None
            else:
                self._systems.append(user_input)
            return await self.async_step_systems_manager()

        existing_data = self._systems[self._editing_index] if self._editing_index is not None else None
        return self.async_show_form(
            step_id="add_system",
            data_schema=_get_system_schema(existing_data)
        )

    async def async_step_edit_api(self, user_input=None):
        if user_input is not None:
            self._api_key = user_input[CONF_API_KEY]
            return await self.async_step_systems_manager()

        return self.async_show_form(
            step_id="edit_api",
            data_schema=vol.Schema({
                vol.Required(CONF_API_KEY, default=self._api_key): str,
            })
        )

    async def async_step_systems_manager(self, user_input=None):
        if user_input is not None:
            action = user_input["action"]

            if action == "finish":
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={CONF_API_KEY: self._api_key, CONF_SYSTEMS: self._systems}
                )
                return self.async_create_entry(title="", data={})
            elif action == "edit_api":
                return await self.async_step_edit_api()
            elif action == "add_new":
                self._editing_index = None
                return await self.async_step_add_system()
            elif action.startswith("edit_"):
                self._editing_index = int(action.split("_")[1])
                return await self.async_step_add_system()
            elif action.startswith("remove_"):
                idx = int(action.split("_")[1])
                self._systems.pop(idx)
                return await self.async_step_systems_manager()

        options = [
            selector.SelectOptionDict(value="finish", label="Save and Close"),
            selector.SelectOptionDict(value="edit_api", label="Edit API Key"),
            selector.SelectOptionDict(value="add_new", label="Add New System")
        ]

        for idx, sys in enumerate(self._systems):
            display_name = sys.get(CONF_NAME, sys.get(CONF_SYSTEM_ID))
            options.append(selector.SelectOptionDict(
                value=f"edit_{idx}", label=f"Edit: {display_name}"
            ))
            options.append(selector.SelectOptionDict(
                value=f"remove_{idx}", label=f"Remove: {display_name}"
            ))

        return self.async_show_form(
            step_id="systems_manager",
            data_schema=vol.Schema({
                vol.Required("action", default="finish"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=options, mode=selector.SelectSelectorMode.LIST)
                )
            })
        )
