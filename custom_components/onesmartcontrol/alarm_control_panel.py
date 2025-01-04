"""Read and control One Smart Control system mode"""
from __future__ import annotations
import json
from homeassistant.config_entries import ConfigEntry

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity, AlarmControlPanelEntityFeature, AlarmControlPanelState
)
from homeassistant.core import HomeAssistant

from .onesmartentity import OneSmartEntity
from .onesmartwrapper import OneSmartWrapper

from .const import *


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up the One Smart Control Site Mode"""

    wrapper: OneSmartWrapper = hass.data[DOMAIN][entry.entry_id][ONESMART_WRAPPER]

    entities = []

    entities.append(
        OneSmartAlarmPanel(
            hass,
            entry,
            wrapper,
            update_topic=OneSmartUpdateTopic.PUSH,
            source=OneSmartEventType.SITE_UPDATE,
            key="mode",
            name="System Mode",
            command_home={
                "command": OneSmartCommand.SITEPRESET,
                OneSmartFieldName.ACTION: OneSmartAction.PERFORM,
                OneSmartFieldName.PERFORM: OneSmartDefaultSitePreset.HOME
            },
            command_away={
                "command": OneSmartCommand.SITEPRESET,
                OneSmartFieldName.ACTION: OneSmartAction.PERFORM,
                OneSmartFieldName.PERFORM: OneSmartDefaultSitePreset.AWAY
            },
            command_night={
                "command": OneSmartCommand.SITEPRESET,
                OneSmartFieldName.ACTION: OneSmartAction.PERFORM,
                OneSmartFieldName.PERFORM: OneSmartDefaultSitePreset.ASLEEP
            }
        )
    )

    async_add_entities(entities)


class OneSmartAlarmPanel(OneSmartEntity, AlarmControlPanelEntity):
    def __init__(
        self,
        hass,
        config_entry,
        wrapper: OneSmartWrapper,
        update_topic,
        source,
        key,
        name,
        command_home: dict,
        command_away: dict,
        command_night: dict,
        device_id=None,
        suffix=None,
        icon=None
    ):
        super().__init__(hass, config_entry, wrapper, update_topic, source, device_id, name, suffix, icon)
        self.wrapper = wrapper
        self._key = key

        self._command_home = command_home
        self._command_away = command_away
        self._command_night = command_night

    @property
    def supported_features(self) -> AlarmControlPanelEntityFeature:
        return AlarmControlPanelEntityFeature.ARM_AWAY | AlarmControlPanelEntityFeature.ARM_NIGHT

    @property
    def alarm_state(self):
        onesmartvalue = self.get_cache_value(self._key)
        if onesmartvalue == OneSmartDefaultSitePreset.HOME:
            return AlarmControlPanelState.DISARMED
        if onesmartvalue == OneSmartDefaultSitePreset.AWAY:
            return AlarmControlPanelState.ARMED_AWAY
        if onesmartvalue == OneSmartDefaultSitePreset.ASLEEP:
            return AlarmControlPanelState.ARMED_NIGHT
        return None

    @property
    def available(self) -> bool:
        value = self.get_cache_value(self._key)
        return value is not None

    async def async_alarm_disarm(self, code=None):
        command_arm_home = json.loads(json.dumps(self._command_home))
        await self.wrapper.command(SOCKET_PUSH, **command_arm_home)

    async def async_alarm_arm_away(self, code=None):
        command_arm_away = json.loads(json.dumps(self._command_away))
        await self.wrapper.command(SOCKET_PUSH, **command_arm_away)

    async def async_alarm_arm_night(self, code=None):
        command_arm_night = json.loads(json.dumps(self._command_night))
        await self.wrapper.command(SOCKET_PUSH, **command_arm_night)
