import asyncio
import logging
import signal
from typing import Any, Callable, Coroutine, List, Tuple, Union

from togglws.socket import TogglSocket, TogglSocketMessage

DEFAULT_WS_ENDPOINT = "wss://track.toggl.com/stream"
DEFAULT_WS_ORIGIN = "https://api.track.toggl.com"
_MESSAGE_HANDLER = Callable[[str, str, TogglSocketMessage], Coroutine[Any, Any, Any]]
LOGGER = logging.getLogger('togglws')


class TogglClient:
    """
    A wrapper around TogglSocket with a higher level API and ability to call handlers in response
    to events. TogglClient will automatically authenticate with the Toggl Server using the API key
    passed in the constructor.

    You must call open() before performing any TogglClient actions (e.g. start, stop, run).

    Using TogglClient in a 'with' statement will implicitly call open() and close() so you don't have to.
    """

    def __init__(self, api_token: str, ws_endpoint=DEFAULT_WS_ENDPOINT, ws_origin=DEFAULT_WS_ORIGIN, logger=None):
        """
        :param api_token: Required. Your Toggl API token.
        :param ws_endpoint: Optional. Specify a custom Toggl websocket URL. Defaults to DEFAULT_WS_ENDPOINT.
        :param ws_origin: Optional. Specify a custom value for the 'Origin' header. Defaults to DEFAULT_WS_ORIGIN.
        :param logger: Optional. Logging facility.
        """
        self.__api_token = api_token
        self.__ws_endpoint = ws_endpoint
        self.__ws_origin = ws_origin
        self.__logger = logger or LOGGER

        self.__should_run = True
        self.__run_task: Union[None, asyncio.Task] = None
        self.__ws_client = TogglSocket(self.__ws_endpoint, self.__ws_origin, api_token, logger=self.__logger)

        self.__handlers: List[Tuple[str, str, _MESSAGE_HANDLER]] = []
        return

    async def open(self):
        """Opens the underlying TogglSocket"""
        await self.__ws_client.open()

    async def close(self):
        """Closes the underlying TogglSocket"""
        await self.__ws_client.close()

    async def run(self, handle_os_signals=True):
        """
        Calls self.start(), then waits for the underlying TogglSocket to end.
        This method will not end naturally; it can be stopped by calling .stop()
        """

        if handle_os_signals:
            signal.signal(signal.SIGINT, self.__signal_handler)

        # self.start() handles authentication and starts the background task to handle incoming messages
        await self.start()

        # If self.start() succeeded, run until self.__should_run is set to false (or self.__run_task is finished,
        # but that shouldn't happen without __should_run being set to false..)
        self.__logger.debug('Running Toggl client..')
        while self.__should_run and not self.__run_task.done():
            await asyncio.sleep(0.1)

        # Probably not needed, but make absolutely sure everything is done before returning
        await self.wait()
        return

    async def start(self):
        """
        Authenticates the underlying socket with the Toggl server and starts listening for events on that socket
        asynchronously. It will "block" (asynchronously) until the socket is authenticated, and then start the
        async background task before returning.
        """

        # Initialise the underlying socket, checking that it is open first.
        # This call handles authentication with the Toggl server.
        await self.__initialise()

        # Start the listener process on the underlying socket
        self.__ws_client.start_listening()

        # Start the async BG task
        self.__logger.debug('Starting listener task..')
        self.__run_task = asyncio.create_task(self.__run())
        return

    async def wait(self, handle_os_signals=True):
        """
        Waits for the socket listener task to end
        :return:
        """

        if handle_os_signals:
            signal.signal(signal.SIGINT, self.__signal_handler)

        await self.__run_task
        return

    async def stop(self):
        """
        Signals the socket listening task to end, then waits for it to finish.
        """
        self.__should_run = False
        await self.wait()
        return

    def handle(self, actions: str, models: str, handler: _MESSAGE_HANDLER):
        """
        Register a handler to be called when the TogglClient receives an event matching those listed in the
        'actions' and 'models' parameters.

        The possible action and model values are specified in values.py.

        You can use a wildcard - '*' - to specify any action or any model.

        :param actions: Either a single string value or a list of strings specifying which actions this handler
            will respond to
        :param models: Either a single string value of a list of strings specifying which models this handler
            will respond to
        :param handler: A handler that will be called when an event is received that matches one of the specified
            actions and one of the specified models
        """
        if type(actions) is not list:
            actions = [actions]

        if type(models) is not list:
            models = [models]

        for action in actions:
            for model in models:
                self.__handlers.append((action, model, handler))

    def is_open(self):
        """Returns true if the underlying websocket is open."""
        return self.__ws_client.is_open()

    async def __initialise(self):
        """Initialises the underlying socket. Requires that it is open."""
        if not self.is_open():
            raise Exception('TogglClient attempted initialisation before .open() was called.')

        self.__logger.debug('Initialising TogglClient..')

        await self.__ws_client.initialise_connection()
        return

    async def __run(self):
        """
        __run is the main method of the background task that reads new events from the
        underlying socket and passes them to the message_handler.
        """
        if not self.is_open():
            raise Exception('ToggleClient attempted to run before .open() was called.')

        # Shouldn't really be needed (all paths to __run initialise first).. but just in case
        if not self.__ws_client.is_initialised():
            await self.__ws_client.initialise_connection()

        # Repeatedly check for another message, checking if should_run has been changed every 0.1s.
        # When a message is received, pass to __message_handler
        while self.__should_run:
            msg_task = asyncio.create_task(self.__ws_client.next_message())

            while self.__should_run and not msg_task.done():
                await asyncio.sleep(0.1)

            if msg_task.done():
                try:
                    res = msg_task.result()
                except Exception as e:
                    self.__logger.warning(f'Error retrieving next message from Toggl: {e}')
                    continue

                if res is not None:
                    await self.__message_handler(msg_task.result())

        return

    async def __message_handler(self, msg: TogglSocketMessage):
        """
        __message_handler takes a message returned by the underlying socket and calls the registered
        handler/s (if any).
        :param msg: A message returned by the underlying sockets next_message() method.
        """
        action = msg.get_action()
        model = msg.get_model()

        # Run all tasks asynchronously and await all at once afterwards.
        tasks = []
        for candidate in self.__handlers:
            a, m, h = candidate

            if (a == '*' or a == action) and (m == '*' or m == model):
                tasks.append(asyncio.create_task(h(action, model, msg)))

        for t in tasks:
            await t

        return

    def __signal_handler(self, sig, frame):
        """
        __signal_handler instructs background tasks to stop.
        It is called in response to receiving a SIGINT.
        """
        self.__logger.debug('TogglClient detected SIGINT')
        self.__should_run = False
        return

    async def __aenter__(self):
        """Open the underlying socket when we enter a 'with' clause"""
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close the underlying socket when we exit a 'with' clause"""
        await self.close()
        return
