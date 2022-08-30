"""Read One Smart Control power and energy data"""
from __future__ import annotations
from homeassistant.config_entries import ConfigEntry


from homeassistant.const import (
    POWER_WATT, 
    ENERGY_WATT_HOUR,
    ATTR_IDENTIFIERS, ATTR_DEFAULT_NAME, ATTR_SW_VERSION, ATTR_VIA_DEVICE,
    ATTR_UNIT_OF_MEASUREMENT, ATTR_DEVICE_CLASS, ATTR_NAME, CONF_PLATFORM, Platform
)
from homeassistant.components.sensor import (
    SensorDeviceClass, SensorStateClass,
    ATTR_STATE_CLASS,
    SensorEntity
)
from homeassistant.core import HomeAssistant

from .onesmartentity import OneSmartEntity
from .onesmartwrapper import OneSmartWrapper

from .const import * 

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the One Smart Control sensors"""

    wrapper: OneSmartWrapper = hass.data[DOMAIN][entry.entry_id][ONESMART_WRAPPER]

    cache = wrapper.get_cache()

    entities = []

    # Meter sensors (Energy & Power)
    for meter in cache[(COMMAND_METER,ACTION_LIST)]:
        entities.append(
            OneSmartSensor(
                hass,
                entry,
                wrapper,
                ONESMART_UPDATE_PUSH,
                meter[RPC_ID],
                meter[RPC_NAME],
                "power",
                EVENT_ENERGY_CONSUMPTION,
                None,
                POWER_WATT,
                None,
                SensorDeviceClass.POWER,
                SensorStateClass.MEASUREMENT
            )
        )

        entities.append(
            OneSmartSensor(
                hass,
                entry,
                wrapper,
                ONESMART_UPDATE_POLL,
                meter[RPC_ID],
                meter[RPC_NAME],
                "energy",
                (COMMAND_ENERGY,ACTION_TOTAL),
                None,
                ENERGY_WATT_HOUR,
                None,
                SensorDeviceClass.ENERGY,
                SensorStateClass.TOTAL
            )
        )

    # Site sensors
    entities.append(
        OneSmartSensor(
            hass,
            entry,
            wrapper,
            ONESMART_UPDATE_PUSH,
            "mode",
            "System Mode",
            None,
            EVENT_SITE_UPDATE,
            None,
            None,
            "mdi:home-account",
            None,
            None
        )
    )

    # Device sensors
    devices_attributes = wrapper.get_apparatus_attributes()
    devices = cache[(COMMAND_DEVICE,ACTION_LIST)]

    for device_id in devices_attributes:
        device = devices[device_id]
        device_name = device[RPC_NAME]
        attributes = devices_attributes[device_id]
        for attribute_name in attributes:
            attribute = attributes[attribute_name]

            if(attribute[CONF_PLATFORM] == Platform.SENSOR):
                required_attributes = [
                    ATTR_UNIT_OF_MEASUREMENT, ATTR_DEVICE_CLASS, ATTR_STATE_CLASS
                ]

                for required_attribute in required_attributes:
                    if not required_attribute in attribute:
                        attribute[required_attribute] = None

                entities.append(
                    OneSmartSensor(
                        hass,
                        entry,
                        wrapper,
                        ONESMART_UPDATE_APPARATUS,
                        f"{device_id}.{attribute_name}",
                        f"{device_name} {attribute_name.replace('_',' ').title()}",
                        None,
                        (COMMAND_APPARATUS,ACTION_GET),
                        device_id,
                        attribute[ATTR_UNIT_OF_MEASUREMENT],
                        None,
                        attribute[ATTR_DEVICE_CLASS],
                        attribute[ATTR_STATE_CLASS]
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
        key,
        name,
        suffix,
        source,
        device_id,
        unit,
        icon,
        device_class,
        state_class,
    ):
        super().__init__(hass, config_entry, wrapper, update_topic)
        self.wrapper = wrapper
        self._key = key
        if device_id != None:
            self._device_id = device_id
            devices = self.cache[(COMMAND_DEVICE,ACTION_LIST)]
            self._device = devices[device_id]
        else:
            self._device_id = self.cache[(COMMAND_SITE,ACTION_GET)][SITE_NODEID]
        self._name = name
        self._suffix = suffix
        self._source = source
        self._unit = unit
        self._icon = icon
        self._device_class = device_class
        self._state_class = state_class

    @property
    def state(self):
        return self.get_cache_value(self._key)

    @property
    def available(self) -> bool:
        if not self._source in self.cache:
            return False
        
        value = self.get_cache_value(self._key)
        return value is not None

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
        if self._suffix != None:
            return f"{self._name} {self._suffix.title()}"
        else:
            return self._name

    @property
    def unique_id(self):
        if self._suffix != None:
            return f"{DOMAIN}-{self._device_id}-{self._key}-{self._suffix}"
        else:
            return f"{DOMAIN}-{self._device_id}-{self._key}"

    @property
    def device_info(self):
        site = self.cache[(COMMAND_SITE,ACTION_GET)]
        if self._device_id == site[SITE_NODEID]:
            identifiers = {(DOMAIN, site[SITE_MAC]), (DOMAIN, self._device_id)}
            device_name = site[RPC_NAME]
        else:
            identifiers = {(DOMAIN, self._device_id)}
            device_name = self._device[RPC_NAME]

        
        return {
            ATTR_IDENTIFIERS: identifiers,
            ATTR_DEFAULT_NAME: site[RPC_NAME],
            ATTR_NAME: device_name,
            "default_manufacturer": DEVICE_MANUFACTURER,
            ATTR_SW_VERSION: site[SITE_VERSION],
            ATTR_VIA_DEVICE: (DOMAIN, site[SITE_NODEID])
        }

