from homeassistant.const import (
    Platform
)
from homeassistant.components.climate import (
    ATTR_HVAC_MODES, ATTR_HVAC_ACTION, HVACMode, HVACAction
)
from homeassistant.components.water_heater import (
    STATE_ECO, STATE_ELECTRIC, STATE_HEAT_PUMP, STATE_PERFORMANCE, ATTR_OPERATION_LIST
)

from .const import *

ENTITY_TEMPLATES = dict()

ENTITY_TEMPLATES[Platform.SENSOR] = [

]
ENTITY_TEMPLATES[Platform.SELECT] = [
    
]

ENTITY_TEMPLATES[Platform.CLIMATE] = [
    {
        ONESMART_CACHE: (OneSmartCommand.APPARATUS, OneSmartAction.GET),
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
        ONESMART_CACHE: (OneSmartCommand.APPARATUS, OneSmartAction.GET),
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
ENTITY_TEMPLATES[Platform.WATER_HEATER] = [
    {
        ONESMART_CACHE: (OneSmartCommand.APPARATUS, OneSmartAction.GET),
        ONESMART_KEY_TARGET_TEMPERATURE:"water_tank_setpoint",
        ONESMART_KEY_TEMPERATURE:"water_tank_temperature",
        ONESMART_KEY_MODE:"operating_mode_dhw",
        ATTR_OPERATION_LIST:{
            STATE_ECO:"eco",
            STATE_PERFORMANCE:"normal"
        }
    }
]