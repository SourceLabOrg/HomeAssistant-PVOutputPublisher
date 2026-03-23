import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    DOMAIN, CONF_API_KEY, CONF_SYSTEMS, CONF_SYSTEM_ID,
    CONF_ENTITY_ID, CONF_FREQUENCY, PVOUTPUT_API_URL
)

_LOGGER = logging.getLogger(__name__)

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
        frequency = system[CONF_FREQUENCY]

        async def push_data(now: datetime, sys_id=system_id, ent_id=entity_id):
            state = hass.states.get(ent_id)
            if not state or state.state in ['unknown', 'unavailable']:
                _LOGGER.warning("Entity %s is unavailable. Skipping push.", ent_id)
                return

            try:
                # PVOutput expects an integer. We cast to float first.
                value = float(state.state)
            except ValueError:
                _LOGGER.error("Entity %s has non-numeric state: %s", ent_id, state.state)
                return

            # Dynamically check for Kilowatts and convert to Watts
            unit = state.attributes.get("unit_of_measurement", "").lower()
            if unit in ["kw", "kilowatt", "kilowatts"]:
                value = value * 1000

            # Convert to final integer for PVOutput
            value = int(value)

            # Format strictly for PVOutput requirements
            d = now.strftime('%Y%m%d')
            t = now.strftime('%H:%M')
            payload = f"d={d}&t={t}&v2={value}"

            headers = {
                "X-Pvoutput-Apikey": api_key,
                "X-Pvoutput-SystemId": sys_id,
                "Content-Type": "application/x-www-form-urlencoded"
            }

            try:
                async with session.post(PVOUTPUT_API_URL, headers=headers, data=payload) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        _LOGGER.error("PVOutput API error (%s): %s", resp.status, text)
            except Exception as e:
                _LOGGER.error("Failed to connect to PVOutput: %s", e)

        # Register the timer and save the cleanup function
        listener = async_track_time_interval(
            hass,
            push_data,
            timedelta(minutes=frequency)
        )
        remove_listeners.append(listener)

    # Store listeners so we can clean them up if the user deletes the integration
    hass.data[DOMAIN][entry.entry_id] = remove_listeners

    # This listens for the user clicking "Submit" in the Options Flow
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    listeners = hass.data[DOMAIN].pop(entry.entry_id, [])
    for remove_listener in listeners:
        remove_listener()
    return True

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
