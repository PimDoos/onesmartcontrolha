"""One Smart Control JSON-RPC Socket implementation"""
import asyncio
from hashlib import sha1
import json
import logging
import ssl
from .const import *

_LOGGER = logging.getLogger(__name__)

class OneSmartSocket:

    def __init__(self):
        # Initialize SSLContext without certificate checking
        self._ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE

        self._reader = None
        self._writer = None

        # Allow old ciphers
        self._ssl_context.set_ciphers('DEFAULT')

        # Initialize caches
        self._response_cache = dict()
        self._event_cache = []

    async def connect(self, host, port):
        if self._writer:
            try:
                self.close()
            except:
                pass

        self._reader, self._writer = await asyncio.open_connection(host, port, ssl=self._ssl_context)

        self._transaction_count = 0
        return self.is_connected

    async def authenticate(self, username, password):
        password_hash = sha1(password.encode()).hexdigest()
        return await self.send_cmd(command=OneSmartCommand.AUTHENTICATE, username=username, password=password_hash)

    async def close(self):
        try:
            self._writer.close()
            await self._writer.wait_closed()
            self._writer = None
            self._reader = None
        except ssl.SSLEOFError:
            pass

    @property
    def is_connected(self):
        if self._reader is None or self._writer is None:
            return False
        elif self._reader.at_eof() or self._writer.is_closing():
            return False
        else:
            return True

    """Start a new transaction"""
    async def send_cmd(self, command, **kwargs):
        self._transaction_count += 1
        transaction_id = self._transaction_count
        rpc_message = { OneSmartFieldName.COMMAND:command, OneSmartFieldName.TRANSACTION:transaction_id } | kwargs
        rpc_data = json.dumps(rpc_message) + "\r\n"
        self._writer.write(rpc_data.encode())
        await self._writer.drain()
        self._response_cache[transaction_id] = None

        return transaction_id
    
    async def ping(self):
        return await self.send_cmd(command=OneSmartCommand.PING)

    """Fetch outstanding responses and cache them by transaction ID"""
    async def get_responses(self):
        data = bytes()
    
        done_reading = False
        # Stitch split packages
        while not done_reading:
            read_bytes = await self._reader.read(SOCKET_BUFFER_SIZE)
            if len(read_bytes) == 0:
                # No data available
                break
            elif len(read_bytes) == SOCKET_BUFFER_SIZE:
                data += read_bytes
                #_LOGGER.debug(f"Packet is { len(data) } bytes, waiting for more")
                continue
            elif read_bytes[-2:] != b"\r\n":
                data += read_bytes
                #_LOGGER.debug(f"Packet does not end with linefeed, waiting for more data")
            else:
                data += read_bytes
                done_reading = True
                
        messages = data.split(b"\r\n")
        
        for message_bytes in messages:
            if len(message_bytes) > 8:
                reply = message_bytes.decode()
                try:
                    reply_data = json.loads(reply)
                    if not reply_data == None:
                        if OneSmartFieldName.TRANSACTION in reply_data:
                            # Received message is a transaction response
                            transaction_id = reply_data[OneSmartFieldName.TRANSACTION]
                            self._response_cache[transaction_id] = reply_data
                            
                        else:
                            # Message is not part of a transaction. Add to eventqueue.
                            self._event_cache.append(reply_data)
                except json.JSONDecodeError:
                    _LOGGER.warning("JSON Decode failed:")
                    _LOGGER.debug(f"Reply data: \"{ reply }\"")
                except Exception as e:
                    _LOGGER.error(f"Unexpected error while reading from the socket: { e }")


    """Get the result of a cached transaction"""
    def get_transaction(self, transaction_id):
        if transaction_id in self._response_cache:
            transaction = self._response_cache.pop(transaction_id)
            return transaction
        else:
            return None
    
    """Return events and clear the cache"""
    def get_events(self):
        events = self._event_cache
        self._event_cache = []
        return events
