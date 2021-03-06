import signal
import asyncio
from toggl.toggl_websocket import TogglSocket, TogglSocketMessage
from typing import Union


WS_ENDPOINT = "wss://track.toggl.com/stream"
WS_ORIGIN = "https://track.toggl.com"


class TogglClient:
    def __init__(self, api_token: str, ws_endpoint=WS_ENDPOINT, ws_origin=WS_ORIGIN):
        self.__api_token = api_token
        self.__ws_endpoint = ws_endpoint
        self.__ws_origin = ws_origin

        self.__should_run = True
        self.__run_task: Union[None, asyncio.Task] = None
        self.__ws_client = TogglSocket(self.__ws_endpoint, self.__ws_origin)
        return

    async def open(self):
        await self.__ws_client.open()

    async def close(self):
        await self.__ws_client.close()

    async def run(self, handle_os_signals=True):
        if handle_os_signals:
            signal.signal(signal.SIGINT, self.__signal_handler)

        await self.start()

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

    def is_open(self):
        return self.__ws_client.is_open()

    async def __initialise(self):
        if not self.is_open():
            raise Exception('TogglClient attempted initialisation before .open() was called.')

        await self.__ws_client.authenticate(self.__api_token)

        return

    async def __run(self):

        return

    def __signal_handler(self, sig, frame):
        self.__should_run = False
        return

    async def __aenter__(self):
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return
