import asyncio
import json
import logging
import queue
from typing import Union, Optional
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

import dateutil.parser
import websockets

from togglws import values


class TogglSocketMessage:
    def __new__(cls, model, definition):
        if cls is TogglSocketMessage:
            if model == values.M_TIME_ENTRY:
                return super(TogglSocketMessage, cls).__new__(TogglSocketTimeEntryMessage)
            elif model == values.M_PROJECT:
                return super(TogglSocketMessage, cls).__new__(TogglSocketProjectMessage)
            elif model == values.M_TASK:
                return super(TogglSocketMessage, cls).__new__(TogglSocketTaskMessage)
            elif model == values.M_CLIENT:
                return super(TogglSocketMessage, cls).__new__(TogglSocketClientMessage)
            elif model == values.M_TAG:
                return super(TogglSocketMessage, cls).__new__(TogglSocketTagMessage)

        return super(TogglSocketMessage, cls).__new__(cls)

    def __init__(self, model: str, definition):
        self.__model = model.lower()

        if 'action' not in definition:
            raise Exception('Missing action key')

        if 'data' not in definition:
            raise Exception('Missing data key')

        self._action = definition['action'].upper()
        self._data = definition['data']

        return

    def get_model(self):
        return self.__model

    def get_action(self):
        return self._action

    def to_dict(self):
        return {
            'action': self._action,
            'model': self.__model,
            'data': self._data
        }

    @staticmethod
    def _get_unix_time(time_str: Union[str, None]) -> Union[float, None]:
        if time_str is None:
            return None

        return dateutil.parser.isoparse(time_str).timestamp()

    @staticmethod
    def _try_get_key(dict, key, default=None):
        if key not in dict:
            return default

        return dict[key]


class TogglSocketTimeEntryMessage(TogglSocketMessage):
    def __init__(self, model, definition):
        super().__init__(model, definition)
        return

    def to_dict(self):
        ret = super().to_dict()

        # We know what type it is, so we can construct better data
        data = {
            # Metadata
            'workspace_id': self._data['wid'],
            'modified': TogglSocketMessage._get_unix_time(self._data['at']),
            'server_deleted_at': TogglSocketMessage._get_unix_time(
                TogglSocketMessage._try_get_key(self._data, 'server_deleted_at')),

            # Time entry
            'time_entry': {
                'id': self._data['id'],
                'desc': self._data['description'],
                'billable': self._data['billable'],
                'start': TogglSocketMessage._get_unix_time(self._data['start']),
                'stop': TogglSocketMessage._get_unix_time(self._data['stop']),
            },

            # Project
            'project': {
                'id': self._data['pid'],
                'task_id': self._data['tid']
            },

            # Tags
            'tags': self._data['tags']
        }

        ret['data'] = data
        return ret


class TogglSocketProjectMessage(TogglSocketMessage):
    def __init__(self, model, definition):
        super().__init__(model, definition)
        return

    def to_dict(self):
        ret = super().to_dict()

        # We know what type it is, so we can construct better data
        data = {
            # Metadata
            'workspace_id': self._data['wid'],
            'modified': TogglSocketMessage._get_unix_time(self._data['at']),
            'server_deleted_at': TogglSocketMessage._get_unix_time(self._data['server_deleted_at']),

            # Project
            'project': {
                'id': self._data['pid'],
                'client_id': self._data['cid'],
                'auto_estimates': self._data['auto_estimates'],
                'billable': self._data['billable'],
                'color': self._data['color'],
                'currency': self._data['currency'],
                'hex_color': self._data['hex_color'],
                'hourly_rate': self._data['hourly_rate'],
                'is_private': self._data['is_private'],
                'is_template': self._data['template'],
                'name': self._data['name'],
                'active': self._data['active']
            },

            # Tags
            'tags': self._data['tags']
        }

        ret['data'] = data
        return ret


class TogglSocketTaskMessage(TogglSocketMessage):
    def __init__(self, model, definition):
        super().__init__(model, definition)
        return

    def to_dict(self):
        ret = super().to_dict()

        # We know what type it is, so we can construct better data
        data = {
            # Metadata
            'workspace_id': self._data['wid'],
            'modified': TogglSocketMessage._get_unix_time(self._data['at']),
            'server_deleted_at': TogglSocketMessage._get_unix_time(self._data['server_deleted_at']),

            # Task
            'task': {
                'project_id': self._data['pid'],
                'id': self._data['tid'],
                'name': self._data['name'],
                'active': self._data['active']
            },

            # Tags
            'tags': self._data['tags']
        }

        ret['data'] = data
        return ret


class TogglSocketClientMessage(TogglSocketMessage):
    def __init__(self, model, definition):
        super().__init__(model, definition)
        return

    def to_dict(self):
        ret = super().to_dict()

        # We know what type it is, so we can construct better data
        data = {
            # Metadata
            'workspace_id': self._data['wid'],
            'modified': TogglSocketMessage._get_unix_time(self._data['at']),
            'server_deleted_at': TogglSocketMessage._get_unix_time(self._data['server_deleted_at']),

            # Client
            'client': {
                'id': self._data['tid'],
                'name': self._data['name']
            },

            # Tags
            'tags': self._data['tags']
        }

        ret['data'] = data
        return ret


