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

from homeassistant.util import dt as dt_util

from .const import *
from .onesmartwrapper import OneSmartWrapper

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up One Smart Control from a config entry."""

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    hass.data[DOMAIN][ONESMART_WRAPPER] = OneSmartWrapper(
        username = config_entry.data.get(CONF_USERNAME),
        password = config_entry.data.get(CONF_PASSWORD),
        host = config_entry.data.get(CONF_HOST),
        port = config_entry.data.get(CONF_PORT),
        hass = hass
    )
    try:
        connection_status = await hass.data[DOMAIN][ONESMART_WRAPPER].connect()
    except:
        raise ConfigEntryNotReady
    if connection_status == CONNECT_FAIL_AUTH:
        raise ConfigEntryAuthFailed
    elif connection_status == CONNECT_FAIL_NETWORK:
        raise ConfigEntryNotReady

    # Set update flags
    await hass.data[DOMAIN][ONESMART_WRAPPER].update_definitions()
    await hass.data[DOMAIN][ONESMART_WRAPPER].update_cache()

    # Wait for incoming data
    await hass.data[DOMAIN][ONESMART_WRAPPER].handle_update_flags()

    # Check cache
    cache = hass.data[DOMAIN][ONESMART_WRAPPER].get_cache()
    if len(cache[COMMAND_METER]) == 0:
        raise ConfigEntryNotReady
    elif len(cache[COMMAND_SITE]) == 0:
        raise ConfigEntryNotReady
    
    # Subscribe to energy events
    await hass.data[DOMAIN][ONESMART_WRAPPER].subscribe(topics=[TOPIC_ENERGY])

    # Start the background runner
    task = asyncio.create_task(
        hass.data[DOMAIN][ONESMART_WRAPPER].run()
    )
    hass.data[DOMAIN][ONESMART_RUNNER] = task

    scan_interval_definitions = timedelta(
        seconds = SCAN_INTERVAL_DEFINITIONS
    )
    scan_interval_cache = timedelta(
        seconds = SCAN_INTERVAL_CACHE
    )

    async def update_definitions(event_time_utc: datetime):
        await hass.data[DOMAIN][ONESMART_WRAPPER].update_definitions()

    async def update_cache(event_time_utc: datetime):
        await hass.data[DOMAIN][ONESMART_WRAPPER].update_cache()

    hass.data[DOMAIN][INTERVAL_TRACKER_DEFINITIONS] = async_track_time_interval(hass, update_definitions, scan_interval_definitions)
    hass.data[DOMAIN][INTERVAL_TRACKER_POLL] = async_track_time_interval(hass, update_cache, scan_interval_cache)

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        if entry.entry_id in hass.data[DOMAIN]:
            hass.data[DOMAIN].pop(entry.entry_id)
        
        hass.data[DOMAIN][ONESMART_RUNNER].cancel()
        hass.data[DOMAIN][ONESMART_WRAPPER].close()

    return unload_ok
