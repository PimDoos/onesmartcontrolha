"""The One Smart Control integration"""
from __future__ import annotations
from datetime import timedelta
import datetime
import logging
import asyncio

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, CONF_USERNAME, CONF_PASSWORD, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from homeassistant.helpers.event import async_track_time_interval

from .const import *
from .onesmartwrapper import OneSmartWrapper

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up One Smart Control from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {}
    
    wrapper = OneSmartWrapper(
        username = entry.data.get(CONF_USERNAME),
        password = entry.data.get(CONF_PASSWORD),
        host = entry.data.get(CONF_HOST),
        port = entry.data.get(CONF_PORT),
        hass = hass
    )
    hass.data[DOMAIN][entry.entry_id][ONESMART_WRAPPER] = wrapper

    try:
        wrapper_status = await wrapper.setup()
    except:
        raise ConfigEntryNotReady
    if wrapper_status == SETUP_FAIL_AUTH:
        raise ConfigEntryAuthFailed
    elif wrapper_status != SETUP_SUCCESS:
        raise ConfigEntryNotReady  

    scan_interval_definitions = timedelta(
        seconds = SCAN_INTERVAL_DEFINITIONS
    )
    scan_interval_cache = timedelta(
        seconds = SCAN_INTERVAL_CACHE
    )

    async def update_definitions(event_time_utc: datetime):
        await hass.data[DOMAIN][entry.entry_id][ONESMART_WRAPPER].update_definitions()

    async def update_cache(event_time_utc: datetime):
        await hass.data[DOMAIN][entry.entry_id][ONESMART_WRAPPER].update_cache()

    hass.data[DOMAIN][entry.entry_id][INTERVAL_TRACKER_DEFINITIONS] = async_track_time_interval(hass, update_definitions, scan_interval_definitions)
    hass.data[DOMAIN][entry.entry_id][INTERVAL_TRACKER_POLL] = async_track_time_interval(hass, update_cache, scan_interval_cache)

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )
    
    print("One Smart Control is done with startup!")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        if entry.entry_id in hass.data[DOMAIN]:
            await hass.data[DOMAIN][entry.entry_id][ONESMART_WRAPPER].close()
            
            hass.data[DOMAIN].pop(entry.entry_id)
        
        

    return unload_ok
