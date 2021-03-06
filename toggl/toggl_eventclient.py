import signal
import asyncio
from toggl.toggl_websocket import TogglSocket, TogglSocketMessage
from typing import Union, List, Callable, Coroutine, Tuple, Any


_WS_ENDPOINT = "wss://track.toggl.com/stream"
_WS_ORIGIN = "https://track.toggl.com"
_MESSAGE_HANDLER = Callable[[str, str, TogglSocketMessage], Coroutine[Any, Any, Any]]


class TogglClient:
    def __init__(self, api_token: str, ws_endpoint=_WS_ENDPOINT, ws_origin=_WS_ORIGIN, verbose=False):
        self.__api_token = api_token
        self.__ws_endpoint = ws_endpoint
        self.__ws_origin = ws_origin
        self.__verbose = verbose

        self.__should_run = True
        self.__run_task: Union[None, asyncio.Task] = None
        self.__ws_client = TogglSocket(self.__ws_endpoint, self.__ws_origin, verbose=self.__verbose)

        self.__handlers: List[Tuple[str, str, _MESSAGE_HANDLER]] = []
        return

    async def open(self):
        await self.__ws_client.open()

    async def close(self):
        await self.__ws_client.close()

    async def run(self, handle_os_signals=True):
        if handle_os_signals:
            signal.signal(signal.SIGINT, self.__signal_handler)

        await self.start()

        while self.__should_run and not self.__run_task.done():
            await asyncio.sleep(0.1)

        await self.wait()
        return

    async def start(self):
        await self.__initialise()
        self.__run_task = asyncio.create_task(self.__run())
        return

    async def wait(self):
        await self.__run_task
        return

    async def stop(self):
        self.__should_run = False
        await self.wait()
        return

    def handle(self, actions: str, models: str, handler: _MESSAGE_HANDLER):
        if type(actions) is not list:
            actions = [actions]

        if type(models) is not list:
            models = [models]

        for action in actions:
            for model in models:
                self.__handlers.append((action, model, handler))

    def is_open(self):
        return self.__ws_client.is_open()

    async def __initialise(self):
        if not self.is_open():
            raise Exception('TogglClient attempted initialisation before .open() was called.')

        self.__log('Initialising TogglClient..')

        await self.__ws_client.authenticate(self.__api_token)
        return

    async def __run(self):
        if not self.is_open():
            raise Exception('ToggleClient attempted to run before .open() was called.')

        self.__log('Running TogglClient..')

        if not self.__ws_client.is_authenticated():
            await self.__ws_client.authenticate(self.__api_token)

        while self.__should_run:
            msg_task = asyncio.create_task(self.__ws_client.next_message())

            while self.__should_run and not msg_task.done():
                await asyncio.sleep(0.1)

            if msg_task.done() and msg_task.result() is not None:
                await self.__message_handler(msg_task.result())

        return

    async def __message_handler(self, msg: TogglSocketMessage):
        action = msg.get_action()
        model = msg.get_model()

        tasks = []
        for candidate in self.__handlers:
            a, m, h = candidate

            if (a == '*' or a == action) and (m == '*' or m == model):
                tasks.append(asyncio.create_task(h(action, model, msg)))

        for t in tasks:
            await t

        return

    def __signal_handler(self, sig, frame):
        print('TogglClient detected SIGINT')
        self.__should_run = False
        return

    async def __aenter__(self):
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return

    def __log(self, msg):
        if not self.__verbose:
            return

        print(msg)
