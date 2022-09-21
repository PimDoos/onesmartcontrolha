from enum import Enum, IntEnum
from homeassistant.components.climate import (
    ATTR_HVAC_MODES, ATTR_HVAC_ACTION, HVACMode, HVACAction
)


DEVICE_MANUFACTURER = "One Smart Control"
INTEGRATION_TITLE = "One Smart Control"

DOMAIN = "onesmartcontrol"
ONESMART_RUNNER = "runner"
ONESMART_WRAPPER = "onesmartwrapper"

class OneSmartUpdateTopic(str, Enum):
    PUSH = f"{DOMAIN}_push"
    POLL = f"{DOMAIN}_poll"
    DEFINITIONS = f"{DOMAIN}_definitions"
    APPARATUS = f"{DOMAIN}_apparatus"
    PRESET = f"{DOMAIN}_preset"

ONESMART_CACHE = "cache"
ONESMART_KEY = "key"
ONESMART_KEY_ACTION = "key_action"
ONESMART_KEY_TEMPERATURE = "key_temperature"
ONESMART_KEY_TARGET_TEMPERATURE = "key_target_temperature"
ONESMART_KEY_MODE = "key_mode"

class OneSmartAccessLevel(str, Enum):
    READ = "READ"
    READWRITE = "READWRITE"
    WRITE = "WRITE"

class OneSmartAction(str, Enum):
    ADD = "add"
    CHECK = "check"
    DELETE = "delete"
    GET = "get"
    LIST = "list"
    PERFORM = "perform"
    SET = "set"
    SUBSCRIBE = "subscribe"
    TOTAL = "total"
    UPDATE = "update"

class OneSmartActionType(str, Enum):
    SITE_PRESET = "SITEPRESET"
    PRESET_GROUP = "PRESETGROUP"

class OneSmartSetupStatus(IntEnum):
    SUCCESS = 0
    FAIL_NETWORK = 1
    FAIL_AUTH = 2
    FAIL_CACHE = 3

class OneSmartCommand(str, Enum):
    APPARATUS = "apparatus"
    AUTHENTICATE = "authenticate"
    DEVICE = "device"
    ENERGY = "energy"
    EVENTS = "events"
    GETTOKEN = "gettoken"
    LOGBOOK = "logbook"
    METER = "meter"
    MODULES = "modules"
    PING = "ping"
    PRESET = "preset"
    PRESET_GROUP = "presetgroup"
    ROLE = "role"
    ROOM = "room"
    SITE = "site"
    USER = "user"
    UPGRADE = "upgrade"
    SITEPRESET = "sitepreset"
    TRIGGER = "trigger"

class OneSmartEventType(str, Enum):
    DEVICE_DATA = "device_data"
    DEVICE_INPUT = "device_input"
    DEVICE_STATUS = "device_status"

    ENERGY_CONSUMPTION = "energy_consumption"

    PRESET_PERFORM = "preset_perform"
    PRESET_STOP = "preset_stop"
    PRESET_DELETE = "preset_delete"
    
    ROOM_CREATE = "room_create"
    ROOM_UPDATE = "room_update"
    ROOM_DELETE = "room_delete"

    SITE_UPDATE = "site_update"

    TRIGGER_CREATE = "trigger_create"
    TRIGGER_PERFORM = "trigger_perform"
    TRIGGER_DELETE = "trigger_delete"

class OneSmartPresetType(str, Enum):
    ROOMON = "ROOM{}"
    ROOMOFF = "ROOMOFF"
    AREAON = "AREA{}ON"
    AREAOFF = "AREA{}OFF"

class OneSmartFieldName(str, Enum):
    ACCESS = "access"
    ACTION = "action"
    ACTIVE = "active"
    ATTRIBUTES = "attributes"
    COMMAND = "cmd"
    DATA = "data"
    DEVICES = "devices"
    ENUM = "enum"
    ERROR = "error"
    EVENT = "event"
    GROUP = "group"
    MAC = "mac"
    NODEID = "nodeID"
    PRESETS = "presets"
    RESULT = "result"
    ROOM = "room"
    ROOMS = "rooms"
    TRANSACTION = "transaction"
    TYPE = "type"
    VALUES = "values"
    VALUE = "value"
    VERSION = "version"
    VISIBLE = "visible"
    NAME = "name"
    METERS = "meters"
    ID = "id"

