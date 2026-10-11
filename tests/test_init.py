"""Test the PVOutput Publisher initialization, migration, and payload generation."""
from datetime import timedelta
import logging
from unittest.mock import patch, MagicMock
import pytest
import aiohttp
from aioresponses import aioresponses
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.pvoutput_publisher import (
    async_migrate_entry,
    migrate_v1_system_to_v2,
    _determine_energy_or_power
)
from custom_components.pvoutput_publisher.const import (
    DOMAIN, CONF_API_KEY, CONF_SYSTEMS, CONF_NAME, CONF_SYSTEM_ID,
    CONF_FREQUENCY, CONF_NOTES, CONF_V1, CONF_V2, CONF_V3, CONF_V4,
    CONF_V5, CONF_V6, CONF_V7, CONF_V8, CONF_V9, CONF_V10, CONF_V11, CONF_V12,
    CONF_C1, CONF_NET, CONF_ENTITY_ID, CONF_SECONDARY_ENTITY_ID,
    CONF_CONSUMPTION_ENTITY_ID, CONF_TEMPERATURE_ENTITY_ID, CONF_VOLTAGE_ENTITY_ID,
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

    entry = MockConfigEntry(domain=DOMAIN, data=config_data, version=2)
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
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "123", CONF_SYSTEMS: []}, version=2)
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
async def test_push_data_all_sensors_v2(hass: HomeAssistant):
    """Test payload generation with all V2 sensors, extended metrics, and flags."""
    hass.states.async_set("sensor.solar_energy", "12500", {"unit_of_measurement": "Wh"})
    hass.states.async_set("sensor.solar_power", "3500", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.home_energy", "4500", {"unit_of_measurement": "Wh"})
    hass.states.async_set("sensor.home_power", "800", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.outside_temp", "22.5", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.grid_voltage", "240.2", {"unit_of_measurement": "V"})
    hass.states.async_set("sensor.battery_soc", "88.5", {})
    hass.states.async_set("sensor.ext_8", "12", {})
    hass.states.async_set("sensor.ext_9", "34", {})
    hass.states.async_set("sensor.ext_10", "56", {})
    hass.states.async_set("sensor.ext_11", "78", {})
    hass.states.async_set("sensor.ext_12", "90", {})

    system_config = {
        CONF_NAME: "Test System",
        CONF_SYSTEM_ID: MOCK_SYSTEM_ID,
        CONF_FREQUENCY: "5",
        CONF_NOTES: "Internal array notes",
        CONF_V1: "sensor.solar_energy",
        CONF_V2: "sensor.solar_power",
        CONF_V3: "sensor.home_energy",
        CONF_V4: "sensor.home_power",
        CONF_V5: "sensor.outside_temp",
        CONF_V6: "sensor.grid_voltage",
        CONF_V7: "sensor.battery_soc",
        CONF_V8: "sensor.ext_8",
        CONF_V9: "sensor.ext_9",
        CONF_V10: "sensor.ext_10",
        CONF_V11: "sensor.ext_11",
        CONF_V12: "sensor.ext_12",
        CONF_C1: True,
        CONF_NET: True,
    }

    with aioresponses() as mock_aio:
        payload = await setup_and_trigger(hass, mock_aio, system_config)

    # Assertions
    assert "&v1=12500" in payload # Energy Gen
    assert "&v2=3500" in payload  # Power Gen
    assert "&v3=4500" in payload  # Energy Con
    assert "&v4=800" in payload   # Power Con
    assert "&v5=22.5" in payload  # Temperature
    assert "&v6=240.2" in payload # Voltage
    assert "&v7=88.5" in payload  # Extended 1
    assert "&v8=12" in payload
    assert "&v9=34" in payload
    assert "&v10=56" in payload
    assert "&v11=78" in payload
    assert "&v12=90" in payload
    assert "&c1=1" in payload     # Lifetime flag
    assert "&n=1" in payload      # Net flag
    assert "Internal array notes" not in payload # Notes must NOT be sent to API


@pytest.mark.asyncio
async def test_push_data_conversions_and_scaling(hass: HomeAssistant):
    """Test that units like kW, kWh, MWh, and Fahrenheit are properly converted before sending."""
    hass.states.async_set("sensor.solar_energy_kwh", "15.5", {"unit_of_measurement": "kWh"})
    hass.states.async_set("sensor.solar_power_kw", "2.5", {"unit_of_measurement": "kW"})
    hass.states.async_set("sensor.consumption_mwh", "0.02", {"unit_of_measurement": "MWh"})
    hass.states.async_set("sensor.consumption_kw", "1.2", {"unit_of_measurement": "kilowatt"})
    hass.states.async_set("sensor.temp_f", "68", {"unit_of_measurement": "°F"})

    system_config = {
        CONF_NAME: "Test Conversions",
        CONF_SYSTEM_ID: MOCK_SYSTEM_ID,
        CONF_FREQUENCY: "5",
        CONF_V1: "sensor.solar_energy_kwh",
        CONF_V2: "sensor.solar_power_kw",
        CONF_V3: "sensor.consumption_mwh",
        CONF_V4: "sensor.consumption_kw",
        CONF_V5: "sensor.temp_f",
    }

    with aioresponses() as mock_aio:
        payload = await setup_and_trigger(hass, mock_aio, system_config)

    assert "&v1=15500" in payload  # 15.5 kWh -> 15500 Wh
    assert "&v2=2500" in payload   # 2.5 kW -> 2500 W
    assert "&v3=20000" in payload  # 0.02 MWh -> 20000 Wh
    assert "&v4=1200" in payload   # 1.2 kW -> 1200 W
    assert "&v5=20.0" in payload   # 68°F -> 20.0°C


@pytest.mark.asyncio
async def test_push_data_minimal(hass: HomeAssistant):
    """Test payload generation when ONLY power generation is configured."""
    hass.states.async_set("sensor.solar_power_only", "2000", {"unit_of_measurement": "W"})

    system_config = {
        CONF_NAME: "Test Minimal",
        CONF_SYSTEM_ID: MOCK_SYSTEM_ID,
        CONF_FREQUENCY: "5",
        CONF_V2: "sensor.solar_power_only",
    }

    with aioresponses() as mock_aio:
        payload = await setup_and_trigger(hass, mock_aio, system_config)

    assert "&v2=2000" in payload
    assert "&v1=" not in payload
    assert "&v5=" not in payload


@pytest.mark.asyncio
async def test_api_error_response(hass: HomeAssistant, caplog):
    """Test that the integration gracefully handles a non-200 response from PVOutput."""
    hass.states.async_set("sensor.solar_power", "2000", {"unit_of_measurement": "W"})

    system_config = {
        CONF_NAME: "Error System",
        CONF_SYSTEM_ID: MOCK_SYSTEM_ID,
        CONF_FREQUENCY: "5",
        CONF_V2: "sensor.solar_power",
    }

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: MOCK_API_KEY, CONF_SYSTEMS: [system_config]}, version=2)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with aioresponses() as mock_aio:
        mock_aio.post(PVOUTPUT_API_URL, status=400, body="Bad Request: Invalid System ID")

        future = dt_util.utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    assert "PVOutput API error for Error System" in caplog.text
    assert "Bad Request: Invalid System ID" in caplog.text


