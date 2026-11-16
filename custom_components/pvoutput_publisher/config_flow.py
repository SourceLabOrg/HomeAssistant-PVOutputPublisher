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
    """Flatten donation section inputs and strip empty/whitespace values from the system dictionary."""
    raw = {**user_input}
    if CONF_DONATION_FIELDS in raw:
        donation_data = raw.pop(CONF_DONATION_FIELDS) or {}
        raw.update(donation_data)

    cleaned = {}
    for k, v in raw.items():
        if isinstance(v, str):
            v = v.strip()
            if not v:
                continue
        elif v is None:
            continue
        cleaned[k] = v
    return cleaned

NON_EMPTY_STR = vol.All(str, vol.Strip, vol.Length(min=1))

def _required_non_empty_str_field(key: str, val: str | None = None):
    """Create a vol.Required marker with suggested_value if non-empty."""
    if val:
        return vol.Required(key, description={"suggested_value": val})
    return vol.Required(key)

def _optional_field(key: str, data: dict):
    """Create a vol.Optional marker with suggested_value if present, allowing fields to be cleared."""
    val = data.get(key)
    if val:
        return vol.Optional(key, description={"suggested_value": val})
    return vol.Optional(key)

def _get_system_schema(existing_data=None):
    frequency_options = {
        "5": "5 minutes", "10": "10 minutes", "15": "15 minutes",
        "30": "30 minutes", "60": "1 hour", "180": "3 hours"
    }

    data = existing_data or {}

    schema = {
        _required_non_empty_str_field(CONF_NAME, data.get(CONF_NAME) or data.get(CONF_SYSTEM_ID)): NON_EMPTY_STR,
        _required_non_empty_str_field(CONF_SYSTEM_ID, data.get(CONF_SYSTEM_ID)): NON_EMPTY_STR,
        vol.Required(CONF_FREQUENCY, default=str(data.get(CONF_FREQUENCY, DEFAULT_FREQUENCY))): vol.In(frequency_options),
    }

    # Internal Notes (Optional, not sent to API)
    schema[_optional_field(CONF_NOTES, data)] = selector.TextSelector(
        selector.TextSelectorConfig(multiline=True)
    )

    # v1 (Energy Generation - Wh)
    schema[_optional_field(CONF_V1, data)] = selector.EntitySelector(
        selector.EntitySelectorConfig(domain="sensor", device_class=["energy"])
    )

    # v2 (Power Generation - W)
    schema[_optional_field(CONF_V2, data)] = selector.EntitySelector(
        selector.EntitySelectorConfig(domain="sensor", device_class=["power"])
    )

    # v3 (Energy Consumption - Wh)
    schema[_optional_field(CONF_V3, data)] = selector.EntitySelector(
        selector.EntitySelectorConfig(domain="sensor", device_class=["energy"])
    )

    # v4 (Power Consumption - W)
    schema[_optional_field(CONF_V4, data)] = selector.EntitySelector(
        selector.EntitySelectorConfig(domain="sensor", device_class=["power"])
    )

    # v5 (Temperature - °C / °F)
    schema[_optional_field(CONF_V5, data)] = selector.EntitySelector(
        selector.EntitySelectorConfig(domain="sensor")
    )

    # v6 (Voltage - V)
    schema[_optional_field(CONF_V6, data)] = selector.EntitySelector(
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
        donation_schema[_optional_field(v_key, donation_data)] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain=["sensor", "number", "input_number"])
        )

    # b1 (Battery Power - W)
    donation_schema[_optional_field(CONF_B1, donation_data)] = selector.EntitySelector(
        selector.EntitySelectorConfig(domain="sensor", device_class=["power"])
    )

    # b2 (Battery State of Charge - %)
    donation_schema[_optional_field(CONF_B2, donation_data)] = selector.EntitySelector(
        selector.EntitySelectorConfig(domain="sensor", device_class=["battery"])
    )

    # b3 (Battery Size / Usable Capacity - Wh)
    donation_schema[_optional_field(CONF_B3, donation_data)] = selector.EntitySelector(
        selector.EntitySelectorConfig(domain=["sensor", "number", "input_number"])
    )

    # b4 (Battery Lifetime Charge - Wh)
    donation_schema[_optional_field(CONF_B4, donation_data)] = selector.EntitySelector(
        selector.EntitySelectorConfig(domain="sensor", device_class=["energy"])
    )

    # b5 (Battery Lifetime Discharge - Wh)
    donation_schema[_optional_field(CONF_B5, donation_data)] = selector.EntitySelector(
        selector.EntitySelectorConfig(domain="sensor", device_class=["energy"])
    )

    # b6 (Battery State - Code 0-9)
    donation_schema[_optional_field(CONF_B6, donation_data)] = selector.EntitySelector(
        selector.EntitySelectorConfig(domain=["sensor", "number", "input_number"])
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
            data_schema=vol.Schema({_required_non_empty_str_field(CONF_API_KEY): NON_EMPTY_STR})
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
                _required_non_empty_str_field(CONF_API_KEY, self._api_key): NON_EMPTY_STR,
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
