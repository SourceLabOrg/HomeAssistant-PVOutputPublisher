import voluptuous as vol
from unittest.mock import patch
import pytest

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pvoutput_publisher.config_flow import _get_system_schema
from custom_components.pvoutput_publisher.const import (
    DOMAIN, CONF_API_KEY, CONF_SYSTEMS, CONF_NAME, CONF_SYSTEM_ID,
    CONF_FREQUENCY, CONF_NOTES, CONF_V1, CONF_V2, CONF_V3, CONF_V4,
    CONF_V5, CONF_V6, CONF_V7, CONF_V8, CONF_V9, CONF_V10, CONF_V11, CONF_V12,
    CONF_B1, CONF_B2, CONF_B3, CONF_B4, CONF_B5, CONF_B6,
    CONF_C1, CONF_NET, CONF_DONATION_FIELDS
)

@pytest.mark.asyncio
async def test_show_user_form(hass):
    """Test that the initial setup form is displayed correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result.get("errors") is None

@pytest.mark.asyncio
async def test_initial_setup_flow(hass):
    """Test the complete happy-path of the initial setup flow in V2."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # Submit API Key
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: "my_secret_key"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "add_system"

    # Submit First Solar System with V2 fields, notes, battery (in donation section), and flags
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "Main Array",
            CONF_SYSTEM_ID: "12345",
            CONF_FREQUENCY: "5",
            CONF_NOTES: "Roof solar panels installed 2024",
            CONF_V1: "sensor.inverter_energy",
            CONF_V2: "sensor.inverter_power",
            CONF_V6: "sensor.inverter_voltage",
            CONF_DONATION_FIELDS: {
                CONF_B1: "sensor.battery_power",
                CONF_B2: "sensor.battery_soc",
            },
            CONF_C1: True,
            CONF_NET: False,
        }
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "systems_manager"

    # Finish Setup
    with patch("custom_components.pvoutput_publisher.async_setup_entry", return_value=True) as mock_setup:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"action": "finish"}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "PVOutput Publisher"
    assert result["data"][CONF_API_KEY] == "my_secret_key"
    assert len(result["data"][CONF_SYSTEMS]) == 1

    sys = result["data"][CONF_SYSTEMS][0]
    assert sys[CONF_NAME] == "Main Array"
    assert sys[CONF_SYSTEM_ID] == "12345"
    assert sys[CONF_NOTES] == "Roof solar panels installed 2024"
    assert sys[CONF_V1] == "sensor.inverter_energy"
    assert sys[CONF_V2] == "sensor.inverter_power"
    assert sys[CONF_V6] == "sensor.inverter_voltage"
    assert sys[CONF_B1] == "sensor.battery_power"
    assert sys[CONF_B2] == "sensor.battery_soc"
    assert sys[CONF_C1] is True
    assert sys[CONF_NET] is False
    assert len(mock_setup.mock_calls) == 1


