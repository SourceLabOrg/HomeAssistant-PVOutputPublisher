import logging
import aiohttp
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
import homeassistant.util.dt as dt_util

from .const import (
    DOMAIN, CONF_API_KEY, CONF_SYSTEMS, CONF_NAME, CONF_SYSTEM_ID,
    CONF_FREQUENCY, PVOUTPUT_API_URL, CONF_NOTES,
    CONF_V1, CONF_V2, CONF_V3, CONF_V4, CONF_V5, CONF_V6,
    CONF_V7, CONF_V8, CONF_V9, CONF_V10, CONF_V11, CONF_V12,
    CONF_C1, CONF_NET,
    CONF_ENTITY_ID, CONF_SECONDARY_ENTITY_ID, CONF_CONSUMPTION_ENTITY_ID,
    CONF_TEMPERATURE_ENTITY_ID, CONF_VOLTAGE_ENTITY_ID, DEFAULT_FREQUENCY
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

def _determine_energy_or_power(hass: HomeAssistant, entity_id: str | None) -> tuple[str | None, bool]:
    """Helper to detect whether an entity is energy (v1/v3) or power (v2/v4) and if lifetime."""
    if not entity_id:
        return None, False

    # 1. Try checking live state machine
    state = hass.states.get(entity_id)
    if state:
        unit = state.attributes.get("unit_of_measurement", "").lower()
        device_class = state.attributes.get("device_class", "").lower()
        state_class = state.attributes.get("state_class", "").lower()
        is_lifetime = state_class in ["total", "total_increasing"]

        if unit in ["wh", "kwh", "mwh"] or device_class == "energy":
            return "energy", is_lifetime
        if unit in ["w", "kw", "kilowatt", "kilowatts"] or device_class == "power":
            return "power", False

    # 2. Try checking Home Assistant Entity Registry
    try:
        registry = er.async_get(hass)
        entry_obj = registry.async_get(entity_id)
        if entry_obj:
            unit = (entry_obj.unit_of_measurement or "").lower()
            dc = (entry_obj.device_class or entry_obj.original_device_class or "").lower()
            if unit in ["wh", "kwh", "mwh"] or dc == "energy":
                return "energy", False
            if unit in ["w", "kw"] or dc == "power":
                return "power", False
    except Exception:
        pass

    # 3. String heuristics fallback
    lower_id = entity_id.lower()
    if any(k in lower_id for k in ["energy", "kwh", "wh", "yield", "total"]):
        return "energy", False
    if any(k in lower_id for k in ["power", "kw", "watt"]):
        return "power", False

    # Default to power if cannot determine
    return "power", False


def migrate_v1_system_to_v2(hass: HomeAssistant, system: dict) -> dict:
    """Convert a single v1 system dictionary to the v2 schema."""
    # If already in v2 format (contains v1 or v2 keys), return as is
    if CONF_V1 in system or CONF_V2 in system:
        return system

    name = system.get(CONF_NAME, system.get(CONF_SYSTEM_ID, "Solar System"))
    system_id = system.get(CONF_SYSTEM_ID, "")
    frequency = str(system.get(CONF_FREQUENCY, DEFAULT_FREQUENCY))
    notes = system.get(CONF_NOTES, "")

    prim_id = system.get(CONF_ENTITY_ID)
    sec_id = system.get(CONF_SECONDARY_ENTITY_ID)
    con_id = system.get(CONF_CONSUMPTION_ENTITY_ID)
    temp_id = system.get(CONF_TEMPERATURE_ENTITY_ID)
    volt_id = system.get(CONF_VOLTAGE_ENTITY_ID)

    v1 = None
    v2 = None
    c1 = False

    if prim_id:
        prim_type, prim_lifetime = _determine_energy_or_power(hass, prim_id)
        if prim_type == "energy":
            v1 = prim_id
            if prim_lifetime:
                c1 = True
            if sec_id:
                sec_type, _ = _determine_energy_or_power(hass, sec_id)
                if sec_type == "power":
                    v2 = sec_id
        else:
            v2 = prim_id
            if sec_id:
                sec_type, sec_lifetime = _determine_energy_or_power(hass, sec_id)
                if sec_type == "energy":
                    v1 = sec_id
                    if sec_lifetime:
                        c1 = True
    elif sec_id:
        sec_type, sec_lifetime = _determine_energy_or_power(hass, sec_id)
        if sec_type == "energy":
            v1 = sec_id
            if sec_lifetime:
                c1 = True
        else:
            v2 = sec_id

    v3 = None
    v4 = None
    if con_id:
        con_type, con_lifetime = _determine_energy_or_power(hass, con_id)
        if con_type == "energy":
            v3 = con_id
            if con_lifetime and not v1:
                c1 = True
        else:
            v4 = con_id

    return {
        CONF_NAME: name,
        CONF_SYSTEM_ID: system_id,
        CONF_FREQUENCY: frequency,
        CONF_NOTES: notes,
        CONF_V1: v1,
        CONF_V2: v2,
        CONF_V3: v3,
        CONF_V4: v4,
        CONF_V5: temp_id,
        CONF_V6: volt_id,
        CONF_V7: None,
        CONF_V8: None,
        CONF_V9: None,
        CONF_V10: None,
        CONF_V11: None,
        CONF_V12: None,
        CONF_C1: c1,
        CONF_NET: False,
    }


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry to version 2."""
    _LOGGER.info("Migrating PVOutput Publisher configuration entry from version %s to 2", config_entry.version)

    if config_entry.version == 1:
        new_data = {**config_entry.data}
        raw_systems = new_data.get(CONF_SYSTEMS, [])
        migrated_systems = [migrate_v1_system_to_v2(hass, sys) for sys in raw_systems]
        new_data[CONF_SYSTEMS] = migrated_systems

        hass.config_entries.async_update_entry(config_entry, data=new_data, version=2)
        _LOGGER.info("PVOutput Publisher migration to version 2 successful")

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    api_key = entry.data[CONF_API_KEY]
    systems = entry.data.get(CONF_SYSTEMS, [])
    session = async_get_clientsession(hass)

    remove_listeners = []

    for raw_system in systems:
        # Guarantee system is in v2 format even if migration was somehow bypassed
        system = migrate_v1_system_to_v2(hass, raw_system)

        system_id = system[CONF_SYSTEM_ID]
        frequency = int(system.get(CONF_FREQUENCY, DEFAULT_FREQUENCY))
        sys_name = system.get(CONF_NAME, system_id)

        # We pass loop variables as default arguments to avoid Python closure late-binding bugs
        async def push_data(now: datetime, sys_data=system, sys_id=system_id, name=sys_name):
            # Localized time
            local_time = dt_util.now()
            d = local_time.strftime('%Y%m%d')
            t = local_time.strftime('%H:%M')
            payload = f"d={d}&t={t}"
            log_parts = []

            # v1: Energy Generation (Wh)
            v1_id = sys_data.get(CONF_V1)
            if v1_id:
                v1_state = hass.states.get(v1_id)
                if v1_state and v1_state.state not in ['unknown', 'unavailable']:
                    try:
                        v1_val = float(v1_state.state)
                        unit = v1_state.attributes.get("unit_of_measurement", "").lower()
                        raw = v1_val
                        if unit == "kwh":
                            v1_val *= 1000
                        elif unit == "mwh":
                            v1_val *= 1000000
                        payload += f"&v1={int(v1_val)}"
                        log_parts.append(f"v1 (Energy Gen): {raw} {unit} -> {int(v1_val)}Wh")
                    except ValueError:
                        pass

            # v2: Power Generation (W)
            v2_id = sys_data.get(CONF_V2)
            if v2_id:
                v2_state = hass.states.get(v2_id)
                if v2_state and v2_state.state not in ['unknown', 'unavailable']:
                    try:
                        v2_val = float(v2_state.state)
                        unit = v2_state.attributes.get("unit_of_measurement", "").lower()
                        raw = v2_val
                        if unit in ["kw", "kilowatt", "kilowatts"]:
                            v2_val *= 1000
                        payload += f"&v2={int(v2_val)}"
                        log_parts.append(f"v2 (Power Gen): {raw} {unit} -> {int(v2_val)}W")
                    except ValueError:
                        pass

            # v3: Energy Consumption (Wh)
            v3_id = sys_data.get(CONF_V3)
            if v3_id:
                v3_state = hass.states.get(v3_id)
                if v3_state and v3_state.state not in ['unknown', 'unavailable']:
                    try:
                        v3_val = float(v3_state.state)
                        unit = v3_state.attributes.get("unit_of_measurement", "").lower()
                        raw = v3_val
                        if unit == "kwh":
                            v3_val *= 1000
                        elif unit == "mwh":
                            v3_val *= 1000000
                        payload += f"&v3={int(v3_val)}"
                        log_parts.append(f"v3 (Energy Con): {raw} {unit} -> {int(v3_val)}Wh")
                    except ValueError:
                        pass

            # v4: Power Consumption (W)
            v4_id = sys_data.get(CONF_V4)
            if v4_id:
                v4_state = hass.states.get(v4_id)
                if v4_state and v4_state.state not in ['unknown', 'unavailable']:
                    try:
                        v4_val = float(v4_state.state)
                        unit = v4_state.attributes.get("unit_of_measurement", "").lower()
                        raw = v4_val
                        if unit in ["kw", "kilowatt", "kilowatts"]:
                            v4_val *= 1000
                        payload += f"&v4={int(v4_val)}"
                        log_parts.append(f"v4 (Power Con): {raw} {unit} -> {int(v4_val)}W")
                    except ValueError:
                        pass

            # v5: Temperature (°C)
            v5_id = sys_data.get(CONF_V5)
            if v5_id:
                v5_state = hass.states.get(v5_id)
                if v5_state and v5_state.state not in ['unknown', 'unavailable']:
                    try:
                        temp_val = float(v5_state.state)
                        unit = v5_state.attributes.get("unit_of_measurement", "").lower()
                        raw = temp_val
                        if unit in ["°f", "f"]:
                            temp_val = (temp_val - 32) * 5.0 / 9.0
                            log_parts.append(f"v5 (Temp): {raw}°F -> {temp_val:.1f}°C")
                        else:
                            log_parts.append(f"v5 (Temp): {raw}°C -> {temp_val:.1f}°C")
                        payload += f"&v5={temp_val:.1f}"
                    except ValueError:
                        pass

            # v6: Voltage (V)
            v6_id = sys_data.get(CONF_V6)
            if v6_id:
                volt_state = hass.states.get(v6_id)
                if volt_state and volt_state.state not in ['unknown', 'unavailable']:
                    try:
                        volt_val = float(volt_state.state)
                        log_parts.append(f"v6 (Volt): {volt_val:.1f}V")
                        payload += f"&v6={volt_val:.1f}"
                    except ValueError:
                        pass

            # v7 to v12: Extended Metrics
            for v_key in [CONF_V7, CONF_V8, CONF_V9, CONF_V10, CONF_V11, CONF_V12]:
                ext_id = sys_data.get(v_key)
                if ext_id:
                    ext_state = hass.states.get(ext_id)
                    if ext_state and ext_state.state not in ['unknown', 'unavailable']:
                        try:
                            ext_val = float(ext_state.state)
                            val_str = f"{ext_val:g}"
                            payload += f"&{v_key}={val_str}"
                            log_parts.append(f"{v_key}: {val_str}")
                        except ValueError:
                            pass

            # Flags: c1 (Cumulative) and n (Net)
            if sys_data.get(CONF_C1):
                payload += "&c1=1"
                log_parts.append("c1=1 (Cumulative)")

            if sys_data.get(CONF_NET):
                payload += "&n=1"
                log_parts.append("n=1 (Net)")

            # Do not push if no metrics are present
            if not log_parts:
                return

            # Human-readable info log
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
            minutes = list(range(0, 60, frequency))
            listener = async_track_time_change(hass, push_data, minute=minutes, second=0)
        elif frequency == 60:
            listener = async_track_time_change(hass, push_data, minute=0, second=0)
        elif frequency == 180:
            hours = list(range(0, 24, 3))
            listener = async_track_time_change(hass, push_data, hour=hours, minute=0, second=0)
        else:
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