class TogglSocketTagMessage(TogglSocketMessage):
    def __init__(self, model, definition):
        super().__init__(model, definition)
        return

    def to_dict(self):
        ret = super().to_dict()

        # We know what type it is, so we can construct better data
        data = {
            # Metadata
            'workspace_id': self._data['wid'],
            'modified': TogglSocketMessage._get_unix_time(self._data['at']),
            'server_deleted_at': TogglSocketMessage._get_unix_time(self._data['server_deleted_at']),

            # Tag
            'tag': {
                'id': self._data['tid'],
                'name': self._data['name']
            },

            # Tags
            'tags': self._data['tags']
        }

        ret['data'] = data
        return ret


class TogglSocket:
    """
    A "lower level" (relative to TogglClient) API over the Toggl websocket connection. This
    class is responsible for sending and receiving messages with the Toggl server over a WS
    connection. It implements authentication, and responds to pings from the server. All
    other messages from the server are returned to calling code via next_message().

    Using TogglSocket in a 'with' statement will implicitly call open() and close() so you don't have to.
    """

    def __init__(self, endpoint, origin, token, logger=None):
        """
        :param endpoint: Required. The Toggl socket URI to which to connect.
        :param origin: Required. The origin header to use with the socket connection.
        :param logger: Optional. Logging facility.
        """
        self.__endpoint = endpoint
        self.__origin = origin
        self.__token = token
        self.__logger = logger or logging.getLogger('togglws.socket')
        self.__session_id = None
        self.__should_run_ws = False
        self.__run_ws_task = None
        self.__ws_message_queue = queue.Queue()
        self.__ws: Union[None, websockets.WebSocketClientProtocol] = None
        self.__ws_recv_lock = asyncio.Lock()
        self.__is_open = False
        self.__is_initialised = False
        return

    async def open(self):
        """
        Opens the connection by calling websockets.connect and creating the background task
        to handle incoming messages and pings.
        """
        if self.is_open():
            return

        self.__ws = await self.__new_connection()
        self.__is_open = True
        self.__logger.debug('Opened TogglSocket.')
        return

    async def close(self):
        """
        Closes the connection by signalling to the background task that it should shut down, and then
        calling .close() on the underlying socket.
        """
        if not self.is_open():
            return

        self.__should_run_ws = False

        if self.__run_ws_task is not None:
            await self.__run_ws_task

        if self.__ws.open:
            await self.__ws.close()

        self.__is_open = False
        self.__logger.debug('Closed TogglSocket.')
        return

    def start_listening(self):
        self.__should_run_ws = True
        self.__run_ws_task = asyncio.create_task(self.__run_ws())
        self.__logger.debug('TogglSocket now listening for messages.')
        return

    async def initialise_connection(self):
        await self.__authenticate()

        self.__is_initialised = True
        return

    async def next_message(self) -> Union[TogglSocketMessage, None]:
        """
        Gets the next message from the internal queue (or waits for one to arrive), in the form
        or a TogglSocketMessage.
        """

        # Further notes:
        # Messages are placed on the queue by __run_ws().
        # This method assumes: 1. that all messages on the queue are valid JSON, and; 2. That the JSON
        # is consumable by TogglSocketMessage.

        if not self.is_open():
            raise Exception('Cannot get next message because socket is not open.')

        # Wait for the next message on the queue.
        raw_msg = await self.__next_ws_message()
        if raw_msg is None:
            # A None value indicates that __should_run_ws has been set to false.
            return None

        msg = json.loads(raw_msg)

        if 'model' not in msg:
            raise Exception(f'Missing "model" key in message: {raw_msg}')

        # TogglSocketMessage will construct as a different subclass depending on which model the JSON matches.
        return TogglSocketMessage(msg['model'], msg)

    def is_open(self):
        """Returns true if the .open() has been called successfully."""
        return self.__is_open

    def is_initialised(self):
        """Returns true if the .authenticate() has been called successfully."""
        return self.__is_initialised

    async def __aenter__(self):
        """Calls .open() when entering a with clause"""
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Calls .close() when exiting a with clause"""
        await self.close()
        return

    async def __authenticate(self):
        """
        Authenticates with the Toggl server by sending the given API key and waiting for a valid response
        from the Toggl server. If the API key is incorrect, the server will not respond. If this happens,
        an auth attempt will timeout after 5s.
        :param token: Your Toggl API token
        :return:
        """
        masked_token = self.__token[:2] + "*" * (len(self.__token) - 4) + self.__token[-2:]
        self.__logger.debug(f'Authenticating with Toggl server.. : {self.__endpoint} (token: {masked_token})')

        if not self.is_open():
            raise Exception('Cannot authenticate because socket is not open.')

        await self.__ws.send(json.dumps({
            "type": "authenticate",
            "api_token": self.__token
        }))

        # We can assume the next message after auth will be the auth response, because the Toggl
        # server will not send any messages until after auth is complete.
        timeout_secs = 5
        try:
            rawReply = await asyncio.wait_for(self.__ws_recv(), timeout=timeout_secs)
        except asyncio.TimeoutError:
            self.__logger.error(f'Authentication attempt timed out after {timeout_secs} seconds. '
                                f'This could be due to an incorrect API key.')
            raise

        reply = json.loads(rawReply)

        # Current we dont use this for anything, but I thought it might be worth storing.
        if 'session_id' in reply:
            self.__session_id = reply['session_id']
            self.__logger.debug('Successfully authenticated with Toggl server.')
        else:
            # Since the Toggl server typically does not reply unless we're authenticated.
            # we assume authentication is OK.
            self.__logger.debug(f'Received unexpected reply after authenticating ("{rawReply}"). '
                                f'Assuming authentication OK.')

        return

    async def __next_ws_message(self):
        """
        Returns the next message string found on the internal queue, or None if
        __should_run_ws is set to False.
        """

        # Don't use queue.get() because we need to repeatedly check the value of __should_run_ws
        # and return None if it is False.
        while self.__should_run_ws and self.__ws_message_queue.qsize() == 0:
            await asyncio.sleep(0.1)

        if self.__ws_message_queue.qsize() > 0:
            return self.__ws_message_queue.get()

        return None

    async def __run_ws(self):
        """
        This is the method that ultimately reads from the underlying websocket.
        It waits for a socket message, continually checking __should_run_ws.
        Once a message is received, if it's a ping message, we respond immediately with a pong.
        If the message is anything else, place it on the internal queue for processing by other
        methods.
        :return:
        """

        errors = 0
        exc: Optional[Exception] = None
        while self.__should_run_ws and errors < 5:
            if errors > 0:

                # Don't wait on the first attempt, as we're probably just reconnecting after
                # the server's hourly disconnect
                wait_for = 2.5 * (errors - 1)
                self.__logger.debug(f'Waiting for {wait_for} seconds before retry..')
                await asyncio.sleep(wait_for)

            next_msg_task = asyncio.create_task(self.__ws_recv())

            while not next_msg_task.done() and self.__should_run_ws:
                await asyncio.sleep(0.1)

            if next_msg_task.done():

                # Wrap this in a try/catch to handle the case where the socket is closed, and attempt
                # to reconnect if that happens.
                try:
                    # We have a message; now process it based on what it is.
                    next_msg = next_msg_task.result()
                except Exception as e:
                    errors += 1
                    exc = e
                    if type(e) not in [ConnectionClosedError, ConnectionClosedOK]:
                        self.__logger.warning(f'Unhandled error occurred reading from socket - {type(e)}: {e}')
                        continue
                    elif errors < 5:
                        # The socket has been closed. Check if it was by us:
                        if not self.__should_run_ws:
                            self.__logger.debug('__run_ws aborting: should_run is False.')
                            return None  # We closed it, so we should return

                        # Server closed it, so we should open a new one
                        self.__logger.debug('Socket disconnected by server. Attempting to reconnect..')

                        self.__ws = await self.__new_connection()
                        await self.initialise_connection()
                        continue
                    else:
                        self.__logger.error('Socket disconnected by server and all reconnection attempts failed.')
                        break

                # Successfully retrieved message
                errors = 0

                if TogglSocket.__is_ping(next_msg):
                    # If it's a ping, return a pong
                    await self.__ws.send(json.dumps({'type': 'pong'}))
                else:
                    # Otherwise queue the message for later processing
                    self.__ws_message_queue.put(next_msg)
            else:

                # We don't have a message; we're only here because __should_run_ws was set to False.
                next_msg_task.cancel()

                try:
                    # This is necessary because the websocket will close, which causes a CancelledError.
                    # if we don't wait for it and catch it here, it will be logged as an error when the
                    # program terminates.
                    await next_msg_task
                except asyncio.CancelledError as e:
                    pass

        if self.__should_run_ws:
            # This means we failed due to errors
            self.__logger.error(f'Fatal error running websocket connection - {type(exc)}: {exc}')
            pass

        return

    async def __new_connection(self):
        self.__logger.debug(f'Connecting to {self.__endpoint}..')
        return await websockets.connect(self.__endpoint, origin=self.__origin)

    async def __ws_recv(self):
        """A simple wrapper around the __ws.recv() call, for debugging."""

        if self.__ws_recv_lock.locked():
            # If you're seeing this message, there's probably some kind of synchronisation issue with
            # authenticating the socket, and the background listener. Both methods call __ws_recv, but they're
            # not supposed to do so at the same time.
            self.__logger.warning('Websocket receive method is blocked; waiting..')

        async with self.__ws_recv_lock:
            msg = await self.__ws.recv()
            self.__logger.debug(f'Received: {msg}')
            return msg

    @staticmethod
    def __is_ping(msg: str) -> bool:
        """Returns true if the provided string is a Toggl server ping."""
        try:
            msg_json = json.loads(msg)
            if msg_json['type'] == 'ping':
                return True

            return False
        except Exception as e:
            return False
