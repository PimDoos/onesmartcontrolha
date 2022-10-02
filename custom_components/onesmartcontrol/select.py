"""Read and control One Smart Control device select"""
from __future__ import annotations
from homeassistant.config_entries import ConfigEntry


from homeassistant.const import (
    ATTR_DEVICE_CLASS, ATTR_NAME, Platform, CONF_DEVICE_ID,
    SERVICE_TURN_ON, SERVICE_TURN_OFF, STATE_ON
)
from homeassistant.components.select import (
    SelectEntity, ATTR_OPTIONS, SERVICE_SELECT_OPTION
)
from homeassistant.core import HomeAssistant

from .onesmartentity import OneSmartEntity
from .onesmartwrapper import OneSmartWrapper

from .const import * 

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the One Smart Control select"""

    wrapper: OneSmartWrapper = hass.data[DOMAIN][entry.entry_id][ONESMART_WRAPPER]

    entities = []
    
    wrapper_entities = wrapper.get_platform_entities(Platform.SELECT)

    for wrapper_entity in wrapper_entities:
        optional_attributes = [
            CONF_DEVICE_ID, STATE_ON
        ]

        for optional_attribute in optional_attributes:
            if not optional_attribute in wrapper_entity:
                wrapper_entity[optional_attribute] = None

        entities.append(
            OneSmartSelect(
                hass,
                entry,
                wrapper,
                update_topic=wrapper_entity[OneSmartUpdateTopic],
                source=wrapper_entity[ONESMART_CACHE],
                key=wrapper_entity[ONESMART_KEY],
                name=wrapper_entity[ATTR_NAME],
                device_id=wrapper_entity[CONF_DEVICE_ID],
                options=wrapper_entity[ATTR_OPTIONS],
                options_commands=wrapper_entity[SERVICE_SELECT_OPTION],
                state_on=wrapper_entity[STATE_ON]
            )
        )


    async_add_entities(entities)
    
class OneSmartSelect(OneSmartEntity, SelectEntity):
    def __init__(
        self,
        hass,
        config_entry,
        wrapper: OneSmartWrapper,
        update_topic,
        source,
        key,
        name,
        options: dict,
        options_commands: dict,
        state_on = True,
        device_id=None,
        suffix=None,
        icon=None
    ):
        super().__init__(hass, config_entry, wrapper, update_topic, source, device_id, name, suffix, icon)
        self.wrapper = wrapper
        self._key = key
        self._options = options
        self._options_commands = options_commands
    
        self._state_on = state_on
        if self._state_on == None:
            self._state_on = True

    @property
    def current_option(self):
        for option_key in self._options:
            option_state = self.get_cache_value(option_key)
            if option_state == self._state_on:
                return self._options[option_key]
        else:
            return None
    
    @property
    def options(self):
        return list(self._options.values())

    @property
    def available(self) -> bool:
        for option_key in self._options:
            option_state = self.get_cache_value(option_key)
            if option_state is None:
                return False
        else:
            return True

    async def async_select_option(self, option: str) -> None:
        command = self._options_commands[option]
        await self.wrapper.command(SOCKET_PUSH, **command)
        self.wrapper.set_update_flag(self._source)
