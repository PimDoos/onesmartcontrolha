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
    CONF_ATTRIBUTE,
    SERVICE_TURN_ON, SERVICE_TURN_OFF,
    CONF_DEVICE_ID, ATTR_NAME,
    STATE_ON, STATE_OFF,

)
from homeassistant.components.sensor import (
    SensorDeviceClass, 
    SensorStateClass,
    ATTR_STATE_CLASS
)
from homeassistant.components.light import (
    ColorMode, ATTR_SUPPORTED_COLOR_MODES
)
from homeassistant.components.select import (
    ATTR_OPTIONS, SERVICE_SELECT_OPTION
)

from time import time

from .const import *
from .entitytemplates import ENTITY_TEMPLATES
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
        self.cache[OneSmartEventType.ENERGY_CONSUMPTION] = dict()
        self.cache[(OneSmartCommand.METER,OneSmartAction.LIST)] = dict()
        self.cache[(OneSmartCommand.ENERGY,OneSmartAction.TOTAL)] = dict()
        self.cache[(OneSmartCommand.SITE,OneSmartAction.GET)] = dict()
        self.cache[(OneSmartCommand.DEVICE,OneSmartAction.LIST)] = dict()
        self.cache[(OneSmartCommand.APPARATUS,OneSmartAction.GET)] = dict()
        self.cache[(OneSmartCommand.PRESET,OneSmartAction.LIST)] = dict()
        self.cache[(OneSmartCommand.ROOM,OneSmartAction.LIST)] = dict()

        self.last_update = dict()
        self.last_update[INTERVAL_TRACKER_POLL] = 0
        self.last_update[INTERVAL_TRACKER_DEFINITIONS] = 0

        self.update_flags = []
        self.command_queue = []

        self.last_apparatus_index = dict()
        self.device_apparatus_attributes = dict()
        self.entities = []

        self.timeout = TimeoutManager()
    
    async def setup(self):
        for socket_name in self.sockets:
            connection_status = await self.connect(socket_name)
            if connection_status != OneSmartSetupStatus.SUCCESS:
                return connection_status
        
        # Check cache
        cache = self.get_cache()

        if len(cache[(OneSmartCommand.METER,OneSmartAction.LIST)]) == 0:
            return OneSmartSetupStatus.FAIL_CACHE
        elif len(cache[(OneSmartCommand.SITE,OneSmartAction.GET)]) == 0:
            return OneSmartSetupStatus.FAIL_CACHE
        elif len(cache[(OneSmartCommand.DEVICE,OneSmartAction.LIST)]) == 0:
            return OneSmartSetupStatus.FAIL_CACHE

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

        return OneSmartSetupStatus.SUCCESS

    async def connect(self, socket_name):
        socket = self.sockets[socket_name]
        try:
            async with self.timeout.async_timeout(SOCKET_CONNECTION_TIMEOUT):
                connection_success = await socket.connect(self.host, self.port)
        except asyncio.TimeoutError:
            _LOGGER.warning(f"Connection timeout out after { SOCKET_CONNECTION_TIMEOUT } seconds")
            return OneSmartSetupStatus.FAIL_NETWORK
        except SOCKET_ERROR as e:
            _LOGGER.warning(f"Connection error: { e }")
            return OneSmartSetupStatus.FAIL_NETWORK
        else:
            _LOGGER.info(f"Socket { socket_name }: Established network connection")
        
        if not connection_success:
            return OneSmartSetupStatus.FAIL_NETWORK

        login_transaction = await socket.authenticate(self.username, self.password)

        login_status = None
        try:
            async with self.timeout.async_timeout(SOCKET_AUTHENTICATION_TIMEOUT):
                login_status = await self.wait_for_transaction(socket_name, login_transaction)
        except asyncio.TimeoutError:
            _LOGGER.warning(f"Authentication timeout out after { SOCKET_AUTHENTICATION_TIMEOUT } seconds")
            return OneSmartSetupStatus.FAIL_AUTH
        except Exception as e:
            _LOGGER.warning(f"Authentication error: { e }")
            return OneSmartSetupStatus.FAIL_AUTH
        else:
            _LOGGER.info(f"Socket { socket_name }: Authentication successful")
        

        if OneSmartFieldName.ERROR in login_status:
            return OneSmartSetupStatus.FAIL_AUTH
        else:
            try:
                if socket_name == SOCKET_PUSH:
                    # Subscribe to energy events
                    await self.subscribe(topics=[OneSmartTopic.ENERGY, OneSmartTopic.SITE, OneSmartTopic.PRESET])
                elif socket_name == SOCKET_POLL:
                    # Set update flags
                    self.set_update_flag((OneSmartCommand.SITE,OneSmartAction.GET))
                    self.set_update_flag((OneSmartCommand.METER,OneSmartAction.LIST))
                    self.set_update_flag((OneSmartCommand.DEVICE,OneSmartAction.LIST))
                    self.set_update_flag((OneSmartCommand.PRESET,OneSmartAction.LIST))
                    self.set_update_flag((OneSmartCommand.ROOM,OneSmartAction.LIST))
                    self.last_update[INTERVAL_TRACKER_DEFINITIONS] = time()

                    self.set_update_flag((OneSmartCommand.ENERGY,OneSmartAction.TOTAL))
                    self.last_update[INTERVAL_TRACKER_POLL] = time()
                    
                    # Wait for incoming data
                    await self.handle_update_flags()

                    await self.discover_entities()
            except:
                return OneSmartSetupStatus.FAIL_NETWORK
            else:
                return OneSmartSetupStatus.SUCCESS

    """Make sure the selected socket object is connected"""
    async def ensure_connected_socket(self, socket_name):
        socket = self.sockets[socket_name]
        force_reconnect = False
        for connect_attempt in range(0, SOCKET_RECONNECT_RETRIES):
            try:
                # Check if socket status is connected
                if not socket.is_connected or force_reconnect:
                    connection_status = await self.connect(socket_name)
                    if not connection_status == OneSmartSetupStatus.SUCCESS:
                        _LOGGER.warning(f"Reconnect failed. Trying again in {SOCKET_RECONNECT_DELAY} seconds. Attempt { connect_attempt + 1} of { SOCKET_RECONNECT_RETRIES }.")
                        await asyncio.sleep(SOCKET_RECONNECT_DELAY)
                    else:
                        _LOGGER.info(f"Socket { socket_name } successfully reconnected after { connect_attempt + 1 } attempts.")
                        force_reconnect = False
                    continue

                # Try ping
                ping_result = await self.command_wait(socket_name, OneSmartCommand.PING)

                if ping_result == None:
                    _LOGGER.warning(f"Ping to server timed out. Reconnecting.")
                    force_reconnect = True
                    continue

            except SOCKET_ERROR as e:
                _LOGGER.warning(f"Connection error on socket {socket_name}: '{e}' Reconnecting in {SOCKET_RECONNECT_DELAY} seconds. Attempt { connect_attempt + 1 } of { SOCKET_RECONNECT_RETRIES }.")
                force_reconnect = True
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
                    self.set_update_flag((OneSmartCommand.SITE,OneSmartAction.GET))
                    self.set_update_flag((OneSmartCommand.METER,OneSmartAction.LIST))
                    # self.set_update_flag((OneSmartCommand.DEVICE,OneSmartAction.LIST))
                    # self.set_update_flag((OneSmartCommand.ROOM,OneSmartAction.LIST))
                    self.set_update_flag((OneSmartCommand.PRESET,OneSmartAction.LIST))
                    self.last_update[INTERVAL_TRACKER_DEFINITIONS] = time()
                    

                if time() > self.last_update[INTERVAL_TRACKER_POLL] + SCAN_INTERVAL_CACHE:
                    _LOGGER.info(f"Updating cache") 
                    self.set_update_flag((OneSmartCommand.ENERGY,OneSmartAction.TOTAL))
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
                async with self.timeout.async_timeout(SOCKET_COMMAND_TIMEOUT):
                    await socket.get_responses()
                    
                    # Read events
                    events = socket.get_events()
                    
                    # Handle events
                    for event in events:
                        if event[OneSmartFieldName.EVENT] == OneSmartEventType.ENERGY_CONSUMPTION and len(self.cache[(OneSmartCommand.METER,OneSmartAction.LIST)]) > 0:
                            for reading in event[OneSmartFieldName.DATA][OneSmartFieldName.VALUES]:
                                meter_value = reading["value"]
                                self.cache[OneSmartEventType.ENERGY_CONSUMPTION][reading["id"]] = meter_value
                        elif event[OneSmartFieldName.EVENT] == OneSmartEventType.SITE_UPDATE:
                            self.cache[OneSmartEventType.SITE_UPDATE] = event[OneSmartFieldName.DATA]
                        elif event[OneSmartFieldName.EVENT] == OneSmartEventType.PRESET_PERFORM:
                            preset_id = event[OneSmartFieldName.DATA][OneSmartFieldName.ID]
                            self.cache[(OneSmartCommand.PRESET,OneSmartAction.LIST)][preset_id][OneSmartFieldName.ACTIVE] = True
                            self.set_update_flag((OneSmartCommand.PRESET,OneSmartAction.LIST))
                            async_dispatcher_send(self.hass, OneSmartUpdateTopic.POLL)

                    async_dispatcher_send(self.hass, OneSmartUpdateTopic.PUSH)

                    # Send queued push commands
                    for queued_command in self.command_queue:
                        await self.command(socket_name, queued_command.pop("command"), kwargs = queued_command)
            except TimeoutError:
                _LOGGER.debug(f"Timeout in { socket_name } while waiting for responses")

            except Exception as e:
                _LOGGER.error(f"Error in { socket_name } gateway wrapper: { e }")

        _LOGGER.warning(f"Gateway wrapper exited ({ socket_name }).")

    """Shut down the wrapper"""
    async def close(self):
        for task in self.runners:
            task.cancel()

        for socket_name in self.sockets:
            try:
                await self.sockets[socket_name].close()
            except:
                pass
        

    """Send command to the socket and return the transaction id"""
    async def command(self, socket_name, command: OneSmartCommand, **kwargs) -> int:
        socket = self.sockets[socket_name]
        return await socket.send_cmd(command, **kwargs)

    """Send command to the socket and return the transaction data"""
    async def command_wait(self, socket_name, command: OneSmartCommand, **kwargs) -> dict:
        transaction_id = await self.command(socket_name, command, **kwargs)

        # Wait for transaction to return
        try:
            async with self.timeout.async_timeout(SOCKET_COMMAND_TIMEOUT):
                transaction = await self.wait_for_transaction(socket_name, transaction_id)

        except asyncio.TimeoutError:
            _LOGGER.warning(f"Command on socket { socket_name } timed out after {SOCKET_COMMAND_TIMEOUT} seconds: { command }")
            return None
        else:
            return transaction

    async def wait_for_transaction(self, socket_name, transaction_id):
        transaction_done = False
        first_loop = True
        while not transaction_done:
            if first_loop:
                first_loop = False
            else:
                # Wait for a bit if the first loop did not retrieve a result
                await asyncio.sleep(1)
            await self.sockets[socket_name].get_responses()
            transaction = self.sockets[socket_name].get_transaction(transaction_id)
            transaction_done = transaction != None
            
        return transaction
        

    """Subscribe the socket to the specified event topics"""
    async def subscribe(self, topics: list):
        return await self.command(socket_name=SOCKET_PUSH, command=OneSmartCommand.EVENTS, action=OneSmartAction.SUBSCRIBE, topics=topics)


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

                if flag_command in [OneSmartCommand.SITE, OneSmartCommand.METER, OneSmartCommand.DEVICE, OneSmartCommand.ENERGY, OneSmartCommand.ROOM, OneSmartCommand.PRESET]:
                    transaction = await self.command_wait(SOCKET_POLL, command=flag_command, action=flag_action)
                    if transaction == None:
                        # Skip if transaction returns no data.
                        continue
                    elif not OneSmartFieldName.RESULT in transaction:
                        # TODO: Set depending sensors to unavailable
                        continue
                    else:
                        transaction_result = transaction[OneSmartFieldName.RESULT]

                    if flag_command == OneSmartCommand.SITE:
                        # Fill cache with RPC result
                        self.cache[flag] = transaction_result

                        # Also store in Site Event cache
                        self.cache[OneSmartEventType.SITE_UPDATE] = transaction_result

                        if not OneSmartUpdateTopic.DEFINITIONS in dispatcher_topics:
                            dispatcher_topics.append(OneSmartUpdateTopic.DEFINITIONS)

                    elif flag_command == OneSmartCommand.METER:
                        # Fill cache with RPC result (in corresponding subkey)
                        if OneSmartFieldName.METERS in transaction_result:
                            self.cache[flag] = transaction_result[OneSmartFieldName.METERS]

                            if not OneSmartUpdateTopic.DEFINITIONS in dispatcher_topics:
                                dispatcher_topics.append(OneSmartUpdateTopic.DEFINITIONS)

                    elif flag_command == OneSmartCommand.ENERGY:
                        if OneSmartFieldName.VALUES in transaction_result:
                            for entry in transaction_result[OneSmartFieldName.VALUES]:
                                self.cache[flag][entry[OneSmartFieldName.ID]] = entry[OneSmartFieldName.VALUE]

                            if not OneSmartUpdateTopic.POLL in dispatcher_topics:
                                dispatcher_topics.append(OneSmartUpdateTopic.POLL)
                    elif flag_command == OneSmartCommand.DEVICE:
                        if OneSmartFieldName.DEVICES in transaction_result:
                            for entry in transaction_result[OneSmartFieldName.DEVICES]:
                                self.cache[flag][entry[OneSmartFieldName.ID]] = entry
                            
                            if not OneSmartUpdateTopic.DEFINITIONS in dispatcher_topics:
                                dispatcher_topics.append(OneSmartUpdateTopic.DEFINITIONS)
                    elif flag_command == OneSmartCommand.PRESET:
                        if OneSmartFieldName.PRESETS in transaction_result:
                            for entry in transaction_result[OneSmartFieldName.PRESETS]:
                                self.cache[flag][entry[OneSmartFieldName.ID]] = entry

                            if not OneSmartUpdateTopic.POLL in dispatcher_topics:
                                dispatcher_topics.append(OneSmartUpdateTopic.POLL)
                    elif flag_command == OneSmartCommand.ROOM:
                        if OneSmartFieldName.ROOMS in transaction_result:
                            for entry in transaction_result[OneSmartFieldName.ROOMS]:
                                self.cache[flag][entry[OneSmartFieldName.ID]] = entry

                            if not OneSmartUpdateTopic.DEFINITIONS in dispatcher_topics:
                                dispatcher_topics.append(OneSmartUpdateTopic.DEFINITIONS)

                elif flag_command == OneSmartCommand.APPARATUS:
                    if flag_action == OneSmartAction.LIST:
                        for device_id in self.cache[(OneSmartCommand.DEVICE, OneSmartAction.LIST)]:
                            transaction = await self.command_wait(
                                SOCKET_POLL,
                                command=flag_command, action=flag_action, 
                                id=device_id
                            )
                            if transaction is None:
                                self.cache[flag] = None
                            elif not OneSmartFieldName.RESULT in transaction:
                                self.cache[flag] = None
                            elif not OneSmartFieldName.ATTRIBUTES in transaction[OneSmartFieldName.RESULT]:
                                self.cache[flag] = None
                            else:
                                self.cache[flag] = transaction[OneSmartFieldName.RESULT][OneSmartFieldName.ATTRIBUTES]
            except Exception as e:
                _LOGGER.error(f"Error while handling update flag { flag }: { e }")

        self.update_flags = []        
        
        # Send dispatcher event to update bound entities
        for topic in dispatcher_topics:
            async_dispatcher_send(self.hass, topic)
        
    async def poll_apparatus(self):
        # Update apparatus values
        for device_id in self.device_apparatus_attributes:
            devices = self.cache[(OneSmartCommand.DEVICE,OneSmartAction.LIST)]
            device = devices[device_id]
            device_name = device[OneSmartFieldName.NAME]

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
                command=OneSmartCommand.APPARATUS, action=OneSmartAction.GET, 
                id=device_id, attributes=split_attributes
            )
            if transaction == None:
                _LOGGER.warning(f"Could not update {split_attributes} for '{device_name}': Client read timed out")
                continue
            if OneSmartFieldName.ERROR in transaction[OneSmartFieldName.RESULT]:
                _LOGGER.warning(f"Could not update {split_attributes} for '{device_name}': Server responded with {transaction[OneSmartFieldName.RESULT]}")
            else:
                try:
                    values_new = transaction[OneSmartFieldName.RESULT][OneSmartFieldName.ATTRIBUTES]
                    for value_name in values_new:
                        value = values_new[value_name]
                        if isinstance(value, int):
                            bit_length = value.bit_length()
                            if bit_length >= BIT_LENGTH_DOUBLE - 4:
                                values_new[value_name] = struct.unpack("<d",value.to_bytes(8,byteorder="little", signed=True))[0]
                                if values_new[value_name] < 1:
                                    values_new[value_name] = 0

                    if device_id in self.cache[(OneSmartCommand.APPARATUS,OneSmartAction.GET)]:
                        values_cache = self.cache[(OneSmartCommand.APPARATUS,OneSmartAction.GET)][device_id]
                    else:
                        values_cache = {}
                    self.cache[(OneSmartCommand.APPARATUS,OneSmartAction.GET)][device_id] = values_cache | values_new
                except Exception as e:
                    _LOGGER.warning(f"Could not update {split_attributes} for '{device_name}': { e } ''")
            
        async_dispatcher_send(self.hass, OneSmartUpdateTopic.APPARATUS)

    def get_cache(self, cache_name = None):
        if cache_name == None:
            return self.cache
        else:
            return self.cache[cache_name]

    async def discover_entities(self):
        self.entities = dict()
        for platform_name in Platform:
            self.entities[platform_name] = list()

        # Discover device attributes
        for device_id in self.cache[(OneSmartCommand.DEVICE,OneSmartAction.LIST)]:
            try:
                device = self.cache[(OneSmartCommand.DEVICE,OneSmartAction.LIST)][device_id]
                device_name = device[OneSmartFieldName.NAME]
                if(device[OneSmartFieldName.VISIBLE] == False):
                    continue

                transaction = await self.command_wait(SOCKET_POLL, OneSmartCommand.APPARATUS, action=OneSmartAction.LIST, id=device_id)
                attributes = transaction[OneSmartFieldName.RESULT][OneSmartFieldName.ATTRIBUTES]
                self.device_apparatus_attributes[device_id] = dict()
                
                device_attribute_names = [attribute[OneSmartFieldName.NAME] for attribute in attributes]

                for platform_name in ENTITY_TEMPLATES:
                    for entity_template in ENTITY_TEMPLATES[platform_name]:
                        entity_template_keys = [value for value in list(entity_template.values()) if isinstance(value, str)]
                        if all(attribute_name in device_attribute_names for attribute_name in entity_template_keys):
                            entity = dict()
                            entity[CONF_PLATFORM] = platform_name
                            entity[ONESMART_CACHE] = (OneSmartCommand.APPARATUS,OneSmartAction.GET)
                            entity[ATTR_NAME] = device_name
                            entity[CONF_DEVICE_ID] = device_id
                            entity[OneSmartUpdateTopic] = OneSmartUpdateTopic.APPARATUS
                            entity = entity | entity_template

                            for entity_template_key in entity_template:
                                key = entity_template[entity_template_key]
                                if isinstance(key, str):
                                    entity[entity_template_key] = f"{device_id}.{key}"

                            # Append the entity
                            self.entities[entity[CONF_PLATFORM]].append(entity)

                            # Mark the attribute for polling
                            for attribute_name in entity_template_keys:
                                self.device_apparatus_attributes[device_id][attribute_name] = attribute_name
                        
                    

                for attribute in attributes:
                    attribute_name: str = attribute[OneSmartFieldName.NAME]
                    entity = dict()
                    entity[ONESMART_CACHE] = (OneSmartCommand.APPARATUS,OneSmartAction.GET)
                    entity[ONESMART_KEY] = f"{device_id}.{attribute_name}"
                    entity[CONF_DEVICE_ID] = device_id
                    entity[ATTR_NAME] = f"{device_name} {attribute_name.replace('_',' ').title()}"
                    entity[OneSmartUpdateTopic] = OneSmartUpdateTopic.APPARATUS
                    use_entity = False

                    if attribute[OneSmartFieldName.ACCESS] == OneSmartAccessLevel.READ:
                        if attribute[OneSmartFieldName.TYPE] in [OneSmartDataType.NUMBER, OneSmartDataType.REAL]:
                            
                            entity[CONF_PLATFORM] = Platform.SENSOR
                            entity[ATTR_STATE_CLASS] = SensorStateClass.MEASUREMENT
                            
                            # Temperature sensors
                            if "_temp" in attribute_name:
                                entity[ATTR_UNIT_OF_MEASUREMENT] = TEMP_CELSIUS
                                entity[ATTR_DEVICE_CLASS] = SensorDeviceClass.TEMPERATURE
                                use_entity = True

                            elif "_percent" in attribute_name or "efficiency" in attribute_name:
                                entity[ATTR_UNIT_OF_MEASUREMENT] = PERCENTAGE
                                use_entity = True
                            
                            elif "co2_level" in attribute_name:
                                entity[ATTR_UNIT_OF_MEASUREMENT] = CONCENTRATION_PARTS_PER_MILLION
                                entity[ATTR_DEVICE_CLASS] = SensorDeviceClass.CO2
                                use_entity = True
                            
                            elif "_rpm" in attribute_name:
                                entity[ATTR_UNIT_OF_MEASUREMENT] = "rpm"
                                use_entity = True
                            
                            elif "flow_rate_4graph" in attribute_name:
                                entity[ATTR_UNIT_OF_MEASUREMENT] = f"{VOLUME_LITERS}/{TIME_MINUTES}"
                                use_entity = True
                              
                            elif "_power" in attribute_name:
                                entity[ATTR_UNIT_OF_MEASUREMENT] = POWER_WATT
                                entity[ATTR_DEVICE_CLASS] = SensorDeviceClass.POWER
                                if "reactive" in attribute_name:
                                    entity[ATTR_UNIT_OF_MEASUREMENT] = None
                                    entity[ATTR_DEVICE_CLASS] = SensorDeviceClass.POWER_FACTOR

                                use_entity = True

                            elif "current" in attribute_name:
                                entity[ATTR_UNIT_OF_MEASUREMENT] = ELECTRIC_CURRENT_AMPERE
                                entity[ATTR_DEVICE_CLASS] = SensorDeviceClass.CURRENT
                                use_entity = True
                            
                            elif "voltage" in attribute_name:
                                entity[ATTR_UNIT_OF_MEASUREMENT] = ELECTRIC_POTENTIAL_VOLT
                                entity[ATTR_DEVICE_CLASS] = SensorDeviceClass.VOLTAGE
                                use_entity = True
                            
                            elif "frequency" in attribute_name:
                                entity[ATTR_UNIT_OF_MEASUREMENT] = FREQUENCY_HERTZ
                                entity[ATTR_DEVICE_CLASS] = SensorDeviceClass.FREQUENCY
                                use_entity = True

                            elif "e_total" == attribute_name:
                                entity[ATTR_UNIT_OF_MEASUREMENT] = ENERGY_KILO_WATT_HOUR
                                entity[ATTR_DEVICE_CLASS] = SensorDeviceClass.ENERGY
                                entity[ATTR_STATE_CLASS] = SensorStateClass.TOTAL
                                use_entity = True

                            elif "e_day" == attribute_name:
                                entity[ATTR_UNIT_OF_MEASUREMENT] = ENERGY_KILO_WATT_HOUR
                                entity[ATTR_DEVICE_CLASS] = SensorDeviceClass.ENERGY
                                entity[ATTR_STATE_CLASS] = SensorStateClass.TOTAL_INCREASING
                                use_entity = True
                            
                            elif "_energy_" in attribute_name and device[OneSmartFieldName.TYPE] == "ENERGY_PROCON_ATW":
                                entity[ATTR_UNIT_OF_MEASUREMENT] = ENERGY_WATT_HOUR
                                entity[ATTR_DEVICE_CLASS] = SensorDeviceClass.ENERGY
                                entity[ATTR_STATE_CLASS] = SensorStateClass.TOTAL_INCREASING
                                use_entity = True

                        elif attribute[OneSmartFieldName.TYPE] in [OneSmartDataType.STRING]:
                            entity[CONF_PLATFORM] = Platform.SENSOR
                            use_entity = True

                    elif attribute[OneSmartFieldName.ACCESS] == OneSmartAccessLevel.READWRITE:
                        if "operating_mode" in attribute_name:
                            entity[CONF_PLATFORM] = Platform.SENSOR
                            use_entity = True
                        elif OneSmartFieldName.ENUM in attribute:
                            enum_values = attribute[OneSmartFieldName.ENUM]
                            if "on" in enum_values and "off" in enum_values:
                                entity[CONF_PLATFORM] = Platform.SWITCH
                                entity[SERVICE_TURN_ON] = {
                                    "command":OneSmartCommand.APPARATUS, 
                                    OneSmartFieldName.ACTION:OneSmartAction.SET, 
                                    OneSmartFieldName.ID:device_id, 
                                    OneSmartFieldName.ATTRIBUTES:{attribute_name:"on"}
                                }
                                entity[SERVICE_TURN_OFF] = {
                                    "command":OneSmartCommand.APPARATUS, 
                                    OneSmartFieldName.ACTION:OneSmartAction.SET, 
                                    OneSmartFieldName.ID:device_id, 
                                    OneSmartFieldName.ATTRIBUTES:{attribute_name:"off"}
                                }
            
                                entity[STATE_ON] = "on"
                                entity[STATE_OFF] = "off"
                                use_entity = True
                        elif "outputvalue" == attribute_name:
                            if device[OneSmartFieldName.GROUP] == OneSmartGroupType.LIGHTS:
                                if attribute[OneSmartFieldName.TYPE] == OneSmartDataType.NUMBER:
                                    entity[CONF_PLATFORM] = Platform.LIGHT
                                    if "LID" in device[OneSmartFieldName.TYPE]:
                                        outputmode_response = await self.command_wait(SOCKET_POLL, 
                                            command=OneSmartCommand.APPARATUS,
                                            action=OneSmartAction.GET,
                                            id=device_id,
                                            attributes=[OneSmartFieldName.OUTPUT_MODE]
                                        )
                                        output_mode = outputmode_response.get(OneSmartFieldName.RESULT, dict()).get(OneSmartFieldName.ATTRIBUTES, dict()).get(OneSmartFieldName.OUTPUT_MODE, OneSmartOutputMode.OFF)
                                        if output_mode == OneSmartOutputMode.DIMMER:
                                            entity[ATTR_SUPPORTED_COLOR_MODES] = [ColorMode.BRIGHTNESS]
                                        else:
                                            entity[ATTR_SUPPORTED_COLOR_MODES] = [ColorMode.ONOFF]

                                        
                                        entity[SERVICE_TURN_ON] = {
                                            "command":OneSmartCommand.APPARATUS, 
                                            OneSmartFieldName.ACTION:OneSmartAction.SET, 
                                            OneSmartFieldName.ID:device_id, 
                                            OneSmartFieldName.ATTRIBUTES:{attribute_name:COMMAND_REPLACE_VALUE}
                                        }
                                    else:
                                        entity[ATTR_SUPPORTED_COLOR_MODES] = [ColorMode.ONOFF]
                                        entity[SERVICE_TURN_ON] = {
                                            "command":OneSmartCommand.APPARATUS, 
                                            OneSmartFieldName.ACTION:OneSmartAction.SET, 
                                            OneSmartFieldName.ID:device_id, 
                                            OneSmartFieldName.ATTRIBUTES:{attribute_name:255}
                                        }

                                    entity[STATE_OFF] = 0
                                    entity[ATTR_NAME] = device_name
                                    
                                    entity[SERVICE_TURN_OFF] = {
                                        "command":OneSmartCommand.APPARATUS, 
                                        OneSmartFieldName.ACTION:OneSmartAction.SET, 
                                        OneSmartFieldName.ID:device_id, 
                                        OneSmartFieldName.ATTRIBUTES:{attribute_name:0}
                                    }
                                    use_entity = True

                    if use_entity == True:
                        # Append the entity
                        self.entities[entity[CONF_PLATFORM]].append(entity)

                        # Mark the attribute for polling
                        self.device_apparatus_attributes[device_id][attribute[OneSmartFieldName.NAME]] = attribute

                
                
            except Exception as e:
                _LOGGER.error(f"Error while discovering entities for device { device[OneSmartFieldName.NAME] }: { e }")

        # Preset entities
        for room_id in self.cache[(OneSmartCommand.ROOM,OneSmartAction.LIST)]:
            try:
                room = self.cache[(OneSmartCommand.ROOM,OneSmartAction.LIST)][room_id]
                room_name = room[OneSmartFieldName.NAME]
                if(room[OneSmartFieldName.VISIBLE] == False):
                    continue

                room_presets = dict()
                for group_name in OneSmartGroupType:
                    room_presets[group_name] = dict()
            
                for preset_id in self.cache[(OneSmartCommand.PRESET,OneSmartAction.LIST)]:
                    preset = self.cache[(OneSmartCommand.PRESET,OneSmartAction.LIST)][preset_id]
                    if preset[OneSmartCommand.ROOM] == room_id:
                        room_presets[preset[OneSmartFieldName.GROUP]][preset[OneSmartFieldName.TYPE]] = preset

                for group_name in room_presets:
                    group_presets = room_presets[group_name]

                    entity = dict()
                    entity[ONESMART_CACHE] = (OneSmartCommand.PRESET,OneSmartAction.LIST)
                    entity[OneSmartUpdateTopic] = OneSmartUpdateTopic.POLL
                    entity[CONF_PLATFORM] = Platform.SELECT
                    entity[ATTR_OPTIONS] = dict()
                    entity[SERVICE_SELECT_OPTION] = dict()
                    entity[ATTR_NAME] = f"{room_name} {group_name.title()} Preset"
                    entity[ONESMART_KEY] = f"{room_id}.{group_name}"

                    for preset_type in group_presets:
                        preset = group_presets[preset_type]
                        preset_name = preset[OneSmartFieldName.NAME]
                        preset_id = preset[OneSmartFieldName.ID]
                        entity[ATTR_OPTIONS][f"{preset_id}.{OneSmartFieldName.ACTIVE}"] = preset_name
                        entity[SERVICE_SELECT_OPTION][preset_name] = {
                            "command":OneSmartCommand.PRESET,
                            OneSmartFieldName.ACTION:OneSmartAction.PERFORM,
                            OneSmartFieldName.ID:preset_id
                        }

                    if len(group_presets) >= 2:
                        # Append the entity
                        self.entities[entity[CONF_PLATFORM]].append(entity)

            except Exception as e:
                _LOGGER.error(f"Error while discovering entities for room { room[OneSmartFieldName.NAME] }: { e }")
            
    # def get_apparatus_attributes(self, device_id = None):
    #     if device_id != None:
    #         if device_id in self.device_apparatus_attributes:
    #             return self.device_apparatus_attributes[device_id]
    #         else:
    #             return None
    #     else:
    #         return self.device_apparatus_attributes
    
    def get_platform_entities(self, platform: Platform):
        if platform in self.entities:
            return self.entities[platform]
        else:
            return list()

    def split_list(self, lst, n):  
        for i in range(0, len(lst), n): 
            yield lst[i:i + n]

    @property
    def is_connected(self):
        for socket_name in self.sockets:
            if not self.sockets[socket_name].is_connected:
                return False
        return True
