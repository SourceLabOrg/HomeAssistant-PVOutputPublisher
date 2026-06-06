"""Test the PVOutput Publisher config flow."""
from unittest.mock import patch
import pytest

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pvoutput_publisher.const import (
    DOMAIN, CONF_API_KEY, CONF_SYSTEMS, CONF_NAME, CONF_SYSTEM_ID,
    CONF_ENTITY_ID, CONF_SECONDARY_ENTITY_ID, CONF_FREQUENCY,
    CONF_VOLTAGE_ENTITY_ID
)

@pytest.mark.asyncio
async def test_show_user_form(hass):
    """Test that the initial setup form is displayed correctly."""

    # 1. Initialize the config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # 2. Assert the flow returns the expected form
    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result.get("errors") is None

@pytest.mark.asyncio
async def test_initial_setup_flow(hass):
    """Test the complete happy-path of the initial setup flow."""
    # 1. Start the Config Flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    # 2. Submit the API Key
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: "my_secret_key"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "add_system"

    # 3. Submit the First Solar System
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "Main Array",
            CONF_SYSTEM_ID: "12345",
            CONF_ENTITY_ID: "sensor.inverter_power",
            CONF_SECONDARY_ENTITY_ID: "sensor.inverter_energy",
            CONF_VOLTAGE_ENTITY_ID: "sensor.inverter_voltage",
            CONF_FREQUENCY: "5"
        }
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "systems_manager"

    # 4. Finish the Setup
    with patch("custom_components.pvoutput_publisher.async_setup_entry", return_value=True) as mock_setup:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"action": "finish"}
        )

    # 5. Verify the Final Output
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "PVOutput Publisher"

    assert result["data"][CONF_API_KEY] == "my_secret_key"
    assert len(result["data"][CONF_SYSTEMS]) == 1
    assert result["data"][CONF_SYSTEMS][0][CONF_NAME] == "Main Array"
    assert result["data"][CONF_SYSTEMS][0][CONF_VOLTAGE_ENTITY_ID] == "sensor.inverter_voltage"
    assert len(mock_setup.mock_calls) == 1


@pytest.mark.asyncio
async def test_options_flow_edit_api_key(hass):
    """Test that a user can successfully update their API key via the Options flow."""
    # 1. Create a mocked existing integration
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "old_key", CONF_SYSTEMS: []}
    )
    entry.add_to_hass(hass)

    # 2. Launch the options flow
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "systems_manager"

    # 3. Select 'Edit API Key' from the dropdown
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"action": "edit_api"}
    )
    assert result["step_id"] == "edit_api"

    # 4. Submit the new key
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_API_KEY: "new_shiny_key"}
    )
    assert result["step_id"] == "systems_manager"

    # 5. Save and close
    with patch("custom_components.pvoutput_publisher.async_setup_entry", return_value=True):
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"action": "finish"}
        )

    # Verify the underlying config entry was updated
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.data[CONF_API_KEY] == "new_shiny_key"


@pytest.mark.asyncio
async def test_options_flow_manage_systems(hass):
    """Test adding, editing, and removing solar arrays within the Options flow."""
    # 1. Create a mock integration with exactly one existing system
    initial_system = {
        CONF_NAME: "Original System",
        CONF_SYSTEM_ID: "111",
        CONF_ENTITY_ID: "sensor.power_1",
        CONF_FREQUENCY: "5"
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key123", CONF_SYSTEMS: [initial_system]}
    )
    entry.add_to_hass(hass)

    # Launch Options
    result = await hass.config_entries.options.async_init(entry.entry_id)

    # --- ACTION 1: EDIT THE EXISTING SYSTEM ---
    # Select the first system (index 0) from the dropdown
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"action": "edit_0"}
    )
    assert result["step_id"] == "add_system"

    # Submit updated data for it
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={
            CONF_NAME: "Updated System",
            CONF_SYSTEM_ID: "111",
            CONF_ENTITY_ID: "sensor.power_1",
            CONF_VOLTAGE_ENTITY_ID: "sensor.new_voltage",
            CONF_FREQUENCY: "5"
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
            CONF_ENTITY_ID: "sensor.power_2",
            CONF_FREQUENCY: "10"
        }
    )
    assert result["step_id"] == "systems_manager"

    # --- ACTION 3: REMOVE THE FIRST SYSTEM ---
    # We delete "Updated System" (which is at index 0)
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

    # After editing, adding, and removing, we should be left with ONLY the "Secondary Array"
    final_systems = entry.data[CONF_SYSTEMS]
    assert len(final_systems) == 1
    assert final_systems[0][CONF_NAME] == "Secondary Array"
    assert final_systems[0][CONF_SYSTEM_ID] == "222"