@pytest.mark.asyncio
async def test_options_flow_edit_api_key(hass):
    """Test that a user can successfully update their API key via Options flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "old_key", CONF_SYSTEMS: []},
        version=2
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "systems_manager"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"action": "edit_api"}
    )
    assert result["step_id"] == "edit_api"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "new_shiny_key"}
    )
    assert result["step_id"] == "systems_manager"

    with patch("custom_components.pvoutput_publisher.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"action": "finish"}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.data[CONF_API_KEY] == "new_shiny_key"


@pytest.mark.asyncio
async def test_options_flow_manage_systems(hass):
    """Test adding, editing, and removing solar arrays within Options flow."""
    initial_system = {
        CONF_NAME: "Original System",
        CONF_SYSTEM_ID: "111",
        CONF_FREQUENCY: "5",
        CONF_NOTES: "Initial notes",
        CONF_V2: "sensor.power_1",
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key123", CONF_SYSTEMS: [initial_system]},
        version=2
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    # --- ACTION 1: EDIT EXISTING SYSTEM ---
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"action": "edit_0"}
    )
    assert result["step_id"] == "add_system"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={
            CONF_NAME: "Updated System",
            CONF_SYSTEM_ID: "111",
            CONF_FREQUENCY: "5",
            CONF_NOTES: "Updated notes",
            CONF_V1: "sensor.energy_1",
            CONF_V2: "sensor.power_1",
            CONF_V6: "sensor.new_voltage",
            CONF_DONATION_FIELDS: {
                CONF_B1: "sensor.battery_power",
            },
            CONF_C1: True,
        }
    )
    assert result["step_id"] == "systems_manager"

    # --- ACTION 2: ADD A BRAND NEW SYSTEM ---
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"action": "add_new"}
    )
    assert result["step_id"] == "add_system"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={
            CONF_NAME: "Secondary Array",
            CONF_SYSTEM_ID: "222",
            CONF_FREQUENCY: "10",
            CONF_NOTES: "East roof",
            CONF_V2: "sensor.power_2",
            CONF_DONATION_FIELDS: {
                CONF_V7: "sensor.battery_soc",
            },
            CONF_NET: True,
        }
    )
    assert result["step_id"] == "systems_manager"

    # --- ACTION 3: REMOVE THE FIRST SYSTEM ---
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"action": "remove_0"}
    )
    assert result["step_id"] == "systems_manager"

    # --- SAVE AND VERIFY ---
    with patch("custom_components.pvoutput_publisher.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"action": "finish"}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    final_systems = entry.data[CONF_SYSTEMS]
    assert len(final_systems) == 1
    assert final_systems[0][CONF_NAME] == "Secondary Array"
    assert final_systems[0][CONF_SYSTEM_ID] == "222"
    assert final_systems[0][CONF_NOTES] == "East roof"
    assert final_systems[0][CONF_V7] == "sensor.battery_soc"
    assert final_systems[0][CONF_NET] is True


@pytest.mark.asyncio
async def test_options_flow_edit_all_fields(hass):
    """Test editing an existing system where all fields are already configured."""
    full_system = {
        CONF_NAME: "Full System",
        CONF_SYSTEM_ID: "999",
        CONF_FREQUENCY: "15",
        CONF_NOTES: "Full system notes",
        CONF_V1: "sensor.v1",
        CONF_V2: "sensor.v2",
        CONF_V3: "sensor.v3",
        CONF_V4: "sensor.v4",
        CONF_V5: "sensor.v5",
        CONF_V6: "sensor.v6",
        CONF_V7: "sensor.v7",
        CONF_V8: "sensor.v8",
        CONF_V9: "sensor.v9",
        CONF_V10: "sensor.v10",
        CONF_V11: "sensor.v11",
        CONF_V12: "sensor.v12",
        CONF_B1: "sensor.b1",
        CONF_B2: "sensor.b2",
        CONF_B3: "sensor.b3",
        CONF_B4: "sensor.b4",
        CONF_B5: "sensor.b5",
        CONF_B6: "sensor.b6",
        CONF_C1: True,
        CONF_NET: True,
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key123", CONF_SYSTEMS: [full_system]},
        version=2
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"action": "edit_0"}
    )
    assert result["step_id"] == "add_system"

    # Submit with donation fields nested as frontend sends them
    frontend_submission = {
        CONF_NAME: "Full System",
        CONF_SYSTEM_ID: "999",
        CONF_FREQUENCY: "15",
        CONF_NOTES: "Full system notes",
        CONF_V1: "sensor.v1",
        CONF_V2: "sensor.v2",
        CONF_V3: "sensor.v3",
        CONF_V4: "sensor.v4",
        CONF_V5: "sensor.v5",
        CONF_V6: "sensor.v6",
        CONF_DONATION_FIELDS: {
            CONF_V7: "sensor.v7",
            CONF_V8: "sensor.v8",
            CONF_V9: "sensor.v9",
            CONF_V10: "sensor.v10",
            CONF_V11: "sensor.v11",
            CONF_V12: "sensor.v12",
            CONF_B1: "sensor.b1",
            CONF_B2: "sensor.b2",
            CONF_B3: "sensor.b3",
            CONF_B4: "sensor.b4",
            CONF_B5: "sensor.b5",
            CONF_B6: "sensor.b6",
        },
        CONF_C1: True,
        CONF_NET: True,
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input=frontend_submission
    )
    assert result["step_id"] == "systems_manager"


@pytest.mark.asyncio
async def test_setup_with_custom_temperature_sensor(hass):
    """Test configuring a system with a custom temperature sensor without device class."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: "key123"}
    )
    # Configure system using a sensor that lacks device_class
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "Temp Test Array",
            CONF_SYSTEM_ID: "4321",
            CONF_FREQUENCY: "5",
            CONF_V2: "sensor.solar_power",
            CONF_V5: "sensor.custom_outdoor_temperature",
        }
    )
    assert result["step_id"] == "systems_manager"
    with patch("custom_components.pvoutput_publisher.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"action": "finish"}
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SYSTEMS][0][CONF_V5] == "sensor.custom_outdoor_temperature"


