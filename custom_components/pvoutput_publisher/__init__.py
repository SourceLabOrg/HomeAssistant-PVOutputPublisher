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
    CONF_B1, CONF_B2, CONF_B3, CONF_B4, CONF_B5, CONF_B6,
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
        # NOTE: Use (attr or "").lower() defensively because dict.get("key", "")
        # will return None if the attribute is explicitly set to None (e.g. MQTT/template sensors).
        unit = (state.attributes.get("unit_of_measurement") or "").lower()
        device_class = (state.attributes.get("device_class") or "").lower()
        state_class = (state.attributes.get("state_class") or "").lower()
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
    legacy_keys = [
        CONF_ENTITY_ID, CONF_SECONDARY_ENTITY_ID, CONF_CONSUMPTION_ENTITY_ID,
        CONF_TEMPERATURE_ENTITY_ID, CONF_VOLTAGE_ENTITY_ID
    ]
    # If not containing legacy v1 keys, return as is
    if not any(k in system for k in legacy_keys):
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
        prim_type, _ = _determine_energy_or_power(hass, prim_id)
        if prim_type == "energy":
            v1 = prim_id
            # NOTE: Home Assistant's Entity Registry stores unit_of_measurement and
            # device_class on disk, but does NOT persist state_class. Because async_migrate_entry
            # runs before other integrations initialize their live entity states at boot,
            # state_class (e.g. total_increasing) cannot be read from hass.states here.
            # In PVOutput, virtually all solar inverter energy sensors (Wh/kWh) report lifetime
            # cumulative totals. Without c1=1, PVOutput rejects lifetime values as "Energy too high".
            # We therefore default c1=True whenever an Energy sensor is migrated to v1.
            c1 = True
            if sec_id:
                sec_type, _ = _determine_energy_or_power(hass, sec_id)
                if sec_type == "power":
                    v2 = sec_id
        else:
            v2 = prim_id
            if sec_id:
                sec_type, _ = _determine_energy_or_power(hass, sec_id)
                if sec_type == "energy":
                    v1 = sec_id
                    c1 = True
    elif sec_id:
        sec_type, _ = _determine_energy_or_power(hass, sec_id)
        if sec_type == "energy":
            v1 = sec_id
            c1 = True
        else:
            v2 = sec_id

    v3 = None
    v4 = None
    if con_id:
        con_type, _ = _determine_energy_or_power(hass, con_id)
        if con_type == "energy":
            v3 = con_id
            if not v1:
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
        CONF_B1: None,
        CONF_B2: None,
        CONF_B3: None,
        CONF_B4: None,
        CONF_B5: None,
        CONF_B6: None,
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
                        # NOTE: Use (attr or "").lower() defensively because dict.get("key", "")
                        # returns None if the attribute exists with value None (common in template/MQTT sensors).
                        unit = (v1_state.attributes.get("unit_of_measurement") or "").lower()
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
                        unit = (v2_state.attributes.get("unit_of_measurement") or "").lower()
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
                        unit = (v3_state.attributes.get("unit_of_measurement") or "").lower()
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
                        unit = (v4_state.attributes.get("unit_of_measurement") or "").lower()
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
                        unit = (v5_state.attributes.get("unit_of_measurement") or "").lower()
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

            has_b1 = False
            has_other_battery = False

            # b1: Battery Power (W) (Positive = Charging, Negative = Discharging)
            b1_id = sys_data.get(CONF_B1)
            if b1_id:
                b1_state = hass.states.get(b1_id)
                if b1_state and b1_state.state not in ['unknown', 'unavailable']:
                    try:
                        b1_val = float(b1_state.state)
                        unit = (b1_state.attributes.get("unit_of_measurement") or "").lower()
                        raw = b1_val
                        if unit in ["kw", "kilowatt", "kilowatts"]:
                            b1_val *= 1000
                        payload += f"&b1={int(round(b1_val))}"
                        log_parts.append(f"b1 (Battery Power): {raw} {unit} -> {int(round(b1_val))}W")
                        has_b1 = True
                    except ValueError:
                        pass

            # b2: Battery State of Charge (%)
            b2_id = sys_data.get(CONF_B2)
            if b2_id:
                b2_state = hass.states.get(b2_id)
                if b2_state and b2_state.state not in ['unknown', 'unavailable']:
                    try:
                        b2_val = float(b2_state.state)
                        val_str = f"{b2_val:g}"
                        payload += f"&b2={val_str}"
                        log_parts.append(f"b2 (Battery SOC): {val_str}%")
                        has_other_battery = True
                    except ValueError:
                        pass

            # b3: Battery Size / Usable Capacity (Wh)
            b3_id = sys_data.get(CONF_B3)
            if b3_id:
                b3_state = hass.states.get(b3_id)
                if b3_state and b3_state.state not in ['unknown', 'unavailable']:
                    try:
                        b3_val = float(b3_state.state)
                        unit = (b3_state.attributes.get("unit_of_measurement") or "").lower()
                        raw = b3_val
                        if unit == "kwh":
                            b3_val *= 1000
                        elif unit == "mwh":
                            b3_val *= 1000000
                        payload += f"&b3={int(round(b3_val))}"
                        log_parts.append(f"b3 (Battery Size): {raw} {unit} -> {int(round(b3_val))}Wh")
                        has_other_battery = True
                    except ValueError:
                        pass

            # b4: Battery Lifetime Charge (Wh)
            b4_id = sys_data.get(CONF_B4)
            if b4_id:
                b4_state = hass.states.get(b4_id)
                if b4_state and b4_state.state not in ['unknown', 'unavailable']:
                    try:
                        b4_val = float(b4_state.state)
                        unit = (b4_state.attributes.get("unit_of_measurement") or "").lower()
                        raw = b4_val
                        if unit == "kwh":
                            b4_val *= 1000
                        elif unit == "mwh":
                            b4_val *= 1000000
                        payload += f"&b4={int(round(b4_val))}"
                        log_parts.append(f"b4 (Battery Lifetime Charge): {raw} {unit} -> {int(round(b4_val))}Wh")
                        has_other_battery = True
                    except ValueError:
                        pass

            # b5: Battery Lifetime Discharge (Wh)
            b5_id = sys_data.get(CONF_B5)
            if b5_id:
                b5_state = hass.states.get(b5_id)
                if b5_state and b5_state.state not in ['unknown', 'unavailable']:
                    try:
                        b5_val = float(b5_state.state)
                        unit = (b5_state.attributes.get("unit_of_measurement") or "").lower()
                        raw = b5_val
                        if unit == "kwh":
                            b5_val *= 1000
                        elif unit == "mwh":
                            b5_val *= 1000000
                        payload += f"&b5={int(round(b5_val))}"
                        log_parts.append(f"b5 (Battery Lifetime Discharge): {raw} {unit} -> {int(round(b5_val))}Wh")
                        has_other_battery = True
                    except ValueError:
                        pass

            # b6: Battery State (0-9)
            # PVOutput specification defines codes 0 through 9 (0=Unknown, 1=Charging, 2=Discharging, etc.).
            b6_id = sys_data.get(CONF_B6)
            if b6_id:
                b6_state = hass.states.get(b6_id)
                if b6_state and b6_state.state not in ['unknown', 'unavailable']:
                    try:
                        b6_val = int(float(b6_state.state))
                        if 0 <= b6_val <= 9:
                            payload += f"&b6={b6_val}"
                            log_parts.append(f"b6 (Battery State): {b6_val}")
                            has_other_battery = True
                        else:
                            _LOGGER.warning(
                                "PVOutput [%s | ID: %s] Battery State (b6) value %s is out of range (0-9). Omitting b6.",
                                name, sys_id, b6_val
                            )
                    except ValueError:
                        pass

            # PVOutput specification: When sending battery data, b1 is mandatory;
            # PVOutput will ignore b2-b6 if b1 is missing from the payload.
            if has_other_battery and not has_b1:
                _LOGGER.warning(
                    "PVOutput [%s | ID: %s] Battery parameters (b2-b6) were provided without b1 (Battery Power). "
                    "PVOutput requires b1 for battery data to be accepted; other battery parameters may be ignored.",
                    name, sys_id
                )

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
