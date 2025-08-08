# Discord-Slack Bridge

## Bridge Setup

1) Create a `.env` file (same directory as `main.py`) with:

```
DISCORD_TOKEN=idk
SLACK_TOKEN=xoxb-idk
SLACK_APP_TOKEN=xapp-idk
```

2) Install dependencies:

```
uv sync
```

3) Run the bridge:

```
python main.py
```

## Discord Setup

1) Create a Discord bot in the [Discord Developer Portal](https://discord.com/developers/applications).
2) Enable the "Server Members Intent" and "Message Content Intent" in the bot settings.
3) Go to "Installation" and set the default install settings under Guild Install to "Scopes -> bot" and "Bot Permissions -> Read Messages/View Channels" and "Send Messages".
4) Copy the bot token and add it to your `.env` file as `DISCORD_TOKEN`.
5) Invite the bot to your server.

## Slack Setup

1) Create a Slack app in the [Slack API](https://api.slack.com/apps).
2) Enable the "Socket Mode" and add the `SLACK_APP_TOKEN` to your `.env` file.
3) Set your App Manifest to the contents of `slack-manifest.yaml` and install the app to your workspace.
4) Add the `SLACK_TOKEN` to your `.env` file.
5) Make sure to add the app to the target channel. (TODO: automate this?)
