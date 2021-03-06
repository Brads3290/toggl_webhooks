import asyncio
import websockets
import json
import dateutil.parser
import queue

from typing import Union


class TogglSocketMessage:
    def __new__(cls, model, definition):
        if cls is TogglSocketMessage:
            if model == 'time_entry':
                return super(TogglSocketMessage, cls).__new__(TogglSocketTimeEntryMessage)
            elif model == 'project':
                return super(TogglSocketMessage, cls).__new__(TogglSocketProjectMessage)
            elif model == 'task':
                return super(TogglSocketMessage, cls).__new__(TogglSocketTaskMessage)
            elif model == 'client':
                return super(TogglSocketMessage, cls).__new__(TogglSocketClientMessage)
            elif model == 'tag':
                return super(TogglSocketMessage, cls).__new__(TogglSocketTagMessage)

        return super(TogglSocketMessage, cls).__new__(cls, model, definition)

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
            'server_deleted_at': TogglSocketMessage._get_unix_time(TogglSocketMessage._try_get_key(self._data, 'server_deleted_at')),

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
    def __init__(self, endpoint, origin, verbose=False):
        self.__endpoint = endpoint
        self.__origin = origin
        self.__verbose = verbose
        self.__session_id = None
        self.__should_run_ws = False
        self.__run_ws_task = None
        self.__ws_message_queue = queue.Queue()
        self.__ws: Union[None, websockets.WebSocketClientProtocol] = None
        self.__is_open = False
        self.__is_authenticated = False
        return

    async def open(self):
        if self.is_open():
            return

        self.__ws = await websockets.connect(self.__endpoint, origin=self.__origin)
        self.__should_run_ws = True
        self.__run_ws_task = asyncio.create_task(self.__run_ws())
        self.__is_open = True
        self.__log('Opened TogglSocket.')
        return

    async def close(self):
        if not self.is_open():
            return

        self.__should_run_ws = False
        await self.__run_ws_task
        await self.__ws.close()
        self.__is_open = False
        self.__log('Closed TogglSocket.')
        return

    async def authenticate(self, token):
        self.__log(f'Authenticating with Toggl server.. : {self.__endpoint}')

        if not self.is_open():
            raise Exception('Cannot authenticate because socket is not open.')

        await self.__ws.send(json.dumps({
            "type": "authenticate",
            "api_token": token
        }))

        timeout_secs = 5
        task = self.__next_ws_message()
        try:
            rawReply = await asyncio.wait_for(task, timeout=timeout_secs)
        except asyncio.TimeoutError:
            print(f'Authentication attempt timed out after {timeout_secs} seconds. This could be due to an incorrect '
                  f'API key.')
            raise

        reply = json.loads(rawReply)
        self.__session_id = reply['session_id']
        self.__is_authenticated = True

        self.__log('Successfully authenticated with Toggl server.')

        return

    async def next_message(self) -> Union[TogglSocketMessage, None]:
        if not self.is_open():
            raise Exception('Cannot get next message because socket is not open.')

        raw_msg = await self.__next_ws_message()
        if raw_msg is None:
            return None

        msg = json.loads(raw_msg)

        if 'model' not in msg:
            raise Exception('Missing "model" key')

        return TogglSocketMessage(msg['model'], msg)

    def is_open(self):
        return self.__is_open

    def is_authenticated(self):
        return self.__is_authenticated

    async def __aenter__(self):
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return

    async def __next_ws_message(self):
        while self.__should_run_ws and self.__ws_message_queue.qsize() == 0:
            await asyncio.sleep(0.1)

        if self.__ws_message_queue.qsize() > 0:
            return self.__ws_message_queue.get()

        return None

    async def __run_ws(self):
        while self.__should_run_ws:
            next_msg_task = asyncio.create_task(self.__ws_recv())

            while not next_msg_task.done() and self.__should_run_ws:
                await asyncio.sleep(0.1)

            if next_msg_task.done():
                next_msg = next_msg_task.result()
                if TogglSocket.__is_ping(next_msg):
                    # If it's a ping, return a pong
                    await self.__ws.send(json.dumps({'type': 'pong'}))
                else:
                    # Otherwise queue the message for later processing
                    self.__ws_message_queue.put(next_msg)
            else:
                next_msg_task.cancel()

                try:
                    await next_msg_task
                except asyncio.CancelledError as e:
                    pass

        return

    async def __ws_recv(self):
        msg = await self.__ws.recv()
        self.__log(f'Received: {msg}')
        return msg

    def __log(self, msg):
        if not self.__verbose:
            return

        print(msg)

    @staticmethod
    def __is_ping(msg) -> bool:
        try:
            msg_json = json.loads(msg)
            if msg_json['type'] == 'ping':
                return True

            return False
        except Exception as e:
            return False


