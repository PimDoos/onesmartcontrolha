import asyncio
import logging
import struct
from homeassistant.core import HomeAssistant, CoreState
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.util.timeout import TimeoutManager
from socket import error as SOCKET_ERROR

_LOGGER = logging.getLogger(__name__)

from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    Platform, ATTR_UNIT_OF_MEASUREMENT, ATTR_DEVICE_CLASS, CONF_PLATFORM,
    PERCENTAGE,
    CONCENTRATION_PARTS_PER_MILLION,
    TEMP_CELSIUS,
    POWER_WATT,
    ELECTRIC_POTENTIAL_VOLT,
    ELECTRIC_CURRENT_AMPERE,
    FREQUENCY_HERTZ,
    ENERGY_KILO_WATT_HOUR, ENERGY_WATT_HOUR,
    VOLUME_LITERS, TIME_MINUTES,
    
    
)
from homeassistant.components.sensor import (
    SensorDeviceClass, 
    SensorStateClass,
    ATTR_STATE_CLASS
)
from time import time

from .const import *
from .onesmartsocket import OneSmartSocket

class OneSmartWrapper():
    def __init__(self, username, password, host, port, hass: HomeAssistant):
        self.sockets = {
            SOCKET_PUSH: OneSmartSocket(),
            SOCKET_POLL: OneSmartSocket()
        }

        self.runners = []

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

        self.last_update = dict()
        self.last_update[INTERVAL_TRACKER_POLL] = 0
        self.last_update[INTERVAL_TRACKER_DEFINITIONS] = 0

        self.update_flags = []
        self.command_queue = []

        self.last_apparatus_index = dict()
        self.device_apparatus_attributes = dict()
        self.timeout = TimeoutManager()
    
    async def setup(self):
        for socket_name in self.sockets:
            connection_status = await self.connect(socket_name)
            if connection_status != SETUP_SUCCESS:
                return connection_status
        
        # Check cache
        cache = self.get_cache()

        if len(cache[(COMMAND_METER,ACTION_LIST)]) == 0:
            return SETUP_FAIL_CACHE
        elif len(cache[(COMMAND_SITE,ACTION_GET)]) == 0:
            return SETUP_FAIL_CACHE
        elif len(cache[(COMMAND_DEVICE,ACTION_LIST)]) == 0:
            return SETUP_FAIL_CACHE

        async def setup_runners(_event):
            self.runners.append(asyncio.create_task(
                self.run_push()
            ))
            self.runners.append(asyncio.create_task(
                self.run_poll()
            ))
        if self.hass.state != CoreState.running:
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STARTED, setup_runners
            )
        else:
            await setup_runners(None)

        return SETUP_SUCCESS

    async def connect(self, socket_name):
        socket = self.sockets[socket_name]
        try:
            async with self.timeout.async_timeout(SOCKET_CONNECTION_TIMEOUT):
                connection_success = await socket.connect(self.host, self.port)
        except asyncio.TimeoutError:
            _LOGGER.warning(f"Connection timeout out after { SOCKET_CONNECTION_TIMEOUT } seconds")
            return SETUP_FAIL_NETWORK
        except SOCKET_ERROR as e:
            _LOGGER.warning(f"Connection error: { e }")
            return SETUP_FAIL_NETWORK
        else:
            _LOGGER.info(f"Socket { socket_name }: Established network connection")
        
        if not connection_success:
            return SETUP_FAIL_NETWORK

        login_transaction = await socket.authenticate(self.username, self.password)

        login_status = None
        try:
            async with self.timeout.async_timeout(SOCKET_AUTHENTICATION_TIMEOUT):
                while login_status == None:
                    await socket.get_responses()
                    login_status = socket.get_transaction(login_transaction)
        except asyncio.TimeoutError:
            _LOGGER.warning(f"Authentication timeout out after { SOCKET_AUTHENTICATION_TIMEOUT } seconds")
            return SETUP_FAIL_AUTH
        except Exception as e:
            _LOGGER.warning(f"Authentication error: { e }")
            return SETUP_FAIL_AUTH
        else:
            _LOGGER.info(f"Socket { socket_name }: Authentication successful")
        

        if RPC_ERROR in login_status:
            return SETUP_FAIL_AUTH
        else:
            try:
                if socket_name == SOCKET_PUSH:
                    # Subscribe to energy events
                    await self.subscribe(topics=[TOPIC_ENERGY, TOPIC_SITE])
                elif socket_name == SOCKET_POLL:
                    # Set update flags
                    self.set_update_flag((COMMAND_SITE,ACTION_GET))
                    self.set_update_flag((COMMAND_METER,ACTION_LIST))
                    self.set_update_flag((COMMAND_DEVICE,ACTION_LIST))
                    self.last_update[INTERVAL_TRACKER_DEFINITIONS] = time()

                    self.set_update_flag((COMMAND_ENERGY,ACTION_TOTAL))
                    self.last_update[INTERVAL_TRACKER_POLL] = time()
                    
                    # Wait for incoming data
                    await self.handle_update_flags()
            except:
                return SETUP_FAIL_NETWORK
            else:
                return SETUP_SUCCESS

    """Make sure the selected socket object is connected"""
    async def ensure_connected_socket(self, socket_name):
        for connect_attempt in range(0, SOCKET_RECONNECT_RETRIES):
            try:
                # Check if socket status is connected
                if not self.sockets[socket_name].is_connected:
                    connection_status = await self.connect(socket_name)
                    if not connection_status == SETUP_SUCCESS:
                        _LOGGER.warning(f"Reconnect failed. Trying again in {SOCKET_RECONNECT_DELAY} seconds. Attempt { connect_attempt + 1} of { SOCKET_RECONNECT_RETRIES }.")
                        await asyncio.sleep(SOCKET_RECONNECT_DELAY)
                    else:
                        _LOGGER.info(f"Socket { socket_name } successfully reconnected after { connect_attempt + 1 } attempts.")
                    continue

                # Try ping
                ping_result = await self.command_wait(socket_name, COMMAND_PING)

                if ping_result == None:
                    _LOGGER.warning(f"Ping to server timed out. Reconnecting.")
                    await self.connect(socket_name)
                    continue

            except SOCKET_ERROR as e:
                _LOGGER.warning(f"Connection error on socket {socket_name}: '{e}' Reconnecting in {SOCKET_RECONNECT_DELAY} seconds. Attempt { connect_attempt + 1 } of { SOCKET_RECONNECT_RETRIES }.")
                await asyncio.sleep(SOCKET_RECONNECT_DELAY)
                continue
            except Exception as e:
                _LOGGER.error(f"Unknown error while checking the connection: {e}")
            else:
                # Connection successful
                return

        _LOGGER.error(f"Reconnect failed after { SOCKET_RECONNECT_RETRIES } attempts.")

    """Runner for the POLL channel"""
    async def run_poll(self) -> None:
        await self.hass.async_block_till_done()
        socket_name = SOCKET_POLL

        # Loop through received data, blocked by socket.read
        while self.hass.state == CoreState.not_running or self.hass.is_running:
            await self.ensure_connected_socket(socket_name)
            try:
                # Update caches
                if time() > self.last_update[INTERVAL_TRACKER_DEFINITIONS] + SCAN_INTERVAL_DEFINITIONS:
                    _LOGGER.info(f"Updating definitions")
                    self.set_update_flag((COMMAND_SITE,ACTION_GET))
                    self.set_update_flag((COMMAND_METER,ACTION_LIST))
                    # self.set_update_flag((COMMAND_DEVICE,ACTION_LIST))
                    self.last_update[INTERVAL_TRACKER_DEFINITIONS] = time()
                    

                if time() > self.last_update[INTERVAL_TRACKER_POLL] + SCAN_INTERVAL_CACHE:
                    _LOGGER.info(f"Updating cache") 
                    self.set_update_flag((COMMAND_ENERGY,ACTION_TOTAL))
                    self.last_update[INTERVAL_TRACKER_POLL] = time()
                    
                
                await self.handle_update_flags()

                # Update apparatus attributes
                await self.poll_apparatus()

            except Exception as e:
                _LOGGER.error(f"Error in { socket_name } gateway wrapper: { e }")

        _LOGGER.warning(f"Gateway wrapper exited ({ socket_name }).")

    """Runner for the PUSH channel"""
    async def run_push(self) -> None:
        await self.hass.async_block_till_done()

        socket_name = SOCKET_PUSH

        while self.hass.state == CoreState.not_running or self.hass.is_running:
            await self.ensure_connected_socket(socket_name)
            socket = self.sockets[socket_name]
        
            try:
                await socket.get_responses()
                
                # Read events
                events = socket.get_events()
                
                # Handle events
                for event in events:
                    if event[RPC_EVENT] == EVENT_ENERGY_CONSUMPTION and len(self.cache[(COMMAND_METER,ACTION_LIST)]) > 0:
                        for reading in event[RPC_DATA][RPC_VALUES]:
                            meter_value = reading["value"]
                            self.cache[EVENT_ENERGY_CONSUMPTION][reading["id"]] = meter_value
                    elif event[RPC_EVENT] == EVENT_SITE_UPDATE:
                        self.cache[EVENT_SITE_UPDATE] = event[RPC_DATA]

                async_dispatcher_send(self.hass, ONESMART_UPDATE_PUSH)

                # Send queued push commands
                for queued_command in self.command_queue:
                    await self.command(socket_name, queued_command.pop("command"), kwargs = queued_command)


            except Exception as e:
                _LOGGER.error(f"Error in { socket_name } gateway wrapper: { e }")

        _LOGGER.warning(f"Gateway wrapper exited ({ socket_name }).")

    """Shut down the wrapper"""
    async def close(self):
        for task in self.runners:
            task.cancel()

        for socket_name in self.sockets:
            await self.sockets[socket_name].close()
        

    """Send command to the socket and return the transaction id"""
    async def command(self, socket_name, command, **kwargs) -> int:
        socket = self.sockets[socket_name]
        return await socket.send_cmd(command, **kwargs)

    """Send command to the socket and return the transaction data"""
    async def command_wait(self, socket_name, command, **kwargs):
        transaction_id = await self.command(socket_name, command, **kwargs)

        # Wait for transaction to return
        transaction_done = False
        try:
            async with self.timeout.async_timeout(SOCKET_COMMAND_TIMEOUT):
                while not transaction_done:
                    await self.sockets[socket_name].get_responses()
                    transaction = self.sockets[socket_name].get_transaction(transaction_id)
                    transaction_done = transaction != None

        except asyncio.TimeoutError:
            _LOGGER.warning(f"Command on socket { socket_name } timed out after {SOCKET_COMMAND_TIMEOUT} seconds: { command }")
            return None
        else:
            return transaction

    """Subscribe the socket to the specified event topics"""
    async def subscribe(self, topics: list):
        return await self.command(socket_name=SOCKET_PUSH, command=COMMAND_EVENTS, action=ACTION_SUBSCRIBE, topics=topics)


    def set_update_flag(self, flag):
        self.update_flags.append(flag)
    
    async def handle_update_flags(self):
        dispatcher_topics = []

        # Handle update flags
        if len(self.update_flags) > 0:
            _LOGGER.info(f"Handling { len(self.update_flags) } update flags: { self.update_flags }")
        for flag in self.update_flags:
            try:
                flag_command = flag[0]
                flag_action = flag[1]

                if flag_command in [COMMAND_SITE, COMMAND_METER, COMMAND_DEVICE, COMMAND_ENERGY]:
                    transaction = await self.command_wait(SOCKET_POLL, command=flag_command, action=flag_action)
                    if transaction == None:
                        # Skip if transaction returns no data.
                        continue
                    elif not RPC_RESULT in transaction:
                        # TODO: Set depending sensors to unavailable
                        continue
                    else:
                        transaction_result = transaction[RPC_RESULT]

                    if flag_command == COMMAND_SITE:
                        # Fill cache with RPC result
                        self.cache[flag] = transaction_result

                        # Also store in Site Event cache
                        self.cache[EVENT_SITE_UPDATE] = transaction_result

                        if not ONESMART_UPDATE_DEFINITIONS in dispatcher_topics:
                            dispatcher_topics.append(ONESMART_UPDATE_DEFINITIONS)

                    elif flag_command == COMMAND_METER:
                        # Fill cache with RPC result (in corresponding subkey)
                        if RPC_METERS in transaction_result:
                            self.cache[flag] = transaction_result[RPC_METERS]

                            if not ONESMART_UPDATE_DEFINITIONS in dispatcher_topics:
                                dispatcher_topics.append(ONESMART_UPDATE_DEFINITIONS)

                    elif flag_command == COMMAND_ENERGY:
                        if RPC_VALUES in transaction_result:
                            for entry in transaction_result[RPC_VALUES]:
                                self.cache[flag][entry[RPC_ID]] = entry[RPC_VALUE]

                            if not ONESMART_UPDATE_POLL in dispatcher_topics:
                                dispatcher_topics.append(ONESMART_UPDATE_POLL)
                    elif flag_command == COMMAND_DEVICE:
                        if RPC_DEVICES in transaction_result:
                            for entry in transaction_result[RPC_DEVICES]:
                                self.cache[flag][entry[RPC_ID]] = entry
                            await self.discover_apparatus()

                            if not ONESMART_UPDATE_DEFINITIONS in dispatcher_topics:
                                dispatcher_topics.append(ONESMART_UPDATE_DEFINITIONS)

                elif flag_command == COMMAND_APPARATUS:
                    if flag_action == ACTION_LIST:
                        for device_id in self.cache[(COMMAND_DEVICE, ACTION_LIST)]:
                            transaction = await self.command_wait(
                                SOCKET_POLL,
                                command=flag_command, action=flag_action, 
                                id=device_id
                            )
                            if transaction is None:
                                self.cache[flag] = None
                            elif not RPC_RESULT in transaction:
                                self.cache[flag] = None
                            elif not RPC_ATTRIBUTES in transaction[RPC_RESULT]:
                                self.cache[flag] = None
                            else:
                                self.cache[flag] = transaction[RPC_RESULT][RPC_ATTRIBUTES]
            except Exception as e:
                _LOGGER.error(f"Error while handling update flag { flag }: { e }")

        self.update_flags = []        
        
        # Send dispatcher event to update bound entities
        for topic in dispatcher_topics:
            async_dispatcher_send(self.hass, topic)
        
    async def poll_apparatus(self):
        # Update apparatus values
        for device_id in self.device_apparatus_attributes:
            devices = self.cache[(COMMAND_DEVICE,ACTION_LIST)]
            device = devices[device_id]
            device_name = device[RPC_NAME]

            attributes = self.device_apparatus_attributes[device_id]
            attribute_names = [attribute_name for attribute_name in attributes]

            if(len(attributes) == 0):
                continue

            # Only poll MAX_APPARATUS_POLL per cycle
            if not device_id in self.last_apparatus_index:
                attribute_index = 0
            else:
                attribute_index = self.last_apparatus_index[device_id]
                if attribute_index >= len(attribute_names):
                    attribute_index = 0
            
            end_index = attribute_index + MAX_APPARATUS_POLL
            if end_index > len(attribute_names):
                split_attributes = attribute_names[attribute_index:]
            else:
                split_attributes = attribute_names[attribute_index:end_index]

            self.last_apparatus_index[device_id] = end_index

            await self.ensure_connected_socket(SOCKET_POLL)
            transaction = await self.command_wait(
                SOCKET_POLL,
                command=COMMAND_APPARATUS, action=ACTION_GET, 
                id=device_id, attributes=split_attributes
            )
            if transaction == None:
                _LOGGER.warning(f"Could not update {split_attributes} for '{device_name}': Client read timed out")
                continue
            if RPC_ERROR in transaction[RPC_RESULT]:
                _LOGGER.warning(f"Could not update {split_attributes} for '{device_name}': Server responded with {transaction[RPC_RESULT]}")
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
                    _LOGGER.warning(f"Could not update {split_attributes} for '{device_name}': { e } ''")
            
        async_dispatcher_send(self.hass, ONESMART_UPDATE_APPARATUS)

    def get_cache(self, cache_name = None):
        if cache_name == None:
            return self.cache
        else:
            return self.cache[cache_name]

    async def discover_apparatus(self):
        for device_id in self.cache[(COMMAND_DEVICE,ACTION_LIST)]:
            try:
                device = self.cache[(COMMAND_DEVICE,ACTION_LIST)][device_id]
                if(device[RPC_VISIBLE] == False):
                    continue

                transaction = await self.command_wait(SOCKET_POLL, COMMAND_APPARATUS, action=ACTION_LIST, id=device_id)
                attributes = transaction[RPC_RESULT][RPC_ATTRIBUTES]
                self.device_apparatus_attributes[device_id] = dict()

                for attribute in attributes:
                    if attribute[RPC_ACCESS] == ACCESS_READ:
                        if attribute[RPC_TYPE] in [TYPE_NUMBER, TYPE_REAL]:
                            attribute[CONF_PLATFORM] = Platform.SENSOR
                            attribute[ATTR_STATE_CLASS] = SensorStateClass.MEASUREMENT
                            # Temperature sensors
                            if "_temp" in attribute[RPC_NAME]:
                                attribute[ATTR_UNIT_OF_MEASUREMENT] = TEMP_CELSIUS
                                attribute[ATTR_DEVICE_CLASS] = SensorDeviceClass.TEMPERATURE
                                self.device_apparatus_attributes[device_id][attribute[RPC_NAME]] = attribute
                                continue

                            elif "_percent" in attribute[RPC_NAME] or "efficiency" in attribute[RPC_NAME]:
                                attribute[ATTR_UNIT_OF_MEASUREMENT] = PERCENTAGE
                                self.device_apparatus_attributes[device_id][attribute[RPC_NAME]] = attribute
                                continue
                            

                            elif "co2_level" in attribute[RPC_NAME]:
                                attribute[ATTR_UNIT_OF_MEASUREMENT] = CONCENTRATION_PARTS_PER_MILLION
                                attribute[ATTR_DEVICE_CLASS] = SensorDeviceClass.CO2
                                self.device_apparatus_attributes[device_id][attribute[RPC_NAME]] = attribute
                                continue
                            
                            elif "_rpm" in attribute[RPC_NAME]:
                                attribute[ATTR_UNIT_OF_MEASUREMENT] = "rpm"
                                self.device_apparatus_attributes[device_id][attribute[RPC_NAME]] = attribute
                                continue
                            
                            elif "flow_rate_4graph" in attribute[RPC_NAME]:
                                attribute[ATTR_UNIT_OF_MEASUREMENT] = f"{VOLUME_LITERS}/{TIME_MINUTES}"
                                self.device_apparatus_attributes[device_id][attribute[RPC_NAME]] = attribute
                                continue
                            
                            
                            elif "_power" in attribute[RPC_NAME]:
                                attribute[ATTR_UNIT_OF_MEASUREMENT] = POWER_WATT
                                attribute[ATTR_DEVICE_CLASS] = SensorDeviceClass.POWER
                                if "reactive" in attribute[RPC_NAME]:
                                    attribute[ATTR_UNIT_OF_MEASUREMENT] = None
                                    attribute[ATTR_DEVICE_CLASS] = SensorDeviceClass.POWER_FACTOR

                                self.device_apparatus_attributes[device_id][attribute[RPC_NAME]] = attribute
                                continue

                            elif "current" in attribute[RPC_NAME]:
                                attribute[ATTR_UNIT_OF_MEASUREMENT] = ELECTRIC_CURRENT_AMPERE
                                attribute[ATTR_DEVICE_CLASS] = SensorDeviceClass.CURRENT
                                self.device_apparatus_attributes[device_id][attribute[RPC_NAME]] = attribute
                                continue
                            
                            elif "voltage" in attribute[RPC_NAME]:
                                attribute[ATTR_UNIT_OF_MEASUREMENT] = ELECTRIC_POTENTIAL_VOLT
                                attribute[ATTR_DEVICE_CLASS] = SensorDeviceClass.VOLTAGE
                                self.device_apparatus_attributes[device_id][attribute[RPC_NAME]] = attribute
                                continue
                            
                            elif "frequency" in attribute[RPC_NAME]:
                                attribute[ATTR_UNIT_OF_MEASUREMENT] = FREQUENCY_HERTZ
                                attribute[ATTR_DEVICE_CLASS] = SensorDeviceClass.FREQUENCY
                                self.device_apparatus_attributes[device_id][attribute[RPC_NAME]] = attribute
                                continue

                            elif "e_total" == attribute[RPC_NAME]:
                                attribute[ATTR_UNIT_OF_MEASUREMENT] = ENERGY_KILO_WATT_HOUR
                                attribute[ATTR_DEVICE_CLASS] = SensorDeviceClass.ENERGY
                                attribute[ATTR_STATE_CLASS] = SensorStateClass.TOTAL
                                self.device_apparatus_attributes[device_id][attribute[RPC_NAME]] = attribute
                                continue

                            elif "e_day" == attribute[RPC_NAME]:
                                attribute[ATTR_UNIT_OF_MEASUREMENT] = ENERGY_KILO_WATT_HOUR
                                attribute[ATTR_DEVICE_CLASS] = SensorDeviceClass.ENERGY
                                attribute[ATTR_STATE_CLASS] = SensorStateClass.TOTAL_INCREASING
                                self.device_apparatus_attributes[device_id][attribute[RPC_NAME]] = attribute
                                continue
                            
                            elif "_energy_" in attribute[RPC_NAME] and device[RPC_TYPE] == "ENERGY_PROCON_ATW":
                                attribute[ATTR_UNIT_OF_MEASUREMENT] = ENERGY_WATT_HOUR
                                attribute[ATTR_DEVICE_CLASS] = SensorDeviceClass.ENERGY
                                attribute[ATTR_STATE_CLASS] = SensorStateClass.TOTAL_INCREASING
                                self.device_apparatus_attributes[device_id][attribute[RPC_NAME]] = attribute
                                continue

                        elif attribute[RPC_TYPE] in [TYPE_STRING]:
                            attribute[CONF_PLATFORM] = Platform.SENSOR
                            self.device_apparatus_attributes[device_id][attribute[RPC_NAME]] = attribute
                            continue

                    elif attribute[RPC_ACCESS] == ACCESS_READWRITE:
                        if "operating_mode" in attribute[RPC_NAME]:
                            attribute[CONF_PLATFORM] = Platform.SENSOR
                            self.device_apparatus_attributes[device_id][attribute[RPC_NAME]] = attribute
                            continue
            except Exception as e:
                _LOGGER.error(f"Error while discovering attributes for device { device[RPC_NAME] }: { e }")
            
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
        for socket_name in self.sockets:
            if not self.sockets[socket_name].is_connected:
                return False
        return True
