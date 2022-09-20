"""Read One Smart Control power and energy data"""
from __future__ import annotations
from homeassistant.config_entries import ConfigEntry


from homeassistant.const import (
    ATTR_IDENTIFIERS, ATTR_DEFAULT_NAME, ATTR_SW_VERSION, ATTR_VIA_DEVICE,
    ATTR_DEVICE_CLASS, ATTR_NAME, Platform, CONF_DEVICE_ID,
    SERVICE_TURN_ON, SERVICE_TURN_OFF, STATE_ON
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
        super().__init__(hass, config_entry, wrapper, update_topic, source, device_id, name, suffix, icon)
        self.wrapper = wrapper
        self._key = key

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
        value = self.get_cache_value(self._key)
        return value is not None

    async def async_turn_on(self, **kwargs):
        await self.wrapper.command(SOCKET_PUSH, **self._command_on)
        self.wrapper.set_update_flag(self._source)

    async def async_turn_off(self, **kwargs):
        await self.wrapper.command(SOCKET_PUSH, **self._command_off)
        self.wrapper.set_update_flag(self._source)