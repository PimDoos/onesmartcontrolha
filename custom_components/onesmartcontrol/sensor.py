"""Read One Smart Control device data"""
from __future__ import annotations
from homeassistant.config_entries import ConfigEntry


from homeassistant.const import (
    POWER_WATT, 
    ENERGY_WATT_HOUR,
    ATTR_UNIT_OF_MEASUREMENT, ATTR_DEVICE_CLASS, ATTR_NAME, CONF_PLATFORM, Platform, CONF_DEVICE_ID
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
    for meter in cache[(OneSmartCommand.METER,OneSmartAction.LIST)]:
        entities.append(
            OneSmartSensor(
                hass,
                entry,
                wrapper,
                update_topic=OneSmartUpdateTopic.PUSH,
                key=meter[OneSmartFieldName.ID],
                name=meter[OneSmartFieldName.NAME],
                suffix="power",
                source=OneSmartEventType.ENERGY_CONSUMPTION,
                unit=POWER_WATT,
                device_class=SensorDeviceClass.POWER,
                state_class=SensorStateClass.MEASUREMENT
            )
        )

        entities.append(
            OneSmartSensor(
                hass,
                entry,
                wrapper,
                update_topic=OneSmartUpdateTopic.POLL,
                key=meter[OneSmartFieldName.ID],
                name=meter[OneSmartFieldName.NAME],
                suffix="energy",
                source=(OneSmartCommand.ENERGY,OneSmartAction.TOTAL),
                unit=ENERGY_WATT_HOUR,
                device_class=SensorDeviceClass.ENERGY,
                state_class=SensorStateClass.TOTAL
            )
        )

    # Site sensors
    entities.append(
        OneSmartSensor(
            hass,
            entry,
            wrapper,
            update_topic=OneSmartUpdateTopic.PUSH,
            key="mode",
            name="System Mode",
            source=OneSmartEventType.SITE_UPDATE,
            icon="mdi:home-account",
        )
    )

    wrapper_entities = wrapper.get_platform_entities(Platform.SENSOR)

    for wrapper_entity in wrapper_entities:
        optional_attributes = [
            ATTR_UNIT_OF_MEASUREMENT, ATTR_DEVICE_CLASS, ATTR_STATE_CLASS, CONF_DEVICE_ID, 
        ]

        for optional_attribute in optional_attributes:
            if not optional_attribute in wrapper_entity:
                wrapper_entity[optional_attribute] = None

        entities.append(
            OneSmartSensor(
                hass,
                entry,
                wrapper,
                update_topic=OneSmartUpdateTopic.APPARATUS,
                source=wrapper_entity[ONESMART_CACHE],
                key=wrapper_entity[ONESMART_KEY],
                name=wrapper_entity[ATTR_NAME],
                device_id=wrapper_entity[CONF_DEVICE_ID],
                unit=wrapper_entity[ATTR_UNIT_OF_MEASUREMENT],
                device_class=wrapper_entity[ATTR_DEVICE_CLASS],
                state_class=wrapper_entity[ATTR_STATE_CLASS]
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
        source,
        key,
        name,
        suffix = None,
        device_id = None,
        unit = None,
        icon = None,
        device_class: SensorDeviceClass = None,
        state_class: SensorStateClass = None,
        precision: int = None
    ):
        super().__init__(hass, config_entry, wrapper, update_topic, source, device_id, name, suffix, icon)
        self.wrapper = wrapper
        self._key = key
        
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_native_precision = precision

    @property
    def native_value(self):
        return self.get_cache_value(self._key)

    @property
    def available(self) -> bool:      
        value = self.get_cache_value(self._key)
        return value is not None


