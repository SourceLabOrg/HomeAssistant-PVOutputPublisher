import logging
import aiohttp
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
import homeassistant.util.dt as dt_util

from .const import (
    DOMAIN, CONF_API_KEY, CONF_SYSTEMS, CONF_NAME, CONF_SYSTEM_ID,
    CONF_ENTITY_ID, CONF_SECONDARY_ENTITY_ID, CONF_CONSUMPTION_ENTITY_ID,
    CONF_TEMPERATURE_ENTITY_ID, CONF_FREQUENCY, PVOUTPUT_API_URL, CONF_VOLTAGE_ENTITY_ID
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
        generation_ent_id = system[CONF_ENTITY_ID]
        secondary_generation_ent_id = system.get(CONF_SECONDARY_ENTITY_ID)
        consumption_ent_id = system.get(CONF_CONSUMPTION_ENTITY_ID)
        temperature_ent_id = system.get(CONF_TEMPERATURE_ENTITY_ID)
        voltage_ent_id = system.get(CONF_VOLTAGE_ENTITY_ID)
        frequency = int(system[CONF_FREQUENCY])
        sys_name = system.get(CONF_NAME, system_id)

        # We pass loop variables as default arguments to avoid Python closure late-binding bugs
        async def push_data(now: datetime, sys_id=system_id, gen_id=generation_ent_id, sec_id=secondary_generation_ent_id, con_id=consumption_ent_id, temp_id=temperature_ent_id, volt_id=voltage_ent_id, name=sys_name):
            gen_state = hass.states.get(gen_id)
            if not gen_state or gen_state.state in ['unknown', 'unavailable']:
                return

            try:
                gen_value = float(gen_state.state)
            except ValueError:
                return

            gen_unit = gen_state.attributes.get("unit_of_measurement", "").lower()
            gen_state_class = gen_state.attributes.get("state_class", "").lower()

            # Localized time
            local_time = dt_util.now()
            d = local_time.strftime('%Y%m%d')
            t = local_time.strftime('%H:%M')
            payload = f"d={d}&t={t}"

            # This list will hold our human-readable log strings
            log_parts = []

            # Flags to prevent overwriting if user selects duplicate sensor types
            has_energy_v1 = False
            has_power_v2 = False

            # Primary Generation Data
            if gen_unit in ["wh", "kwh", "mwh"]:
                raw_gen = gen_value
                if gen_unit == "kwh":
                    gen_value *= 1000
                elif gen_unit == "mwh":
                    gen_value *= 1000000

                if gen_state_class in ["total", "total_increasing"]:
                    payload += "&c1=1"
                    log_parts.append(f"Gen1 (Lifetime): {raw_gen} {gen_unit} -> v1={int(gen_value)}")
                else:
                    log_parts.append(f"Gen1 (Daily): {raw_gen} {gen_unit} -> v1={int(gen_value)}")

                payload += f"&v1={int(gen_value)}"
                has_energy_v1 = True
            else:
                raw_gen = gen_value
                if gen_unit in ["kw", "kilowatt", "kilowatts"]:
                    gen_value *= 1000
                payload += f"&v2={int(gen_value)}"
                log_parts.append(f"Gen1 (Power): {raw_gen} {gen_unit} -> v2={int(gen_value)}")
                has_power_v2 = True

            # Secondary Generation Data (Optional)
            if sec_id:
                sec_state = hass.states.get(sec_id)
                if sec_state and sec_state.state not in ['unknown', 'unavailable']:
                    try:
                        sec_value = float(sec_state.state)
                        sec_unit = sec_state.attributes.get("unit_of_measurement", "").lower()
                        sec_state_class = sec_state.attributes.get("state_class", "").lower()
                        raw_sec = sec_value

                        if sec_unit in ["wh", "kwh", "mwh"]:
                            if has_energy_v1:
                                _LOGGER.warning("PVOutput [%s]: Ignored secondary sensor. You selected two Energy (Wh) sensors.", name)
                            else:
                                if sec_unit == "kwh":
                                    sec_value *= 1000
                                elif sec_unit == "mwh":
                                    sec_value *= 1000000

                                if sec_state_class in ["total", "total_increasing"]:
                                    payload += "&c1=1"
                                    log_parts.append(f"Gen2 (Lifetime): {raw_sec} {sec_unit} -> v1={int(sec_value)}")
                                else:
                                    log_parts.append(f"Gen2 (Daily): {raw_sec} {sec_unit} -> v1={int(sec_value)}")

                                payload += f"&v1={int(sec_value)}"
                                has_energy_v1 = True
                        else:
                            if has_power_v2:
                                _LOGGER.warning("PVOutput [%s]: Ignored secondary sensor. You selected two Power (W) sensors.", name)
                            else:
                                if sec_unit in ["kw", "kilowatt", "kilowatts"]:
                                    sec_value *= 1000
                                payload += f"&v2={int(sec_value)}"
                                log_parts.append(f"Gen2 (Power): {raw_sec} {sec_unit} -> v2={int(sec_value)}")
                                has_power_v2 = True
                    except ValueError:
                        pass

            # Add Optional Consumption Data (v3 / v4)
            if con_id:
                con_state = hass.states.get(con_id)
                if con_state and con_state.state not in ['unknown', 'unavailable']:
                    try:
                        con_value = float(con_state.state)
                        con_unit = con_state.attributes.get("unit_of_measurement", "").lower()
                        raw_con = con_value

                        if con_unit in ["wh", "kwh", "mwh"]:
                            if con_unit == "kwh":
                                con_value *= 1000
                            elif con_unit == "mwh":
                                con_value *= 1000000
                            payload += f"&v3={int(con_value)}"
                            log_parts.append(f"Con (Energy): {raw_con} {con_unit} -> v3={int(con_value)}")
                        else:
                            if con_unit in ["kw", "kilowatt", "kilowatts"]:
                                con_value *= 1000
                            payload += f"&v4={int(con_value)}"
                            log_parts.append(f"Con (Power): {raw_con} {con_unit} -> v4={int(con_value)}")
                    except ValueError:
                        pass

            # Add Optional Temperature Data (v5)
            if temp_id:
                temp_state = hass.states.get(temp_id)
                if temp_state and temp_state.state not in ['unknown', 'unavailable']:
                    try:
                        temp_value = float(temp_state.state)
                        temp_unit = temp_state.attributes.get("unit_of_measurement", "").lower()
                        raw_temp = temp_value

                        if temp_unit in ["°f", "f"]:
                            temp_value = (temp_value - 32) * 5.0 / 9.0
                            log_parts.append(f"Temp: {raw_temp}°F -> v5={temp_value:.1f}°C")
                        else:
                            log_parts.append(f"Temp: {raw_temp}°C -> v5={temp_value:.1f}°C")

                        payload += f"&v5={temp_value:.1f}"
                    except ValueError:
                        pass

            # Add Optional Voltage Data (v6)
            if volt_id:
                volt_state = hass.states.get(volt_id)
                if volt_state and volt_state.state not in ['unknown', 'unavailable']:
                    try:
                        volt_value = float(volt_state.state)
                        log_parts.append(f"Volt: {volt_value:.1f}V -> v6={volt_value:.1f}")
                        payload += f"&v6={volt_value:.1f}"
                    except ValueError:
                        pass

            # --- THE HUMAN-READABLE LOG ---
            # We use INFO so it shows up without needing to enable debug logging
            _LOGGER.info("PVOutput [%s | ID: %s] Preparing to send: %s", name, sys_id, " | ".join(log_parts))

            headers = {
                "X-Pvoutput-Apikey": api_key,
                "X-Pvoutput-SystemId": sys_id,
                "Content-Type": "application/x-www-form-urlencoded"
            }

            try:
                async with session.post(PVOUTPUT_API_URL, headers=headers, data=payload) as resp:
                    if resp.status == 200:
                        async_dispatcher_send(hass, f"{DOMAIN}_update_{sys_id}", dt_util.utcnow())
                    else:
                        text = await resp.text()
                        _LOGGER.error("PVOutput API error for %s (%s): (%s) %s", name, sys_id, resp.status, text)
            except aiohttp.ClientError as e:
                _LOGGER.warning("Network error connecting to PVOutput for %s. Retrying next cycle. (%s)", name, e)
            except Exception as e:
                _LOGGER.error("Unexpected error connecting to PVOutput for %s: %s", name, e)

        # Smart clock-aligned scheduling (Cron style)
        if frequency < 60:
            # Creates a list of exact minutes: [0, 5, 10, 15...]
            minutes = list(range(0, 60, frequency))
            listener = async_track_time_change(hass, push_data, minute=minutes, second=0)
        elif frequency == 60:
            # Every hour on the dot (xx:00:00)
            listener = async_track_time_change(hass, push_data, minute=0, second=0)
        elif frequency == 180:
            # Every 3 hours on the dot (00:00, 03:00, 06:00...)
            hours = list(range(0, 24, 3))
            listener = async_track_time_change(hass, push_data, hour=hours, minute=0, second=0)
        else:
            # Safe fallback just in case
            listener = async_track_time_change(hass, push_data, minute=list(range(0, 60, 5)), second=0)

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
