"""Read One Smart Control power and energy data"""
from __future__ import annotations
from homeassistant.config_entries import ConfigEntry


from homeassistant.const import (
    POWER_WATT, DEVICE_CLASS_POWER,
    ENERGY_WATT_HOUR, DEVICE_CLASS_ENERGY
)
from homeassistant.components.sensor import STATE_CLASS_MEASUREMENT, STATE_CLASS_TOTAL, STATE_CLASS_TOTAL_INCREASING, SensorEntity
from homeassistant.core import HomeAssistant

from .onesmartentity import OneSmartEntity
from .onesmartwrapper import OneSmartWrapper

from .const import * 

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    """Set up the One Smart Control sensors"""

    wrapper = hass.data[DOMAIN][ONESMART_WRAPPER]

    cache = wrapper.get_cache()

    entities = []

    for meter in cache[COMMAND_METER]:
        entities.append(
            OneSmartSensor(
                hass,
                config_entry,
                wrapper,
                ONESMART_UPDATE_PUSH,
                meter[RPC_ID],
                meter[RPC_NAME],
                "power",
                EVENT_ENERGY_CONSUMPTION,
                POWER_WATT,
                None,
                DEVICE_CLASS_POWER,
                STATE_CLASS_MEASUREMENT
            )
        )

        entities.append(
            OneSmartSensor(
                hass,
                config_entry,
                wrapper,
                ONESMART_UPDATE_POLL,
                meter[RPC_ID],
                meter[RPC_NAME],
                "energy",
                COMMAND_ENERGY,
                ENERGY_WATT_HOUR,
                None,
                DEVICE_CLASS_ENERGY,
                STATE_CLASS_TOTAL
            )
        )

    async_add_entities(entities)
    
class OneSmartSensor(OneSmartEntity, SensorEntity):
    def __init__(
        self,
        hass,
        config_entry,
        wrapper: OneSmartWrapper,
        update_topic,
        id,
        name,
        suffix,
        source,
        unit,
        icon,
        device_class,
        state_class,
    ):
        super().__init__(hass, config_entry, wrapper, update_topic)
        self.wrapper = wrapper
        self._id = id
        self._nodeid = self.cache[COMMAND_SITE][SITE_NODEID]
        self._name = name
        self._suffix = suffix
        self._source = source
        self._unit = unit
        self._icon = icon
        self._device_class = device_class
        self._state_class = state_class

    @property
    def state(self):
        return self.cache[self._source][self._id]

    @property
    def available(self) -> bool:
        if not self._source in self.cache:
            return False
        if not self._id in self.cache[self._source]:
            return False
        return self.cache[self._source][self._id] is not None

    @property
    def unit_of_measurement(self):
        return self._unit

    @property
    def icon(self):
        return self._icon

    @property
    def device_class(self):
        return self._device_class

    @property
    def state_class(self):
        return self._state_class

    @property
    def name(self):
        return "{} {}".format(self._name, self._suffix.title())

    @property
    def unique_id(self):
        return f"{DOMAIN}-{self._nodeid}-{self._id}-{self._suffix}"