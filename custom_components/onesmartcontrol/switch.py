"""Read One Smart Control power and energy data"""
from __future__ import annotations
from homeassistant.config_entries import ConfigEntry


from homeassistant.const import (
    POWER_WATT, 
    ENERGY_WATT_HOUR,
    ATTR_IDENTIFIERS, ATTR_DEFAULT_NAME, ATTR_SW_VERSION, ATTR_VIA_DEVICE,
    ATTR_UNIT_OF_MEASUREMENT, ATTR_DEVICE_CLASS, ATTR_NAME, CONF_PLATFORM, Platform, CONF_DEVICE_ID,
    CONF_ATTRIBUTE, SERVICE_TURN_ON, SERVICE_TURN_OFF, STATE_ON
)
from homeassistant.components.switch import (
    SwitchDeviceClass, SwitchEntity, SwitchEntityDescription
)
from homeassistant.core import HomeAssistant

from .onesmartentity import OneSmartEntity
from .onesmartwrapper import OneSmartWrapper

from .const import * 

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the One Smart Control switches"""

    wrapper: OneSmartWrapper = hass.data[DOMAIN][entry.entry_id][ONESMART_WRAPPER]

    entities = []
    
    wrapper_entities = wrapper.get_platform_entities(Platform.SWITCH)

    for wrapper_entity in wrapper_entities:
        optional_attributes = [
            CONF_DEVICE_ID, ATTR_DEVICE_CLASS, SERVICE_TURN_ON, SERVICE_TURN_OFF, STATE_ON
        ]

        for optional_attribute in optional_attributes:
            if not optional_attribute in wrapper_entity:
                wrapper_entity[optional_attribute] = None

        entities.append(
            OneSmartSwitch(
                hass,
                entry,
                wrapper,
                update_topic=wrapper_entity[OneSmartUpdateTopic],
                source=wrapper_entity[ONESMART_CACHE],
                key=wrapper_entity[ONESMART_KEY],
                name=wrapper_entity[ATTR_NAME],
                device_id=wrapper_entity[CONF_DEVICE_ID],
                device_class=wrapper_entity[ATTR_DEVICE_CLASS],
                command_on=wrapper_entity[SERVICE_TURN_ON],
                command_off=wrapper_entity[SERVICE_TURN_OFF],
                state_on=wrapper_entity[STATE_ON]
            )
        )


    async_add_entities(entities)
    
class OneSmartSwitch(OneSmartEntity, SwitchEntity):
    def __init__(
        self,
        hass,
        config_entry,
        wrapper: OneSmartWrapper,
        update_topic,
        source,
        key,
        name,
        command_on: dict,
        command_off: dict,
        state_on = True,
        device_id=None,
        suffix=None,
        icon=None,
        device_class: SwitchDeviceClass = None
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
        self._icon = icon
        self._device_class = device_class

        self._command_on = command_on
        self._command_off = command_off

        self._state_on = state_on
        if self._state_on == None:
            self._state_on = True

    @property
    def is_on(self):
        return self.get_cache_value(self._key) == self._state_on

    @property
    def available(self) -> bool:
        if not self._source in self.cache:
            return False
        
        value = self.get_cache_value(self._key)
        return value is not None

    async def async_turn_on(self, **kwargs):
        await self.wrapper.command(SOCKET_PUSH, **self._command_on)
        self.wrapper.set_update_flag(self._source)

    async def async_turn_off(self, **kwargs):
        await self.wrapper.command(SOCKET_PUSH, **self._command_off)
        self.wrapper.set_update_flag(self._source)


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

