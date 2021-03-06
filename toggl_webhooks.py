import asyncio
import json
import requests
from toggl.toggl_websocket import TogglSocketMessage
from toggl.toggl_eventclient import TogglClient


async def main():

    # Load config
    with open('toggl_webhooks.json', 'r') as f:
        config = json.load(f)

    # Create a TogglClient and open it (opens a connection to the Toggl websocket)
    async with TogglClient(config['api_token']) as tc:

        # Configure the TogglClient to handle the hooks configured in the config file by calling message_handler
        for hook in config['hooks']:
            tc.handle(hook['actions'], hook['models'], generate_message_handler(hook['method'], hook['url']))

        # Run TogglClient until CTRL+C is pressed
        print('Running Toggl client.. Press CTRL+C to stop')
        await tc.run(handle_os_signals=True)


# Utility method to generate the handler. This is necessary because we want to pass method and url
# in a closure, and we can't use a lambda because TogglClient expects an async handler (which lambdas don't
# support)
def generate_message_handler(method: str, url: str):
    async def message_handler_outer(action, model, msg: TogglSocketMessage):
        await message_handler(action, model, method, url, msg)
        return

    return message_handler_outer


# The actual handler; in this case, it just sends the data to the server in the manner defined by
# the config file.
async def message_handler(action: str, model: str, method: str, url: str, msg: TogglSocketMessage):
    res = requests.request(method, url, data=msg.to_dict())
    print(f'{action} {model} -> {res.status_code} {method} {url}')

    return


if __name__ == '__main__':
    asyncio.run(main())
