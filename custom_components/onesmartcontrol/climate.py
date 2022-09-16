"""Read One Smart Control power and energy data"""
from __future__ import annotations
from homeassistant.config_entries import ConfigEntry


from homeassistant.const import (
    CONF_PLATFORM, Platform,
    ATTR_IDENTIFIERS, ATTR_DEFAULT_NAME, ATTR_SW_VERSION, 
	ATTR_VIA_DEVICE, ATTR_NAME, 
)
from homeassistant.components.climate import (
    ClimateEntity, ClimateEntityFeature
)
from homeassistant.core import HomeAssistant

from .onesmartentity import OneSmartEntity
from .onesmartwrapper import OneSmartWrapper

from .const import * 

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the One Smart Control climate entities"""

    wrapper: OneSmartWrapper = hass.data[DOMAIN][entry.entry_id][ONESMART_WRAPPER]

    cache = wrapper.get_cache()

    entities = []

    # Device sensors
    devices_attributes = wrapper.get_apparatus_attributes()
    devices = cache[(OneSmartCommand.DEVICE,OneSmartAction.LIST)]

    for device_id in devices_attributes:
        device = devices[device_id]
        device_name = device[OneSmartFieldName.NAME]
        attributes = devices_attributes[device_id]

		# If device has all attributes, create entity

        for attribute_name in attributes:
            attribute = attributes[attribute_name]

            if(attribute[CONF_PLATFORM] == Platform.CLIMATE):
                required_attributes = [
                    
                ]

                for required_attribute in required_attributes:
                    if not required_attribute in attribute:
                        attribute[required_attribute] = None

                entities.append(
                    OneSmartClimate(
                        hass,
                        entry,
                        wrapper,
                        ONESMART_UPDATE_APPARATUS,
                        f"{device_id}.{attribute_name}",
                        f"{device_name} {attribute_name.replace('_',' ').title()}",
                        None,
                        (OneSmartCommand.APPARATUS,OneSmartAction.GET),
                        device_id,
                        
                    )
                )



    async_add_entities(entities)
    
class OneSmartClimate(OneSmartEntity, ClimateEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        wrapper: OneSmartWrapper,
        update_topic: str,
        key: str,
        name: str,
        suffix: str,
        source: str,
        device_id: str,
        attributes: dict()
    ):
        super().__init__(hass, config_entry, wrapper, update_topic)
        self.wrapper = wrapper
        self._key = key
        if device_id != None:
            self._device_id = device_id
            devices = self.cache[(OneSmartCommand.DEVICE,OneSmartAction.LIST)]
            self._device = devices[device_id]
        else:
            self._device_id = self.cache[(OneSmartCommand.SITE,OneSmartAction.GET)][OneSmartFieldName.NODEID]
        self._name = name
        self._suffix = suffix
        self._source = source
        self._attributes = attributes

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
        site = self.cache[(OneSmartCommand.SITE,OneSmartAction.GET)]
        if self._device_id == site[OneSmartFieldName.NODEID]:
            identifiers = {(DOMAIN, site[OneSmartFieldName.MAC]), (DOMAIN, self._device_id)}
            device_name = site[OneSmartFieldName.NAME]
        else:
            identifiers = {(DOMAIN, self._device_id)}
            device_name = self._device[OneSmartFieldName.NAME]

        
        return {
            ATTR_IDENTIFIERS: identifiers,
            ATTR_DEFAULT_NAME: site[OneSmartFieldName.NAME],
            ATTR_NAME: device_name,
            "default_manufacturer": DEVICE_MANUFACTURER,
            ATTR_SW_VERSION: site[OneSmartFieldName.VERSION],
            ATTR_VIA_DEVICE: (DOMAIN, site[OneSmartFieldName.NODEID])
        }

