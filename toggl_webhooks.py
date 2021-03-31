import asyncio
import json
import logging
import sys

import requests

from togglws import TogglClient, TogglSocketMessage

logger = logging.getLogger(__name__)
formatter = logging.Formatter('%(asctime)s (%(filename)s:%(lineno)d) %(levelname)s: %(message)s')
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setFormatter(formatter)
logger.addHandler(stdout_handler)


def usage():
    print('Usage:')
    print('  toggl_webhooks.py <config file> [-v|--verbose]')
    sys.exit(0)


async def main():
    # Check command line args. First argument should be pointing to the config file.
    if len(sys.argv) <= 1:
        usage()

    verbose = '-v' in sys.argv or '--verbose' in sys.argv
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    # Load config
    logger.debug('Loading config..')
    with open(sys.argv[1], 'r') as f:
        config = json.load(f)

    # Create a TogglClient and open it (opens a connection to the Toggl websocket)
    async with TogglClient(config['api_token'], logger=logger) as tc:

        # Configure the TogglClient to handle the hooks configured in the config file by calling message_handler
        logger.debug('Configuring hooks..')
        for hook in config['hooks']:
            actions = hook.pop('actions')
            models = hook.pop('models')
            method = hook.pop('method')
            url = hook.pop('url')
            tc.handle(actions, models, generate_message_handler(method, url, **hook))

        # Run TogglClient until CTRL+C is pressed
        logger.info('Listening for events.. Press CTRL+C to stop')
        await tc.run(handle_os_signals=True)

    logger.debug('Done.')


# Utility method to generate the handler. This is necessary because we want to pass method and url
# in a closure, and we can't use a lambda because TogglClient expects an async handler (which lambdas don't
# support)
def generate_message_handler(method: str, url: str, **kwargs):
    async def message_handler_outer(action, model, msg: TogglSocketMessage):
        await message_handler(action, model, method, url, msg, **kwargs)

    return message_handler_outer


# The actual handler; in this case, it just sends the data to the server in the manner defined by
# the config file.
async def message_handler(action: str, model: str, method: str, url: str, msg: TogglSocketMessage,
                          trials=None, **request_kwargs):
    trials = trials or 1
    assert trials >= 1
    trial = 0
    while True:
        trial += 1
        if trial > trials:
            logger.error(f'{action} {model} -> {method} {url} stop trials')
            break
        try:
            res = requests.request(method, url, json=msg.to_dict(), **request_kwargs)
        except requests.RequestException as e:
            logger.warning(f'{action} {model} -> {method} {url} failed, trial: {trial}. retrying')
            logger.exception(e)
            # retry after a while in case of exception
            await asyncio.sleep(2 ** (trial - 1))
            continue
        if res.status_code >= 400:
            logger.warning(f'{action} {model} -> {res.status_code} {method} {url} failed, trial: {trial}. retrying')
            logger.debug(f'{action} {model} -> {res.status_code} {method} {url} response: {res.text}')
            # retry after a while in case of bad response
            await asyncio.sleep(2 ** (trial - 1))
            continue
        logger.info(f'{action} {model} -> {res.status_code} {method} {url}')
        break


if __name__ == '__main__':
    asyncio.run(main())
