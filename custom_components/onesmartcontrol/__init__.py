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
    

    # Wait for incoming data
    await hass.data[DOMAIN][ONESMART_WRAPPER].handle_update_flags()

    # Check cache
    cache = hass.data[DOMAIN][ONESMART_WRAPPER].get_cache()

    if len(cache[(COMMAND_METER,ACTION_LIST)]) == 0:
        raise ConfigEntryNotReady
    elif len(cache[(COMMAND_SITE,ACTION_GET)]) == 0:
        raise ConfigEntryNotReady
    elif len(cache[(COMMAND_DEVICE,ACTION_LIST)]) == 0:
        raise ConfigEntryNotReady
    
    # Subscribe to energy events
    await hass.data[DOMAIN][ONESMART_WRAPPER].subscribe(topics=[TOPIC_ENERGY, TOPIC_SITE])

    # Fetch initial polling data
    await hass.data[DOMAIN][ONESMART_WRAPPER].update_cache()
    await hass.data[DOMAIN][ONESMART_WRAPPER].poll_apparatus()

    # await hass.data[DOMAIN][ONESMART_WRAPPER].run()
    # Start the background runners
    hass.data[DOMAIN][ONESMART_RUNNER] = asyncio.create_task(
        hass.data[DOMAIN][ONESMART_WRAPPER].run()
    )


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
    
    print("One Smart Control is done with startup!")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        if entry.entry_id in hass.data[DOMAIN]:
            hass.data[DOMAIN].pop(entry.entry_id)
        
        hass.data[DOMAIN][ONESMART_RUNNER].cancel()
        await hass.data[DOMAIN][ONESMART_WRAPPER].close()

    return unload_ok