@pytest.mark.asyncio
async def test_network_connection_error(hass: HomeAssistant, caplog):
    """Test that the integration survives a network connection failure."""
    hass.states.async_set("sensor.solar_power", "2000", {"unit_of_measurement": "W"})

    system_config = {
        CONF_NAME: "Offline System",
        CONF_SYSTEM_ID: MOCK_SYSTEM_ID,
        CONF_FREQUENCY: "5",
        CONF_V2: "sensor.solar_power",
    }

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: MOCK_API_KEY, CONF_SYSTEMS: [system_config]}, version=2)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with aioresponses() as mock_aio:
        mock_aio.post(PVOUTPUT_API_URL, exception=aiohttp.ClientConnectionError("Connection refused"))

        future = dt_util.utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

    assert "Network error connecting to PVOutput for Offline System" in caplog.text


@pytest.mark.asyncio
async def test_unavailable_sensors_skip_push(hass: HomeAssistant):
    """Test that uploads are skipped entirely if configured sensors are offline or empty."""
    hass.states.async_set("sensor.solar_power", "unavailable")

    system_config = {
        CONF_NAME: "Unavailable System",
        CONF_SYSTEM_ID: MOCK_SYSTEM_ID,
        CONF_FREQUENCY: "5",
        CONF_V2: "sensor.solar_power",
    }

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: MOCK_API_KEY, CONF_SYSTEMS: [system_config]}, version=2)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with aioresponses() as mock_aio:
        mock_aio.post(PVOUTPUT_API_URL, status=200)

        future = dt_util.utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        post_requests = mock_aio.requests.get(("POST", PVOUTPUT_API_URL))

    assert post_requests is None


