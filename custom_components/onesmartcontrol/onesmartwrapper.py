

import asyncio
from logging import error, warning
from re import match
import struct
from homeassistant.core import HomeAssistant, CoreState
from homeassistant.helpers.dispatcher import async_dispatcher_send
from functools import partial

from homeassistant.const import (
    Platform, ATTR_UNIT_OF_MEASUREMENT, ATTR_DEVICE_CLASS, CONF_PLATFORM,
    PERCENTAGE,
    DEVICE_CLASS_CO2, CONCENTRATION_PARTS_PER_MILLION,
    DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS,
    DEVICE_CLASS_POWER, POWER_WATT, 
    DEVICE_CLASS_POWER_FACTOR,
    DEVICE_CLASS_VOLTAGE, ELECTRIC_POTENTIAL_VOLT,
    DEVICE_CLASS_CURRENT, ELECTRIC_CURRENT_AMPERE,
    DEVICE_CLASS_FREQUENCY, FREQUENCY_HERTZ
    
)
from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT, ATTR_STATE_CLASS
)
from time import time

from .const import *
from .onesmartsocket import OneSmartSocket

class OneSmartWrapper():
    def __init__(self, username, password, host, port, hass: HomeAssistant):
        self.socket = OneSmartSocket()

        self.username = username
        self.password = password
        self.host = host
        self.port = port

        self.hass = hass
        self.cache = dict()
        self.cache[EVENT_ENERGY_CONSUMPTION] = dict()
        self.cache[(COMMAND_METER,ACTION_LIST)] = dict()
        self.cache[(COMMAND_ENERGY,ACTION_TOTAL)] = dict()
        self.cache[(COMMAND_SITE,ACTION_GET)] = dict()
        self.cache[(COMMAND_DEVICE,ACTION_LIST)] = dict()
        self.cache[(COMMAND_APPARATUS,ACTION_GET)] = dict()

        self.update_flags = []

        self.last_apparatus_index = dict()
        self.device_apparatus_attributes = dict()
    
    async def connect(self):
        connection_success = await self.hass.async_add_executor_job(
            self.socket.connect,
            self.host, self.port
        )
        if not connection_success:
            return CONNECT_FAIL_NETWORK

        login_transaction = await self.hass.async_add_executor_job(
            self.socket.authenticate,
            self.username, self.password
        )

        login_status = None
        while login_status == None:
            self.socket.get_responses()
            login_status = await self.hass.async_add_executor_job(
                self.socket.get_transaction,
                login_transaction
            )

        if RPC_ERROR in login_status:
            return CONNECT_FAIL_AUTH
        else:
            return CONNECT_SUCCESS

    async def run(self):
        last_ping = time()
        

        # Loop through received data, blocked by socket.read
        while self.hass.state == CoreState.not_running or self.hass.is_running:
            try:
                # Make sure socket is connected. Reconnect if neccessary
                if not self.socket.is_connected():
                    await self.connect()

                # Keep the connection alive
                if time() - last_ping > PING_INTERVAL:
                    ping_result = None
                    ping_result = await self.command(COMMAND_PING)

                    if ping_result == None:
                        # Ping timed out, reconnect
                        warning(f"Ping to server timed out. Reconnecting.")
                        await self.connect()
                    last_ping = time()

                # Read data from the socket
                await self.hass.async_add_executor_job(
                    self.socket.get_responses
                )

                tasks = []
                # Handle events (push updates)
                await self.handle_events()
                
                # Update caches
                await self.handle_update_flags()

                # Update apparatus attributes
                await self.poll_apparatus()

            except Exception as e:
                error(f"Error in gateway wrapper: { e }")


    async def close(self):
        await self.hass.async_add_executor_job(
            self.socket.close
        )
        return not self.socket.is_connected

    async def command(self, command, **kwargs):
        transaction_id = await self.hass.async_add_executor_job(
            partial(self.socket.send_cmd, command, **kwargs)
        )
        # print("{} SEND {}".format(transaction_id, (command, kwargs)))
        # Wait for transaction to return
        transaction_done = False
        start_time = time()
        while not transaction_done:
            if time() - start_time > SOCKET_COMMAND_TIMEOUT:
                warning(f"Command timed out after {SOCKET_COMMAND_TIMEOUT} seconds: { command }")
                return None
            # print("{} WAIT".format(transaction_id))
            await self.hass.async_add_executor_job(
                self.socket.get_responses
            )

            transaction = await self.hass.async_add_executor_job(
                self.socket.get_transaction, transaction_id
            )
            transaction_done = transaction != None
        
        # print("{} DONE {}".format(transaction_id, transaction))
        return transaction

    """Subscribe the socket to the specified event topics"""
    async def subscribe(self, topics: list):
        return await self.command(command=COMMAND_EVENTS, action=ACTION_SUBSCRIBE, topics=topics)

    """Update id-name mappings"""
    async def update_definitions(self):
        self.set_update_flag((COMMAND_SITE,ACTION_GET))
        self.set_update_flag((COMMAND_METER,ACTION_LIST))
        self.set_update_flag((COMMAND_DEVICE,ACTION_LIST))
        
    """Update polling cache"""
    async def update_cache(self):
        self.set_update_flag((COMMAND_ENERGY,ACTION_TOTAL))

    def set_update_flag(self, flag):
        self.update_flags.append(flag)
    
    async def handle_update_flags(self):
        dispatcher_topics = []

        # Handle update flags
        for flag in self.update_flags:
            flag_command = flag[0]
            flag_action = flag[1]
            
            if flag_command in [COMMAND_SITE]:
                # Fill cache with RPC result
                transaction = await self.command(command=flag_command, action=flag_action)
                self.cache[flag] = transaction[RPC_RESULT]

                if flag_command == COMMAND_SITE:
                    # Also store in Site Event cache
                    self.cache[EVENT_SITE_UPDATE] = transaction[RPC_RESULT]

                if not ONESMART_UPDATE_DEFINITIONS in dispatcher_topics:
                    dispatcher_topics.append(ONESMART_UPDATE_DEFINITIONS)

            elif flag_command in [COMMAND_METER]:
                # Fill cache with RPC result (in corresponding subkey)
                transaction = await self.command(command=flag_command, action=flag_action)
                if flag_command == COMMAND_METER:
                    if not RPC_METERS in transaction[RPC_RESULT]:
                        self.cache[flag] = None
                    else:
                        self.cache[flag] = transaction[RPC_RESULT][RPC_METERS]

                if not ONESMART_UPDATE_DEFINITIONS in dispatcher_topics:
                    dispatcher_topics.append(ONESMART_UPDATE_DEFINITIONS)

            elif flag_command in [COMMAND_ENERGY, COMMAND_DEVICE]:
                transaction = await self.command(command=flag_command, action = flag_action)
                if flag_command == COMMAND_ENERGY:
                    if RPC_VALUES in transaction[RPC_RESULT]:
                        for entry in transaction[RPC_RESULT][RPC_VALUES]:
                            self.cache[flag][entry[RPC_ID]] = entry[RPC_VALUE]

                        if not ONESMART_UPDATE_POLL in dispatcher_topics:
                            dispatcher_topics.append(ONESMART_UPDATE_POLL)
                elif flag_command == COMMAND_DEVICE:
                    if RPC_DEVICES in transaction[RPC_RESULT]:
                        for entry in transaction[RPC_RESULT][RPC_DEVICES]:
                            self.cache[flag][entry[RPC_ID]] = entry
                        await self.discover_apparatus()

                if not ONESMART_UPDATE_DEFINITIONS in dispatcher_topics:
                    dispatcher_topics.append(ONESMART_UPDATE_DEFINITIONS)

            elif flag_command == COMMAND_APPARATUS:
                if flag_action == ACTION_LIST:
                    for device_id in self.cache[(COMMAND_DEVICE, ACTION_LIST)]:
                        transaction = await self.command(
                            command=flag_command, action=flag_action, 
                            id=device_id
                        )
                        if not RPC_ATTRIBUTES in transaction[RPC_RESULT]:
                            self.cache[flag] = None
                        else:
                            self.cache[flag] = transaction[RPC_RESULT][RPC_ATTRIBUTES]
     
        self.update_flags = []        
        
        # Send dispatcher event to update bound entities
        for topic in dispatcher_topics:
            async_dispatcher_send(self.hass, topic)
        
    async def poll_apparatus(self):
         # Update apparatus values
        for device_id in self.device_apparatus_attributes:
            attributes = self.device_apparatus_attributes[device_id]
            attribute_names = [attribute_name for attribute_name in attributes]

            # Only poll MAX_APPARATUS_POLL per cycle
            if not device_id in self.last_apparatus_index:
                attribute_index = 0
            else:
                attribute_index = self.last_apparatus_index[device_id] + 1
                if attribute_index >= len(attribute_names):
                    attribute_index = 0
            
            end_index = attribute_index + MAX_APPARATUS_POLL
            if end_index >= len(attribute_names):
                split_attributes = attribute_names[attribute_index:]
            else:
                split_attributes = attribute_names[attribute_index:end_index+1]

            self.last_apparatus_index[device_id] = end_index

            transaction = await self.command(
                command=COMMAND_APPARATUS, action=ACTION_GET, 
                id=device_id, attributes=split_attributes
            )
            if transaction == None:
                continue
            if RPC_ERROR in transaction[RPC_RESULT]:
                devices = self.cache[(COMMAND_DEVICE,ACTION_LIST)]
                device = devices[device_id]
                device_name = device[RPC_NAME]
                warning(f"Could not update '{split_attributes}' for '{device_name}': {transaction[RPC_RESULT]}")
            else:
                try:
                    values_new = transaction[RPC_RESULT][RPC_ATTRIBUTES]
                    for value_name in values_new:
                        value = values_new[value_name]
                        if isinstance(value, int):
                            bit_length = value.bit_length()
                            if bit_length >= BIT_LENGTH_DOUBLE - 4:
                                values_new[value_name] = struct.unpack("<d",value.to_bytes(8,byteorder="little", signed=True))[0]
                                if values_new[value_name] < 1:
                                    values_new[value_name] = 0 

                    if device_id in self.cache[(COMMAND_APPARATUS,ACTION_GET)]:
                        values_cache = self.cache[(COMMAND_APPARATUS,ACTION_GET)][device_id]
                    else:
                        values_cache = {}
                    self.cache[(COMMAND_APPARATUS,ACTION_GET)][device_id] = values_cache | values_new
                except Exception as e:
                    warning(f"Could not update '{split_attributes}' for '{device_name}': { e } ''")
            
        async_dispatcher_send(self.hass, ONESMART_UPDATE_APPARATUS)

    def get_cache(self, cache_name = None):
        if cache_name == None:
            return self.cache
        else:
            return self.cache[cache_name]

    async def handle_events(self):
        events = await self.hass.async_add_executor_job(
            self.socket.get_events
        )
        for event in events:
            if event[RPC_EVENT] == EVENT_ENERGY_CONSUMPTION and len(self.cache[(COMMAND_METER,ACTION_LIST)]) > 0:
                for reading in event[RPC_DATA][RPC_VALUES]:
                    meter_value = reading["value"]
                    self.cache[EVENT_ENERGY_CONSUMPTION][reading["id"]] = meter_value
            if event[RPC_EVENT] == EVENT_SITE_UPDATE:
                self.cache[EVENT_SITE_UPDATE] = event[RPC_DATA]

        async_dispatcher_send(self.hass, ONESMART_UPDATE_PUSH)

    async def discover_apparatus(self):
        for device_id in self.cache[(COMMAND_DEVICE,ACTION_LIST)]:
            device = self.cache[(COMMAND_DEVICE,ACTION_LIST)][device_id]
            if(device[RPC_VISIBLE] == False):
                continue
            self.device_apparatus_attributes[device_id] = dict()

            transaction = await self.command(COMMAND_APPARATUS, action=ACTION_LIST, id=device_id)
            attributes = transaction[RPC_RESULT][RPC_ATTRIBUTES]

            for attribute in attributes:
                if attribute[RPC_ACCESS] == ACCESS_READ:
                    attribute[CONF_PLATFORM] = Platform.SENSOR
                    if attribute[RPC_TYPE] in [TYPE_NUMBER, TYPE_REAL]:
                        attribute[ATTR_STATE_CLASS] = STATE_CLASS_MEASUREMENT
                        # Temperature sensors
                        if "_temp" in attribute[RPC_NAME]:
                            attribute[ATTR_UNIT_OF_MEASUREMENT] = TEMP_CELSIUS
                            attribute[ATTR_DEVICE_CLASS] = DEVICE_CLASS_TEMPERATURE
                            self.device_apparatus_attributes[device_id][attribute[RPC_NAME]] = attribute

                        elif "_percent" in attribute[RPC_NAME]:
                            attribute[ATTR_UNIT_OF_MEASUREMENT] = PERCENTAGE
                            self.device_apparatus_attributes[device_id][attribute[RPC_NAME]] = attribute

                        elif "co2_level" in attribute[RPC_NAME]:
                            attribute[ATTR_UNIT_OF_MEASUREMENT] = CONCENTRATION_PARTS_PER_MILLION
                            attribute[ATTR_DEVICE_CLASS] = DEVICE_CLASS_CO2
                            self.device_apparatus_attributes[device_id][attribute[RPC_NAME]] = attribute
                        
                        #This returns weird numbers on HUAWEI SUN2000
                        elif "_power" in attribute[RPC_NAME]:
                            attribute[ATTR_UNIT_OF_MEASUREMENT] = POWER_WATT
                            attribute[ATTR_DEVICE_CLASS] = DEVICE_CLASS_POWER
                            if "reactive" in attribute[RPC_NAME]:
                                attribute[ATTR_UNIT_OF_MEASUREMENT] = None
                                attribute[ATTR_DEVICE_CLASS] = DEVICE_CLASS_POWER_FACTOR

                            self.device_apparatus_attributes[device_id][attribute[RPC_NAME]] = attribute

                        elif "current" in attribute[RPC_NAME]:
                            attribute[ATTR_UNIT_OF_MEASUREMENT] = ELECTRIC_CURRENT_AMPERE
                            attribute[ATTR_DEVICE_CLASS] = DEVICE_CLASS_CURRENT
                            self.device_apparatus_attributes[device_id][attribute[RPC_NAME]] = attribute
                        
                        elif "voltage" in attribute[RPC_NAME]:
                            attribute[ATTR_UNIT_OF_MEASUREMENT] = ELECTRIC_POTENTIAL_VOLT
                            attribute[ATTR_DEVICE_CLASS] = DEVICE_CLASS_VOLTAGE
                            self.device_apparatus_attributes[device_id][attribute[RPC_NAME]] = attribute
                        
                        elif "frequency" in attribute[RPC_NAME]:
                            attribute[ATTR_UNIT_OF_MEASUREMENT] = FREQUENCY_HERTZ
                            attribute[ATTR_DEVICE_CLASS] = DEVICE_CLASS_FREQUENCY
                            self.device_apparatus_attributes[device_id][attribute[RPC_NAME]] = attribute
                    elif attribute[RPC_TYPE] in [TYPE_STRING]:
                        self.device_apparatus_attributes[device_id][attribute[RPC_NAME]] = attribute
    
    def get_apparatus_attributes(self, device_id = None):
        if device_id != None:
            if device_id in self.device_apparatus_attributes:
                return self.device_apparatus_attributes[device_id]
            else:
                return None
        else:
            return self.device_apparatus_attributes

    def split_list(self, lst, n):  
        for i in range(0, len(lst), n): 
            yield lst[i:i + n]

    @property
    def is_connected(self):
        return self.socket.is_connected()
