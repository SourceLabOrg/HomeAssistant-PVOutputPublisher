import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.core import callback
from homeassistant.data_entry_flow import section

from .const import (
    DOMAIN, CONF_API_KEY, CONF_SYSTEMS, CONF_NAME, CONF_SYSTEM_ID,
    CONF_FREQUENCY, DEFAULT_FREQUENCY, CONF_NOTES,
    CONF_V1, CONF_V2, CONF_V3, CONF_V4, CONF_V5, CONF_V6,
    CONF_V7, CONF_V8, CONF_V9, CONF_V10, CONF_V11, CONF_V12,
    CONF_B1, CONF_B2, CONF_B3, CONF_B4, CONF_B5, CONF_B6,
    CONF_C1, CONF_NET, CONF_DONATION_FIELDS
)

def _clean_system_input(user_input: dict) -> dict:
    """Flatten donation section inputs into the main system dictionary."""
    cleaned = {**user_input}
    if CONF_DONATION_FIELDS in cleaned:
        donation_data = cleaned.pop(CONF_DONATION_FIELDS) or {}
        cleaned.update(donation_data)
    return cleaned

def _get_system_schema(existing_data=None):
    frequency_options = {
        "5": "5 minutes", "10": "10 minutes", "15": "15 minutes",
        "30": "30 minutes", "60": "1 hour", "180": "3 hours"
    }

    data = existing_data or {}

    schema = {
        vol.Required(CONF_NAME, default=data.get(CONF_NAME, data.get(CONF_SYSTEM_ID, ""))): str,
        vol.Required(CONF_SYSTEM_ID, default=data.get(CONF_SYSTEM_ID, "")): str,
        vol.Required(CONF_FREQUENCY, default=str(data.get(CONF_FREQUENCY, DEFAULT_FREQUENCY))): vol.In(frequency_options),
    }

    # Internal Notes (Optional, not sent to API)
    if data.get(CONF_NOTES):
        schema[vol.Optional(CONF_NOTES, default=data.get(CONF_NOTES))] = selector.TextSelector(
            selector.TextSelectorConfig(multiline=True)
        )
    else:
        schema[vol.Optional(CONF_NOTES)] = selector.TextSelector(
            selector.TextSelectorConfig(multiline=True)
        )

    # v1 (Energy Generation - Wh)
    if data.get(CONF_V1):
        schema[vol.Optional(CONF_V1, default=data.get(CONF_V1))] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class=["energy"])
        )
    else:
        schema[vol.Optional(CONF_V1)] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class=["energy"])
        )

    # v2 (Power Generation - W)
    if data.get(CONF_V2):
        schema[vol.Optional(CONF_V2, default=data.get(CONF_V2))] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class=["power"])
        )
    else:
        schema[vol.Optional(CONF_V2)] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class=["power"])
        )

    # v3 (Energy Consumption - Wh)
    if data.get(CONF_V3):
        schema[vol.Optional(CONF_V3, default=data.get(CONF_V3))] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class=["energy"])
        )
    else:
        schema[vol.Optional(CONF_V3)] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class=["energy"])
        )

    # v4 (Power Consumption - W)
    if data.get(CONF_V4):
        schema[vol.Optional(CONF_V4, default=data.get(CONF_V4))] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class=["power"])
        )
    else:
        schema[vol.Optional(CONF_V4)] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class=["power"])
        )

    # v5 (Temperature - °C / °F)
    if data.get(CONF_V5):
        schema[vol.Optional(CONF_V5, default=data.get(CONF_V5))] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        )
    else:
        schema[vol.Optional(CONF_V5)] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        )

    # v6 (Voltage - V)
    if data.get(CONF_V6):
        schema[vol.Optional(CONF_V6, default=data.get(CONF_V6))] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class=["voltage"])
        )
    else:
        schema[vol.Optional(CONF_V6)] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class=["voltage"])
        )

    # Flags (Free / Standard)
    schema[vol.Optional(CONF_C1, default=data.get(CONF_C1, False))] = selector.BooleanSelector()
    schema[vol.Optional(CONF_NET, default=data.get(CONF_NET, False))] = selector.BooleanSelector()

    # Donation Section (v7-v12 & b1-b6)
    # NOTE: Use 'or data' fallback in case CONF_DONATION_FIELDS explicitly exists with value None.
    donation_data = data.get(CONF_DONATION_FIELDS) or data
    donation_keys = [
        CONF_V7, CONF_V8, CONF_V9, CONF_V10, CONF_V11, CONF_V12,
        CONF_B1, CONF_B2, CONF_B3, CONF_B4, CONF_B5, CONF_B6
    ]
    has_donation_configured = any(bool(donation_data.get(k)) for k in donation_keys)
    donation_schema = {}

    # v7 through v12 (Extended Data - Donation Feature)
    for v_key in [CONF_V7, CONF_V8, CONF_V9, CONF_V10, CONF_V11, CONF_V12]:
        if donation_data.get(v_key):
            donation_schema[vol.Optional(v_key, default=donation_data.get(v_key))] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )
        else:
            donation_schema[vol.Optional(v_key)] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain="sensor")
            )

    # b1 (Battery Power - W)
    if donation_data.get(CONF_B1):
        donation_schema[vol.Optional(CONF_B1, default=donation_data.get(CONF_B1))] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class=["power"])
        )
    else:
        donation_schema[vol.Optional(CONF_B1)] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class=["power"])
        )

    # b2 (Battery State of Charge - %)
    if donation_data.get(CONF_B2):
        donation_schema[vol.Optional(CONF_B2, default=donation_data.get(CONF_B2))] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class=["battery"])
        )
    else:
        donation_schema[vol.Optional(CONF_B2)] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class=["battery"])
        )

    # b3 (Battery Size / Usable Capacity - Wh)
    if donation_data.get(CONF_B3):
        donation_schema[vol.Optional(CONF_B3, default=donation_data.get(CONF_B3))] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        )
    else:
        donation_schema[vol.Optional(CONF_B3)] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        )

    # b4 (Battery Lifetime Charge - Wh)
    if donation_data.get(CONF_B4):
        donation_schema[vol.Optional(CONF_B4, default=donation_data.get(CONF_B4))] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class=["energy"])
        )
    else:
        donation_schema[vol.Optional(CONF_B4)] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class=["energy"])
        )

    # b5 (Battery Lifetime Discharge - Wh)
    if donation_data.get(CONF_B5):
        donation_schema[vol.Optional(CONF_B5, default=donation_data.get(CONF_B5))] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class=["energy"])
        )
    else:
        donation_schema[vol.Optional(CONF_B5)] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor", device_class=["energy"])
        )

    # b6 (Battery State - Code 0-9)
    if donation_data.get(CONF_B6):
        donation_schema[vol.Optional(CONF_B6, default=donation_data.get(CONF_B6))] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        )
    else:
        donation_schema[vol.Optional(CONF_B6)] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        )

    schema[vol.Optional(CONF_DONATION_FIELDS)] = section(
        vol.Schema(donation_schema),
        options={"collapsed": not has_donation_configured}
    )

    return vol.Schema(schema)

class PVOutputPusherConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

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
            cleaned_input = _clean_system_input(user_input)
            if self._editing_index is not None:
                self._systems[self._editing_index] = cleaned_input
                self._editing_index = None
            else:
                self._systems.append(cleaned_input)

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
            cleaned_input = _clean_system_input(user_input)
            if self._editing_index is not None:
                self._systems[self._editing_index] = cleaned_input
                self._editing_index = None
            else:
                self._systems.append(cleaned_input)
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
