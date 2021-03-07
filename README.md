Toggl Webhooks
===
_A project inspired by the lack of webhook support on the Toggl Track platform (https://toggl.com/track/)._

This project was originally intended as a stand-in for the webhook functionality that Toggl Track doesn't have.
The idea was to use the same Websockets connection that their web app uses to live update, but instead of a browser,
it's a Python script which then forwards the request to a URI to replicate websocket functionality.

I pretty soon realised that this makes no sense; if you're going to have to have this running 24x7 to emulate webhooks,
you might as well integrate it more directly with your automation code (well, most of the time..).
So I abstracted the guts of the project out into a package - `togglws` - which is configurable to call whatever handler
you like when it receives update messages from Toggl. The actual webhooks implementation became more like a demo script.

Therefore, there are two ways to use this project:
1. Use `toggl_webhooks.py` and a configuration file as an out-of-the-box Toggl webhooks replacement which will call whatever URI you specify when it receives events from Toggl.
2. Integrate the `togglws` package directly into your application to directly call whatever code you like in response to events from Toggl.

## Installation
For now, just download the files and put them in your project.

At this stage, I haven't put this project on Pip or anything like that. I made it for my own use and don't have any experience uploading to Pip, but if someone would like me to put it in a package manager let me know and I can look into it.

## Usage

### Out-of-the-box: `toggl_webhooks.py`
`toggl_webhooks.py` is a fully functional program that uses `togglws` to listen for events directly from Toggl and forward them to the URI(s) you specify in a configuration file.

Call it on the command line like so:
```
python toggl_webhooks.py <configuration_file> [-v|--verbose]
```

The configuration file is a JSON file like the following:
```json
{
  "api_token": "<your_api_key>",
  "hooks": [
    {
      "actions": ["INSERT", "UPDATE"],
      "models": ["time_entry"],
      "method": "POST",
      "url": "https://www.example.com"
    }
  ]
}
```
The above file will `POST` an event to `https://www.example.com` in response to any time entry being inserted (starting a new entry) or updated (stopping an entry, changing it's name/project/tags, etc.)

The `POST` body will contain all the details of the new time entry. The exact format is the output of `.to_dict()` in the corresponding model class (inside `togglws/socket.py`). In this case, the appropriate class is `TogglSocketTimeEntryMessage`. 

The list of available actions and models can be found in `togglws/values.py`.

### Custom: package `togglws`

**Basic usage**
```python
import togglws
import asyncio

async def main():
    async with togglws.TogglClient("<your_api_token>") as tc:
        
        # Set a handler for any time a time entry is created or updated
        tc.handle(
            actions=[togglws.A_INSERT, togglws.A_UPDATE],
            models=[togglws.M_TIME_ENTRY],
            handler=message_handler
        )
        
        # Continuously listen for messages, and call the handler whenever
        # a matching message is received.
        await tc.run()


async def message_handler(action: str, model: str, msg: togglws.TogglSocketMessage):
    # Custom handler; do anything you like.
    print(f'Received message: {action} {model} - {msg.to_dict()}')


if __name__ == '__main__':
    asyncio.run(main())
```