def test_schema_donation_section_collapsed_logic():
    """Test that donation section starts collapsed when empty, and expanded when configured."""
    # 1. Empty / new system -> collapsed = True
    empty_schema = _get_system_schema({})
    donation_sec_empty = empty_schema.schema[vol.Optional(CONF_DONATION_FIELDS)]
    assert donation_sec_empty.options["collapsed"] is True

    # 2. System with only free sensors -> collapsed = True
    free_only_schema = _get_system_schema({
        CONF_NAME: "Solar",
        CONF_V1: "sensor.energy",
        CONF_V2: "sensor.power",
        CONF_V3: "sensor.consumption",
        CONF_V4: "sensor.power_con",
        CONF_V5: "sensor.temp",
        CONF_V6: "sensor.voltage",
        CONF_C1: True,
        CONF_NET: False,
    })
    donation_sec_free = free_only_schema.schema[vol.Optional(CONF_DONATION_FIELDS)]
    assert donation_sec_free.options["collapsed"] is True

    # 3. System with each donation sensor individually -> collapsed = False
    for k in [CONF_V7, CONF_V8, CONF_V9, CONF_V10, CONF_V11, CONF_V12,
              CONF_B1, CONF_B2, CONF_B3, CONF_B4, CONF_B5, CONF_B6]:
        schema = _get_system_schema({CONF_NAME: "Solar", k: "sensor.test"})
        sec = schema.schema[vol.Optional(CONF_DONATION_FIELDS)]
        assert sec.options["collapsed"] is False, f"Expected collapsed=False when {k} is set"


@pytest.mark.asyncio
async def test_options_flow_form_section_collapse_state(hass):
    """Test that editing an existing array in options flow properly reflects collapsed/expanded state."""
    free_system = {
        CONF_NAME: "Free Array",
        CONF_SYSTEM_ID: "111",
        CONF_V1: "sensor.energy",
    }
    donation_system = {
        CONF_NAME: "Battery Array",
        CONF_SYSTEM_ID: "222",
        CONF_B1: "sensor.battery_power",
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key123", CONF_SYSTEMS: [free_system, donation_system]},
        version=2
    )
    entry.add_to_hass(hass)

    # 1. Edit free array -> donation section is collapsed
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"action": "edit_0"}
    )
    assert result["step_id"] == "add_system"
    schema = result["data_schema"]
    sec = schema.schema[vol.Optional(CONF_DONATION_FIELDS)]
    assert sec.options["collapsed"] is True

    # 2. Cancel and edit donation array -> donation section is expanded
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"action": "edit_1"}
    )
    assert result["step_id"] == "add_system"
    schema = result["data_schema"]
    sec = schema.schema[vol.Optional(CONF_DONATION_FIELDS)]
    assert sec.options["collapsed"] is False


