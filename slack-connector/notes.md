Setup and run

1) Create a `.env` file (same directory as `main.py`) with:

```
DISCORD_TOKEN=your_discord_bot_token
SLACK_TOKEN=your_slack_bot_token
SLACK_CHANNEL_ID=C12345678
DISCORD_CHANNEL_ID=123456789012345678
```

2) Install dependencies:

```
pip install -r requirements.txt
```

3) Run the bridge:

```
python main.py
```

Notes
- Ensure Discord Message Content Intent is enabled in the Developer Portal.
- Invite the Discord bot to the server and confirm it can access the target channel.
- Invite the Slack app to the target channel and grant required scopes (e.g., chat:write, RTM access).
- `SLACK_CHANNEL_ID` must be the channel ID (e.g., starts with `C`).
- `DISCORD_CHANNEL_ID` must be an integer.