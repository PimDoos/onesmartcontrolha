"""Read One Smart Control water heaters"""
from __future__ import annotations
import json
from homeassistant.config_entries import ConfigEntry


from homeassistant.const import (
    ATTR_DEVICE_CLASS, ATTR_NAME, Platform, CONF_DEVICE_ID,
    SERVICE_TURN_ON, SERVICE_TURN_OFF, STATE_ON, ATTR_TEMPERATURE, UnitOfTemperature
    
)
from homeassistant.components.water_heater import (
    WaterHeaterEntity, WaterHeaterEntityEntityDescription, WaterHeaterEntityFeature,
    ATTR_OPERATION_LIST, ATTR_OPERATION_MODE, STATE_OFF
)
from homeassistant.core import HomeAssistant

from .onesmartentity import OneSmartEntity
from .onesmartwrapper import OneSmartWrapper

from .const import * 

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the One Smart Control water heaters"""

    wrapper: OneSmartWrapper = hass.data[DOMAIN][entry.entry_id][ONESMART_WRAPPER]

    entities = []
    
    wrapper_entities = wrapper.get_platform_entities(Platform.WATER_HEATER)

    for wrapper_entity in wrapper_entities:
        optional_attributes = [
            CONF_DEVICE_ID, ATTR_DEVICE_CLASS
        ]

        for optional_attribute in optional_attributes:
            if not optional_attribute in wrapper_entity:
                wrapper_entity[optional_attribute] = None

        entities.append(
            OneSmartWaterHeater(
                hass,
                entry,
                wrapper,
                update_topic=wrapper_entity[OneSmartUpdateTopic],
                source=wrapper_entity[ONESMART_CACHE],
                key_mode=wrapper_entity[ONESMART_KEY_MODE],
                key_temperature=wrapper_entity[ONESMART_KEY_TEMPERATURE],
                key_target_temperature=wrapper_entity[ONESMART_KEY_TARGET_TEMPERATURE],
                name=wrapper_entity[ATTR_NAME],
                device_id=wrapper_entity[CONF_DEVICE_ID],
                operation_commands = wrapper_entity[ATTR_OPERATION_LIST],
                features = WaterHeaterEntityFeature.TARGET_TEMPERATURE | WaterHeaterEntityFeature.OPERATION_MODE
            )
        )


    async_add_entities(entities)
    
class OneSmartWaterHeater(OneSmartEntity, WaterHeaterEntity):
    def __init__(
        self,
        hass,
        config_entry,
        wrapper: OneSmartWrapper,
        update_topic,
        source,
        key_temperature,
        key_target_temperature,
        key_mode,
        name,
        operation_commands: dict,
        features,
        device_id=None,
        suffix=None,
        icon=None
    ):
        super().__init__(hass, config_entry, wrapper, update_topic, source, device_id, name, suffix, icon)
        self.wrapper = wrapper
        self._key_mode = key_mode
        self._key_temperature = key_temperature
        self._key_target_temperature = key_target_temperature

        self._operation_commands = operation_commands
        self._operation_translation = {value: key for key,value in operation_commands.items()}
        self._features = features


    @property
    def available(self) -> bool:
        value = self.get_cache_value(self._key_mode)
        return value is not None

    @property
    def temperature_unit(self):
        return UnitOfTemperature.CELSIUS

    async def async_set_operation_mode(self, operation_mode: str):
        mode_value = self._operation_commands[operation_mode]
        mode_key = self._key_mode.split(".")[-1]
        if mode_value != None:
            command_mode = {
                "command":self._source[0], OneSmartFieldName.ACTION:OneSmartAction.SET, OneSmartFieldName.ID:self._device_id, 
                OneSmartFieldName.ATTRIBUTES:{mode_key:mode_value}
            }
            await self.wrapper.command(SOCKET_PUSH, command_mode)
            self.wrapper.set_update_flag(self._source)

    async def async_set_temperature(self, **kwargs):
        if ATTR_TEMPERATURE in kwargs:
            temperature = kwargs[ATTR_TEMPERATURE]
            temperature_key = self._key_target_temperature.split(".")[-1]
            command_temperature = {
                "command":self._source[0], OneSmartFieldName.ACTION:OneSmartAction.SET, OneSmartFieldName.ID:self._device_id, 
                OneSmartFieldName.ATTRIBUTES:{temperature_key:temperature}
            }
            await self.wrapper.command(SOCKET_PUSH, **command_temperature)
        self.wrapper.set_update_flag(self._source)


    @property
    def operation_list(self):
        return list(self._operation_commands.keys())
    
    @property
    def current_operation(self):
        if self._key_mode != None:
            value = self.get_cache_value(self._key_mode)
            if value in self._operation_translation:
                return self._operation_translation[value]
            else:
                return STATE_OFF
        else:
            return list(self._operation_commands.keys())[0]


    @property
    def supported_features(self):
        return self._features

    @property
    def current_temperature(self) -> float:
        return self.get_cache_value(self._key_temperature)
    
    @property
    def target_temperature(self) -> float:
        return self.get_cache_value(self._key_target_temperature)

    @property
    def unique_id(self):
        if self._suffix != None:
            return f"{DOMAIN}-{self._device_id}-{self._key_mode}-{self._suffix}"
        else:
            return f"{DOMAIN}-{self._device_id}-{self._key_mode}"
