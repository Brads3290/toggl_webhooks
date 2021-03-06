import asyncio
import signal
import json
from toggl.toggl_websocket import TogglSocket, TogglSocketMessage

# Load config
with open('toggl_webhooks.json', 'r') as f:
    config = json.load(f)

# Lazily sanity check config
for x, t in {'hooks': list, 'endpoint': str, 'ws_origin': str, 'api_token': str}.items():
    if x not in config:
        print(f'[WARN] key "{x}" missing from config')
    elif type(config[x]) is not t:
        print(f'[WARN] config key "{x}" should be {t}')

should_run = True


async def main():
    signal.signal(signal.SIGINT, sig_handler)

    task = asyncio.create_task(run_client())

    while should_run and not task.done():
        await asyncio.sleep(0.1)

    print('Waiting for main task to finish..')
    await task

    print('Exiting.')
    return


def sig_handler(sig, frame):
    global should_run
    should_run = False

    print('Received interrupt signal.')
    return


async def run_client():
    endpoint = config['endpoint']
    api_token = config['api_token']
    ws_origin = config['ws_origin']

    print('Opening Toggl websockets client..')
    async with TogglSocket(endpoint, ws_origin) as ts:

        print('Authenticating with Toggl..')
        await ts.authenticate(api_token)

        print('Now listening for updates from Toggl websocket.')
        while should_run:
            msg_task = asyncio.create_task(ts.next_message())

            while should_run and not msg_task.done():
                await asyncio.sleep(0.1)

            if msg_task.done() and msg_task.result() is not None:
                await handle_message(msg_task.result())

    return


async def handle_message(msg: TogglSocketMessage):
    if 'hooks' not in config or type(config['hooks']) is not list:
        return

    action = msg.get_action()
    model = msg.get_model()

    tasks = []
    for hook in config['hooks']:
        if type(hook) is not dict:
            continue

        if 'actions' not in hook or type(hook['actions']) is not list:
            continue

        if 'models' not in hook or type(hook['models']) is not list:
            continue

        if action in hook['actions'] and model in hook['models']:
            if 'url' not in hook:
                print(f'[WARN] Missing URL from hook: {hook}')
                continue

            tasks.append(asyncio.create_task(call_webhook(msg, hook)))

    if len(tasks) == 0:
        print(f'{action} {model} -> (no hooks defined)')

    for task in tasks:
        await task

    return


async def call_webhook(msg: TogglSocketMessage, hook: dict):
    action = msg.get_action()
    model = msg.get_model()
    url = hook['url']
    method = hook['method'] if 'method' in hook else 'POST'

    print(f'{action} {model} -> {method} {url}')

    return


if __name__ == '__main__':
    asyncio.run(main())
