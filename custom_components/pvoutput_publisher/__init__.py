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
    CONF_ENTITY_ID, CONF_CONSUMPTION_ENTITY_ID, CONF_TEMPERATURE_ENTITY_ID,
    CONF_FREQUENCY, PVOUTPUT_API_URL
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    api_key = entry.data[CONF_API_KEY]
    systems = entry.data.get(CONF_SYSTEMS, [])
    session = async_get_clientsession(hass)

    remove_listeners = []

    for system in systems:
        system_id = system[CONF_SYSTEM_ID]
        system_name system[CONF_NAME]
        generation_ent_id = system[CONF_ENTITY_ID]
        consumption_ent_id = system.get(CONF_CONSUMPTION_ENTITY_ID)
        temperature_ent_id = system.get(CONF_TEMPERATURE_ENTITY_ID)
        frequency = int(system[CONF_FREQUENCY])

        async def push_data(now: datetime, sys_id=system_id, gen_id=generation_ent_id, con_id=consumption_ent_id, temp_id=temperature_ent_id):
            gen_state = hass.states.get(gen_id)
            if not gen_state or gen_state.state in ['unknown', 'unavailable']:
                return

            try:
                gen_value = float(gen_state.state)
            except ValueError:
                return

            gen_unit = gen_state.attributes.get("unit_of_measurement", "").lower()

            # Get the strictly localized time from Home Assistant
            local_time = dt_util.now()
            d = local_time.strftime('%Y%m%d')
            t = local_time.strftime('%H:%M')

            payload = f"d={d}&t={t}"

            # 1. Add Generation Data (v1 / v2)
            if gen_unit in ["wh", "kwh", "mwh"]:
                if gen_unit == "kwh":
                    gen_value *= 1000
                elif gen_unit == "mwh":
                    gen_value *= 1000000
                payload += f"&v1={int(gen_value)}"
            else:
                if gen_unit in ["kw", "kilowatt", "kilowatts"]:
                    gen_value *= 1000
                payload += f"&v2={int(gen_value)}"

            # 2. Add Optional Consumption Data (v3 / v4)
            if con_id:
                con_state = hass.states.get(con_id)
                if con_state and con_state.state not in ['unknown', 'unavailable']:
                    try:
                        con_value = float(con_state.state)
                        con_unit = con_state.attributes.get("unit_of_measurement", "").lower()

                        if con_unit in ["wh", "kwh", "mwh"]:
                            if con_unit == "kwh":
                                con_value *= 1000
                            elif con_unit == "mwh":
                                con_value *= 1000000
                            payload += f"&v3={int(con_value)}"
                        else:
                            if con_unit in ["kw", "kilowatt", "kilowatts"]:
                                con_value *= 1000
                            payload += f"&v4={int(con_value)}"
                    except ValueError:
                        pass # Silently ignore invalid consumption state and continue

            # 3. Add Optional Temperature Data (v5)
            if temp_id:
                temp_state = hass.states.get(temp_id)
                if temp_state and temp_state.state not in ['unknown', 'unavailable']:
                    try:
                        temp_value = float(temp_state.state)
                        temp_unit = temp_state.attributes.get("unit_of_measurement", "").lower()

                        # PVOutput strictly expects Celsius
                        if temp_unit in ["°f", "f"]:
                            temp_value = (temp_value - 32) * 5.0 / 9.0

                        payload += f"&v5={temp_value:.1f}"
                    except ValueError:
                        pass # Silently ignore invalid temp state and continue

            headers = {
                "X-Pvoutput-Apikey": api_key,
                "X-Pvoutput-SystemId": sys_id,
                "Content-Type": "application/x-www-form-urlencoded"
            }

            try:
                async with session.post(PVOUTPUT_API_URL, headers=headers, data=payload) as resp:
                    if resp.status == 200:
                        _LOGGER.debug("Successfully pushed to PVOutput for %s (%s): %s", system_name, sys_id, payload)
                        async_dispatcher_send(hass, f"{DOMAIN}_update_{sys_id}", dt_util.utcnow())
                    else:
                        text = await resp.text()
                        _LOGGER.error("PVOutput API error for %s (%s): (%s) %s", system_name, sys_id, resp.status, text)
            except aiohttp.ClientError as e:
                _LOGGER.warning("Network error connecting to PVOutput. Retrying next cycle. System %s (%s): (%s)", system_name, sys_id, e)
            except Exception as e:
                _LOGGER.error("Unexpected error connecting to PVOutput System %s (%s): %s", system_name, sys_id, e)

        listener = async_track_time_interval(hass, push_data, timedelta(minutes=frequency))
        remove_listeners.append(listener)

    hass.data[DOMAIN][entry.entry_id] = remove_listeners
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        listeners = hass.data[DOMAIN].pop(entry.entry_id, [])
        for remove_listener in listeners:
            remove_listener()

    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
