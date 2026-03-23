from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, CONF_SYSTEMS, CONF_SYSTEM_ID, CONF_NAME

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the sensor platform."""
    systems = entry.data.get(CONF_SYSTEMS, [])
    sensors = []

    for system in systems:
        sensors.append(PVOutputLastUpdateSensor(system))

    async_add_entities(sensors)

class PVOutputLastUpdateSensor(SensorEntity):
    """Representation of a Sensor that tracks the last successful PVOutput upload."""

    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:cloud-upload-outline"

    def __init__(self, system):
        """Initialize the sensor."""
        # Fallback to system_id if name is missing
        name = system.get(CONF_NAME, system.get(CONF_SYSTEM_ID))

        self._attr_name = f"PVOutput {name} Last Upload"
        self._attr_unique_id = f"pvoutput_last_upload_{system[CONF_SYSTEM_ID]}"
        self._sys_id = system[CONF_SYSTEM_ID]

    async def async_added_to_hass(self):
        """Run when entity about to be added to hass. Listen for updates."""
        # Connect to the dispatcher signal sent from __init__.py
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_update_{self._sys_id}",
                self._handle_update
            )
        )

    @callback
    def _handle_update(self, timestamp):
        """Update the sensor state when a successful push occurs."""
        self._attr_native_value = timestamp
        self.async_write_ha_state()