# ===================== MIGRATION TESTS =====================

@pytest.mark.asyncio
async def test_async_migrate_entry_v1_to_v2_with_live_states(hass: HomeAssistant):
    """Test migration from v1 to v2 with active state machine."""
    # Set up states
    hass.states.async_set("sensor.inverter_energy", "1000", {"unit_of_measurement": "kWh", "state_class": "total_increasing"})
    hass.states.async_set("sensor.inverter_power", "3000", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.house_energy", "500", {"unit_of_measurement": "kWh"})
    hass.states.async_set("sensor.temp", "25", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.volts", "230", {"unit_of_measurement": "V"})

    v1_system = {
        CONF_NAME: "Legacy System",
        CONF_SYSTEM_ID: "55555",
        CONF_ENTITY_ID: "sensor.inverter_energy",
        CONF_SECONDARY_ENTITY_ID: "sensor.inverter_power",
        CONF_CONSUMPTION_ENTITY_ID: "sensor.house_energy",
        CONF_TEMPERATURE_ENTITY_ID: "sensor.temp",
        CONF_VOLTAGE_ENTITY_ID: "sensor.volts",
        CONF_FREQUENCY: "5",
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "migrated_key", CONF_SYSTEMS: [v1_system]},
        version=1
    )
    entry.add_to_hass(hass)

    result = await async_migrate_entry(hass, entry)
    assert result is True
    assert entry.version == 2

    migrated = entry.data[CONF_SYSTEMS][0]
    assert migrated[CONF_NAME] == "Legacy System"
    assert migrated[CONF_SYSTEM_ID] == "55555"
    assert migrated[CONF_V1] == "sensor.inverter_energy"
    assert migrated[CONF_V2] == "sensor.inverter_power"
    assert migrated[CONF_V3] == "sensor.house_energy"
    assert migrated[CONF_V4] is None
    assert migrated[CONF_V5] == "sensor.temp"
    assert migrated[CONF_V6] == "sensor.volts"
    assert migrated[CONF_C1] is True  # total_increasing set c1=True
    assert migrated[CONF_NET] is False
    assert migrated[CONF_NOTES] == ""


@pytest.mark.asyncio
async def test_async_migrate_entry_v1_power_primary(hass: HomeAssistant):
    """Test migration when primary sensor is power and secondary is energy."""
    hass.states.async_set("sensor.sol_pwr", "4000", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.sol_eng", "12000", {"unit_of_measurement": "Wh"})

    v1_system = {
        CONF_NAME: "Power First System",
        CONF_SYSTEM_ID: "66666",
        CONF_ENTITY_ID: "sensor.sol_pwr",
        CONF_SECONDARY_ENTITY_ID: "sensor.sol_eng",
        CONF_FREQUENCY: "10",
    }

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "key", CONF_SYSTEMS: [v1_system]},
        version=1
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True
    assert entry.version == 2

    migrated = entry.data[CONF_SYSTEMS][0]
    assert migrated[CONF_V2] == "sensor.sol_pwr"
    assert migrated[CONF_V1] == "sensor.sol_eng"


@pytest.mark.asyncio
async def test_determine_energy_or_power_fallbacks(hass: HomeAssistant):
    """Test helper entity determination fallback to entity registry and heuristics."""
    # Test None / empty
    assert _determine_energy_or_power(hass, None) == (None, False)
    assert _determine_energy_or_power(hass, "") == (None, False)

    # Test entity registry lookup
    entity_reg = er.async_get(hass)
    entity_reg.async_get_or_create(
        "sensor", "test", "solar_reg_energy",
        original_device_class="energy",
        unit_of_measurement="kWh"
    )
    assert _determine_energy_or_power(hass, "sensor.test_solar_reg_energy") == ("energy", False)

    entity_reg.async_get_or_create(
        "sensor", "test", "solar_reg_power",
        original_device_class="power",
        unit_of_measurement="kW"
    )
    assert _determine_energy_or_power(hass, "sensor.test_solar_reg_power") == ("power", False)

    # Test string heuristic fallback
    assert _determine_energy_or_power(hass, "sensor.my_custom_daily_yield") == ("energy", False)
    assert _determine_energy_or_power(hass, "sensor.inverter_power_kw") == ("power", False)


@pytest.mark.asyncio
async def test_migrate_already_v2_system(hass: HomeAssistant):
    """Test that migrating an already v2 system is a no-op."""
    v2_system = {
        CONF_NAME: "V2 System",
        CONF_SYSTEM_ID: "777",
        CONF_V1: "sensor.energy",
        CONF_V2: "sensor.power",
    }
    migrated = migrate_v1_system_to_v2(hass, v2_system)
    assert migrated == v2_system


@pytest.mark.asyncio
async def test_push_data_with_invalid_sensor_values(hass: HomeAssistant):
    """Test that non-numeric sensor values are gracefully ignored."""
    hass.states.async_set("sensor.bad_v1", "not_a_number", {"unit_of_measurement": "kWh"})
    hass.states.async_set("sensor.bad_v2", "invalid", {"unit_of_measurement": "kW"})
    hass.states.async_set("sensor.bad_v3", "nan", {"unit_of_measurement": "kWh"})
    hass.states.async_set("sensor.bad_v4", "abc", {"unit_of_measurement": "kW"})
    hass.states.async_set("sensor.bad_v5", "err", {"unit_of_measurement": "°C"})
    hass.states.async_set("sensor.bad_v6", "none", {})
    hass.states.async_set("sensor.bad_v7", "xyz", {})
    hass.states.async_set("sensor.good_v2", "1500", {"unit_of_measurement": "W"})

    system_config = {
        CONF_NAME: "Invalid Value System",
        CONF_SYSTEM_ID: MOCK_SYSTEM_ID,
        CONF_FREQUENCY: "5",
        CONF_V1: "sensor.bad_v1",
        CONF_V2: "sensor.bad_v2",
        CONF_V3: "sensor.bad_v3",
        CONF_V4: "sensor.bad_v4",
        CONF_V5: "sensor.bad_v5",
        CONF_V6: "sensor.bad_v6",
        CONF_V7: "sensor.bad_v7",
    }

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: MOCK_API_KEY, CONF_SYSTEMS: [system_config]}, version=2)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    with aioresponses() as mock_aio:
        mock_aio.post(PVOUTPUT_API_URL, status=200)

        future = dt_util.utcnow().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()

        post_requests = mock_aio.requests.get(("POST", PVOUTPUT_API_URL))

    # All sensors were invalid strings, so nothing should be posted
    assert post_requests is None