class OneSmartTopic(str, Enum):
    AUTHENTICATION = "AUTHENTICATION"
    ENERGY = "ENERGY"
    DEVICE = "DEVICE"
    MESSAGE = "MESSAGE"
    METER = "METER"
    PRESET = "PRESET"
    PRESETGROUP = "PRESETGROUP"
    ROLE = "ROLE"
    ROOM = "ROOM"
    TRIGGER = "TRIGGER"
    SITE = "SITE"
    SITEPRESET = "SITEPRESET"
    UPGRADE = "UPGRADE"
    USER = "USER"

class OneSmartDataType(str, Enum):
    ARRAY = "ARRAY"
    NUMBER = "NUMBER"
    OBJECT = "OBJECT"
    REAL = "REAL"
    STRING = "STRING"

class OneSmartGroupType(str, Enum):
    ACCESS = "ACCESS"
    AUDIO = "AUDIO"
    BLINDS = "BLINDS"
    CLIMATE = "CLIMATE"
    LIGHTS = "LIGHTS"
    SECURITY = "SECURITY"
    VIDEO = "VIDEO"

# Config
SOCKET_BUFFER_SIZE = 1024
SOCKET_RECEIVE_TIMEOUT = 1
SOCKET_AUTHENTICATION_TIMEOUT = 5
SOCKET_CONNECTION_TIMEOUT = 10
SOCKET_COMMAND_TIMEOUT = 60
SOCKET_COMMAND_DELAY = 5
SOCKET_RECONNECT_DELAY = 60
SOCKET_RECONNECT_RETRIES = 5
SOCKET_POLL = "poll"
SOCKET_PUSH = "push"

SCAN_INTERVAL_DEFINITIONS = 1800
SCAN_INTERVAL_CACHE = 300

INTERVAL_TRACKER_DEFINITIONS = "track_interval_definitions"
INTERVAL_TRACKER_POLL = "track_interval_poll"

MAX_TRANSACTION_ID = 65535
BIT_LENGTH_DOUBLE = 64
MAX_APPARATUS_POLL = 4
PING_INTERVAL = 30
DEFAULT_PORT = 9010

COMMAND_REPLACE_VALUE = 4294967296


CLIMATE_ENTITY_DEFINITIONS = [
    {
        ONESMART_KEY_ACTION:"operating_mode",
        ONESMART_KEY_TEMPERATURE:"room_temperature_zone1",
        ONESMART_KEY_TARGET_TEMPERATURE:"hc_thermostat_target_temperature_zone1",
        ONESMART_KEY_MODE:"system_onoff",
        ATTR_HVAC_MODES:{
            HVACMode.OFF:"off",
            HVACMode.AUTO:"on"
        },
        ATTR_HVAC_ACTION:{
            'stop':HVACAction.OFF, 
            'hot_water':HVACAction.OFF,
            'heating':HVACAction.HEATING, 
            'cooling':HVACAction.COOLING, 
            'freeze_stat':HVACAction.OFF,
            'legionella':HVACAction.OFF
        }
    },
    {
        ONESMART_KEY_ACTION:"bypass_percentage",
        ONESMART_KEY_TEMPERATURE:"outlet_air_temperature",
        ONESMART_KEY_TARGET_TEMPERATURE:"comfort_temperature",
        ONESMART_KEY_MODE:None,
        ATTR_HVAC_MODES:{
            HVACMode.FAN_ONLY:None,
        },
        ATTR_HVAC_ACTION:{
            0:HVACAction.FAN, 
            100:HVACAction.COOLING,
        }
    },

]
WATER_HEATER_ENTITY_DEFINITIONS = [
    {
        ONESMART_KEY_ACTION:"operating_mode_dhw",
        ONESMART_KEY_TARGET_TEMPERATURE:"water_tank_setpoint",
        ONESMART_KEY_TEMPERATURE:"water_tank_temperature",
        ONESMART_KEY_MODE:"dhw_on_prohibit"
    }
]

