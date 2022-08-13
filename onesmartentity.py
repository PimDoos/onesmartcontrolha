from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.const import ATTR_IDENTIFIERS, ATTR_DEFAULT_NAME, ATTR_SW_VERSION, ATTR_VIA_DEVICE

from .onesmartwrapper import OneSmartWrapper
from .const import *


class OneSmartEntity(Entity):
    def __init__(self, hass: HomeAssistant, config_entry, wrapper: OneSmartWrapper, update_topic):
        self.hass = hass
        self.config_entry = config_entry
        self.wrapper = wrapper
        self.update_topic = update_topic
        self.update_topic_listener = None
        self.cache = wrapper.get_cache()

    async def async_added_to_hass(self):
        @callback
        def update():
            self.update_from_latest_data()
            self.async_write_ha_state()

        await super().async_added_to_hass()
        self.update_topic_listener = async_dispatcher_connect(
            self.hass, self.update_topic, update
        )
        self.async_on_remove(self.update_topic_listener)
        self.update_from_latest_data()

    @property
    def available(self) -> bool:
        return self.wrapper.is_connected()

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def device_info(self):
        site = self.cache[COMMAND_SITE]
        return {
            ATTR_IDENTIFIERS: {(DOMAIN, site[SITE_MAC]), (DOMAIN, site[SITE_NODEID])},
            ATTR_DEFAULT_NAME: site[RPC_NAME],
            "default_manufacturer": DEVICE_MANUFACTURER,
            ATTR_SW_VERSION: site[SITE_VERSION],
            ATTR_VIA_DEVICE: (DOMAIN, site[SITE_NODEID])
        }
    @callback
    def update_from_latest_data(self):
        #self.wrapper = self.hass.data[DOMAIN][ONESMART_WRAPPER]
        self.cache = self.wrapper.get_cache()
        