@pytest.mark.asyncio
async def test_frequency_scheduling_options(hass: HomeAssistant):
    """Test setup with 60 minute, 180 minute, and fallback frequencies."""
    systems = [
        {CONF_NAME: "Hourly", CONF_SYSTEM_ID: "1", CONF_FREQUENCY: "60", CONF_V2: "sensor.pwr"},
        {CONF_NAME: "Three Hourly", CONF_SYSTEM_ID: "2", CONF_FREQUENCY: "180", CONF_V2: "sensor.pwr"},
        {CONF_NAME: "Fallback", CONF_SYSTEM_ID: "3", CONF_FREQUENCY: "999", CONF_V2: "sensor.pwr"},
    ]
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: MOCK_API_KEY, CONF_SYSTEMS: systems}, version=2)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.data[DOMAIN][entry.entry_id]) == 3


@pytest.mark.asyncio
async def test_async_migrate_entry_duplicate_energy_sensors(hass: HomeAssistant):
    """Test migration when user mistakenly configured two energy sensors."""
    hass.states.async_set("sensor.sol_eng_1", "5000", {"unit_of_measurement": "Wh"})
    hass.states.async_set("sensor.sol_eng_2", "10000", {"unit_of_measurement": "Wh"})

    v1_system = {
        CONF_NAME: "Duplicate Energy System",
        CONF_SYSTEM_ID: "888",
        CONF_ENTITY_ID: "sensor.sol_eng_1",
        CONF_SECONDARY_ENTITY_ID: "sensor.sol_eng_2",
        CONF_FREQUENCY: "5",
    }

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key", CONF_SYSTEMS: [v1_system]}, version=1)
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True
    migrated = entry.data[CONF_SYSTEMS][0]
    # Primary is energy -> v1, secondary energy is ignored (v2 is None)
    assert migrated[CONF_V1] == "sensor.sol_eng_1"
    assert migrated[CONF_V2] is None
    assert migrated[CONF_C1] is True


