"""Read and control One Smart Control climate data"""
from __future__ import annotations
import json
from homeassistant.config_entries import ConfigEntry


from homeassistant.const import (
    ATTR_DEVICE_CLASS, ATTR_NAME, Platform, CONF_DEVICE_ID,
    ATTR_TEMPERATURE, UnitOfTemperature
    
)
from homeassistant.components.climate import (
    ClimateEntity, ClimateEntityDescription, HVACAction, HVACMode, ClimateEntityFeature,
    ATTR_HVAC_ACTION, ATTR_HVAC_MODES
)
from homeassistant.core import HomeAssistant

from .onesmartentity import OneSmartEntity
from .onesmartwrapper import OneSmartWrapper

from .const import * 

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the One Smart Control climates"""

    wrapper: OneSmartWrapper = hass.data[DOMAIN][entry.entry_id][ONESMART_WRAPPER]

    entities = []
    
    wrapper_entities = wrapper.get_platform_entities(Platform.CLIMATE)

    for wrapper_entity in wrapper_entities:
        optional_attributes = [
            CONF_DEVICE_ID, ATTR_DEVICE_CLASS
        ]

        for optional_attribute in optional_attributes:
            if not optional_attribute in wrapper_entity:
                wrapper_entity[optional_attribute] = None

        entities.append(
            OneSmartClimate(
                hass,
                entry,
                wrapper,
                update_topic=wrapper_entity[OneSmartUpdateTopic],
                source=wrapper_entity[ONESMART_CACHE],
                key_action=wrapper_entity[ONESMART_KEY_ACTION],
                key_mode=wrapper_entity[ONESMART_KEY_MODE],
                key_temperature=wrapper_entity[ONESMART_KEY_TEMPERATURE],
                key_target_temperature=wrapper_entity[ONESMART_KEY_TARGET_TEMPERATURE],
                name=wrapper_entity[ATTR_NAME],
                device_id=wrapper_entity[CONF_DEVICE_ID],
                hvac_commands = wrapper_entity[ATTR_HVAC_MODES],
                hvac_actions = wrapper_entity[ATTR_HVAC_ACTION],
                features = ClimateEntityFeature.TARGET_TEMPERATURE
            )
        )


    async_add_entities(entities)
    
class OneSmartClimate(OneSmartEntity, ClimateEntity):
    def __init__(
        self,
        hass,
        config_entry,
        wrapper: OneSmartWrapper,
        update_topic,
        source,
        key_action,
        key_temperature,
        key_target_temperature,
        key_mode,
        name,
        hvac_commands: dict,
        hvac_actions: dict,
        features,
        device_id=None,
        suffix=None,
        icon=None
    ):
        super().__init__(hass, config_entry, wrapper, update_topic, source, device_id, name, suffix, icon)
        self.wrapper = wrapper

        self._key_action = key_action
        self._key_mode = key_mode
        self._key_temperature = key_temperature
        self._key_target_temperature = key_target_temperature

        self._hvac_commands = hvac_commands
        self._hvac_modes = {value: key for key,value in hvac_commands.items()}
        self._attr_hvac_modes = list(self._hvac_commands.keys())

        self._hvac_actions = hvac_actions
        self._attr_supported_features = features

        self._attr_temperature_unit = UnitOfTemperature.CELSIUS


    @property
    def available(self) -> bool:
        value = self.get_cache_value(self._key_action)
        return value is not None

    async def async_set_hvac_mode(self, hvac_mode):
        mode_value = self._hvac_commands[hvac_mode]
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
    def hvac_action(self) -> HVACAction: 
        value = self.get_cache_value(self._key_action)

        if value in self._hvac_actions:
            return self._hvac_actions[value]
        else:
            return HVACAction.OFF


    @property
    def hvac_mode(self):
        if self._key_mode != None:
            value = self.get_cache_value(self._key_mode)
            if value in self._hvac_modes:
                return self._hvac_modes[value]
            else:
                return HVACMode.OFF
        else:
            return list(self._hvac_commands.keys())[0]


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
