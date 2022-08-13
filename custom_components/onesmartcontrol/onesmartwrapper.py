

from homeassistant.core import HomeAssistant, CoreState
from homeassistant.helpers.dispatcher import async_dispatcher_send
from functools import partial

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
        self.cache[COMMAND_METER] = dict()
        self.cache[COMMAND_ENERGY] = dict()
        self.cache[COMMAND_SITE] = dict()

        self.update_flags = []
    
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
            
            # Make sure socket is connected. Reconnect if neccessary
            if not self.socket.is_connected():
                await self.connect()

            # Keep the connection alive
            if time() - last_ping > PING_INTERVAL:
                await self.hass.async_add_executor_job(
                    self.socket.ping
                )
                last_ping = time()

            # Read data from the socket
            await self.hass.async_add_executor_job(
                self.socket.get_responses
            )

            # Handle events (push updates)
            await self.handle_events()

            # Handle polling updates
            await self.handle_update_flags()

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
        while not transaction_done:
            # print("{} WAIT".format(transaction_id))
            await self.hass.async_add_executor_job(
                self.socket.get_responses
            )

            transaction = await self.hass.async_add_executor_job(
                self.socket.get_transaction, transaction_id
            )
            transaction_done = transaction != None
        
        # print("{} DONE".format(transaction_id))
        return transaction

    """Subscribe the socket to the specified event topics"""
    async def subscribe(self, topics: list):
        return await self.command(command=COMMAND_EVENTS, action=ACTION_SUBSCRIBE, topics=topics)

    """Update id-name mappings"""
    async def update_definitions(self):
        self.set_update_flag(COMMAND_METER)
        
    """Update polling cache"""
    async def update_cache(self):
        self.set_update_flag(COMMAND_SITE)
        self.set_update_flag(COMMAND_ENERGY)

    def set_update_flag(self, flag):
        self.update_flags.append(flag)
    
    async def handle_update_flags(self):
        dispatcher_topics = []

        # Handle update flags
        for flag in self.update_flags:
            
            if flag in [COMMAND_SITE]:
                # Fill cache with RPC result
                transaction = await self.command(command=flag, action=ACTION_GET)
                self.cache[flag] = transaction[RPC_RESULT]

                if not ONESMART_UPDATE_DEFINITIONS in dispatcher_topics:
                    dispatcher_topics.append(ONESMART_UPDATE_DEFINITIONS)
            elif flag in [COMMAND_METER]:
                # Fill cache with RPC result
                transaction = await self.command(command=flag, action=ACTION_LIST)
                self.cache[flag] = transaction[RPC_RESULT][RPC_METERS]

                if not ONESMART_UPDATE_DEFINITIONS in dispatcher_topics:
                    dispatcher_topics.append(ONESMART_UPDATE_DEFINITIONS)
            elif flag in [COMMAND_ENERGY]:
                # Fill cache with mapping result
                if flag == COMMAND_ENERGY:
                    action = ACTION_TOTAL
                    data_field = RPC_VALUES
                    entry_field = RPC_VALUE
                    if not ONESMART_UPDATE_POLL in dispatcher_topics:
                        dispatcher_topics.append(ONESMART_UPDATE_POLL)

                transaction = await self.command(command=flag, action=action)
                for entry in transaction[RPC_RESULT][data_field]:
                    if entry_field != None:
                        self.cache[flag][entry[RPC_ID]] = entry[entry_field]
                
        self.update_flags = []        
        
        # Send dispatcher event to update bound entities
        for topic in dispatcher_topics:
            async_dispatcher_send(self.hass, topic)

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
            if event[RPC_EVENT] == EVENT_ENERGY_CONSUMPTION and len(self.cache[COMMAND_METER]) > 0:
                for reading in event[RPC_DATA][RPC_VALUES]:
                    meter_value = reading["value"]
                    self.cache[EVENT_ENERGY_CONSUMPTION][reading["id"]] = meter_value
        async_dispatcher_send(self.hass, ONESMART_UPDATE_PUSH)
                    
    @property
    def is_connected(self):
        return self.socket.is_connected()
