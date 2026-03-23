import logging
import aiohttp
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
import homeassistant.util.dt as dt_util

from .const import (
    DOMAIN, CONF_API_KEY, CONF_SYSTEMS, CONF_SYSTEM_ID,
    CONF_ENTITY_ID, CONF_FREQUENCY, PVOUTPUT_API_URL
)

_LOGGER = logging.getLogger(__name__)

# Define the platforms this integration supports
PLATFORMS = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up PVOutput Publisher from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    api_key = entry.data[CONF_API_KEY]
    systems = entry.data.get(CONF_SYSTEMS, [])
    session = async_get_clientsession(hass)

    remove_listeners = []

    for system in systems:
        system_id = system[CONF_SYSTEM_ID]
        entity_id = system[CONF_ENTITY_ID]
        frequency = int(system[CONF_FREQUENCY])

        async def push_data(now: datetime, sys_id=system_id, ent_id=entity_id):
            state = hass.states.get(ent_id)
            if not state or state.state in ['unknown', 'unavailable']:
                return

            try:
                value = float(state.state)
            except ValueError:
                return

            unit = state.attributes.get("unit_of_measurement", "").lower()

            # Default payload structure (Date and Time)
            d = now.strftime('%Y%m%d')
            t = now.strftime('%H:%M')
            payload = f"d={d}&t={t}"

            # If it is an ENERGY sensor (Cumulative Daily Total) -> Send as v1
            if unit in ["wh", "kwh", "mwh"]:
                if unit == "kwh":
                    value = value * 1000
                elif unit == "mwh":
                    value = value * 1000000
                payload += f"&v1={int(value)}"

            # If it is a POWER sensor (Instantaneous Snapshot) -> Send as v2
            else:
                if unit in ["kw", "kilowatt", "kilowatts"]:
                    value = value * 1000
                payload += f"&v2={int(value)}"

            headers = {
                "X-Pvoutput-Apikey": api_key,
                "X-Pvoutput-SystemId": sys_id,
                "Content-Type": "application/x-www-form-urlencoded"
            }

            try:
                async with session.post(PVOUTPUT_API_URL, headers=headers, data=payload) as resp:
                    if resp.status == 200:
                        # Success! Send a signal to the sensor to update its timestamp
                        async_dispatcher_send(hass, f"{DOMAIN}_update_{sys_id}", dt_util.utcnow())
                    else:
                        text = await resp.text()
                        _LOGGER.error("PVOutput API error (%s): %s", resp.status, text)

            # Graceful error handling for network drops
            except aiohttp.ClientError as e:
                _LOGGER.warning("Network error connecting to PVOutput. Retrying next cycle. (%s)", e)
            except Exception as e:
                _LOGGER.error("Unexpected error connecting to PVOutput: %s", e)

        listener = async_track_time_interval(hass, push_data, timedelta(minutes=frequency))
        remove_listeners.append(listener)

    hass.data[DOMAIN][entry.entry_id] = remove_listeners
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Forward the setup to the sensor platform (loads sensor.py)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload the sensor platform first
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        listeners = hass.data[DOMAIN].pop(entry.entry_id, [])
        for remove_listener in listeners:
            remove_listener()

    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
