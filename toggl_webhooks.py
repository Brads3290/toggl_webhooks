import asyncio
import json
import requests
from toggl.toggl_websocket import TogglSocketMessage
from toggl.toggl_eventclient import TogglClient


async def main():
    # Load config
    with open('toggl_webhooks.json', 'r') as f:
        config = json.load(f)

    async with TogglClient(config['api_token']) as tc:
        for hook_conf in config['hooks']:
            method = hook_conf['method']
            url = hook_conf['url']

            for action in hook_conf['actions']:
                for model in hook_conf['models']:
                    tc.handle(action, model, generate_message_handler(method, url))

        await tc.run(handle_os_signals=True)


def generate_message_handler(method: str, url: str):
    async def message_handler_outer(action, model, msg: TogglSocketMessage):
        await message_handler(action, model, method, url, msg)
        return

    return message_handler_outer


async def message_handler(action: str, model: str, method: str, url: str, msg: TogglSocketMessage):
    res = requests.request(method, url, data=msg.make_serialisable())
    print(f'{action} {model} -> {res.status_code} {method} {url}')

    return


if __name__ == '__main__':
    asyncio.run(main())
