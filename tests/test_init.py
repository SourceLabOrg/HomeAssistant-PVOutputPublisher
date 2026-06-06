"""Test the PVOutput Publisher initialization and payload generation."""
from datetime import timedelta
import logging
from unittest.mock import patch

import pytest
from aioresponses import aioresponses

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.pvoutput_publisher.const import (
    DOMAIN, CONF_API_KEY, CONF_SYSTEMS, CONF_NAME, CONF_SYSTEM_ID,
    CONF_ENTITY_ID, CONF_SECONDARY_ENTITY_ID, CONF_CONSUMPTION_ENTITY_ID,
    CONF_TEMPERATURE_ENTITY_ID, CONF_VOLTAGE_ENTITY_ID, CONF_FREQUENCY,
    PVOUTPUT_API_URL
)

# Standard mock configuration base
MOCK_API_KEY = "fake_api_key_123"
MOCK_SYSTEM_ID = "112233"

async def setup_and_trigger(hass: HomeAssistant, mock_aio: aioresponses, system_config: dict) -> str:
    """Helper function to setup the integration, trigger the timer, and return the payload."""
    config_data = {
        CONF_API_KEY: MOCK_API_KEY,
        CONF_SYSTEMS: [system_config]
    }

    entry = MockConfigEntry(domain=DOMAIN, data=config_data)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # Intercept the POST request to PVOutput
    mock_aio.post(PVOUTPUT_API_URL, status=200)

    # Force the clock to advance to the next top-of-the-hour to trigger the cron scheduler
    future = dt_util.utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    # Extract the payload that was sent to the mocked API
    post_requests = list(mock_aio.requests.values())[0]
    payload = post_requests[0].kwargs["data"]

    return payload


@pytest.mark.asyncio
async def test_setup_and_unload(hass: HomeAssistant):
    """Test that the integration sets up and unloads successfully."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "123", CONF_SYSTEMS: []})
    entry.add_to_hass(hass)

    # Test Setup
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert DOMAIN in hass.data

    # Test Unload
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.data[DOMAIN].get(entry.entry_id)


@pytest.mark.asyncio
async def test_push_data_all_sensors(hass: HomeAssistant):
    """Test payload generation when ALL optional and required sensors are configured."""
    hass.states.async_set("sensor.solar_energy", "12500", {"unit_of_measurement": "Wh", "state_class": "total_increasing"})
    hass.states.async_set("sensor.solar_power", "3500", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.home_consumption", "800", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.outside_temp", "22.5", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.grid_voltage", "240.2", {"unit_of_measurement": "V"})

    system_config = {
        CONF_NAME: "Test System",
        CONF_SYSTEM_ID: MOCK_SYSTEM_ID,
        CONF_FREQUENCY: "5",
        CONF_ENTITY_ID: "sensor.solar_energy",
        CONF_SECONDARY_ENTITY_ID: "sensor.solar_power",
        CONF_CONSUMPTION_ENTITY_ID: "sensor.home_consumption",
        CONF_TEMPERATURE_ENTITY_ID: "sensor.outside_temp",
        CONF_VOLTAGE_ENTITY_ID: "sensor.grid_voltage"
    }

    with aioresponses() as mock_aio:
        payload = await setup_and_trigger(hass, mock_aio, system_config)

    # Assertions
    assert "&c1=1" in payload     # Lifetime flag triggered
    assert "&v1=12500" in payload # Energy
    assert "&v2=3500" in payload  # Power
    assert "&v4=800" in payload   # Consumption (Power)
    assert "&v5=22.5" in payload  # Temperature
    assert "&v6=240.2" in payload # Voltage


@pytest.mark.asyncio
async def test_push_data_minimal(hass: HomeAssistant):
    """Test payload generation when ONLY the primary required sensor is configured."""
    hass.states.async_set("sensor.solar_power_only", "2000", {"unit_of_measurement": "W"})

    system_config = {
        CONF_NAME: "Test Minimal",
        CONF_SYSTEM_ID: MOCK_SYSTEM_ID,
        CONF_FREQUENCY: "5",
        CONF_ENTITY_ID: "sensor.solar_power_only",
    }

    with aioresponses() as mock_aio:
        payload = await setup_and_trigger(hass, mock_aio, system_config)

    assert "&v2=2000" in payload
    assert "&v1=" not in payload # Energy shouldn't be there
    assert "&v5=" not in payload # Temp shouldn't be there


@pytest.mark.asyncio
async def test_push_data_conversions(hass: HomeAssistant):
    """Test that units like kW, kWh, and Fahrenheit are properly converted before sending."""
    hass.states.async_set("sensor.solar_energy_kwh", "15.5", {"unit_of_measurement": "kWh"})
    hass.states.async_set("sensor.solar_power_kw", "2.5", {"unit_of_measurement": "kW"})
    hass.states.async_set("sensor.temp_f", "68", {"unit_of_measurement": "°F"})

    system_config = {
        CONF_NAME: "Test Conversions",
        CONF_SYSTEM_ID: MOCK_SYSTEM_ID,
        CONF_FREQUENCY: "5",
        CONF_ENTITY_ID: "sensor.solar_energy_kwh",
        CONF_SECONDARY_ENTITY_ID: "sensor.solar_power_kw",
        CONF_TEMPERATURE_ENTITY_ID: "sensor.temp_f",
    }

    with aioresponses() as mock_aio:
        payload = await setup_and_trigger(hass, mock_aio, system_config)

    assert "&v1=15500" in payload # 15.5 kWh -> 15500 Wh
    assert "&v2=2500" in payload  # 2.5 kW -> 2500 W
    assert "&v5=20.0" in payload  # 68 F -> 20.0 C


@pytest.mark.asyncio
async def test_push_data_duplicate_sensor_types(hass: HomeAssistant, caplog):
    """Test that the integration safely ignores the secondary sensor if both are the same type."""
    # User accidentally configured two Energy (Wh) sensors
    hass.states.async_set("sensor.energy_1", "1000", {"unit_of_measurement": "Wh"})
    hass.states.async_set("sensor.energy_2", "2000", {"unit_of_measurement": "Wh"})

    system_config = {
        CONF_NAME: "Duplicate System",
        CONF_SYSTEM_ID: MOCK_SYSTEM_ID,
        CONF_FREQUENCY: "5",
        CONF_ENTITY_ID: "sensor.energy_1",
        CONF_SECONDARY_ENTITY_ID: "sensor.energy_2",
    }

    with aioresponses() as mock_aio:
        payload = await setup_and_trigger(hass, mock_aio, system_config)

    # It should log a warning
    assert "Ignored secondary sensor. You selected two Energy (Wh) sensors." in caplog.text

    # It should only send the primary sensor data
    assert "&v1=1000" in payload
    assert "&v2=" not in payload