@pytest.mark.asyncio
async def test_async_migrate_entry_duplicate_power_sensors(hass: HomeAssistant):
    """Test migration when user mistakenly configured two power sensors."""
    hass.states.async_set("sensor.sol_pwr_1", "3000", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.sol_pwr_2", "2000", {"unit_of_measurement": "W"})

    v1_system = {
        CONF_NAME: "Duplicate Power System",
        CONF_SYSTEM_ID: "999",
        CONF_ENTITY_ID: "sensor.sol_pwr_1",
        CONF_SECONDARY_ENTITY_ID: "sensor.sol_pwr_2",
        CONF_FREQUENCY: "5",
    }

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key", CONF_SYSTEMS: [v1_system]}, version=1)
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True
    migrated = entry.data[CONF_SYSTEMS][0]
    # Primary is power -> v2, secondary power is ignored (v1 is None)
    assert migrated[CONF_V2] == "sensor.sol_pwr_1"
    assert migrated[CONF_V1] is None
    assert migrated[CONF_C1] is False


@pytest.mark.asyncio
async def test_async_migrate_entry_secondary_only(hass: HomeAssistant):
    """Test migration when entity_id is missing but secondary_entity_id exists."""
    hass.states.async_set("sensor.sec_energy", "8000", {"unit_of_measurement": "Wh", "state_class": "total_increasing"})

    v1_system = {
        CONF_NAME: "Secondary Only System",
        CONF_SYSTEM_ID: "1010",
        CONF_SECONDARY_ENTITY_ID: "sensor.sec_energy",
        CONF_FREQUENCY: "5",
    }

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key", CONF_SYSTEMS: [v1_system]}, version=1)
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True
    migrated = entry.data[CONF_SYSTEMS][0]
    assert migrated[CONF_V1] == "sensor.sec_energy"
    assert migrated[CONF_V2] is None
    assert migrated[CONF_C1] is True


@pytest.mark.asyncio
async def test_async_migrate_entry_consumption_lifetime_flag(hass: HomeAssistant):
    """Test that consumption lifetime sensor sets c1=True when no generation sensor is present."""
    hass.states.async_set("sensor.con_lifetime", "15000", {"unit_of_measurement": "kWh", "state_class": "total_increasing"})

    v1_system = {
        CONF_NAME: "Consumption Only",
        CONF_SYSTEM_ID: "2020",
        CONF_CONSUMPTION_ENTITY_ID: "sensor.con_lifetime",
        CONF_FREQUENCY: "5",
    }

    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key", CONF_SYSTEMS: [v1_system]}, version=1)
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True
    migrated = entry.data[CONF_SYSTEMS][0]
    assert migrated[CONF_V3] == "sensor.con_lifetime"
    assert migrated[CONF_C1] is True


