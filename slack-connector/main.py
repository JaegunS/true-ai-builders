import threading
import os

from dotenv import load_dotenv

from discord_handler import DiscordHandler
from slack_handler import SlackHandler
from utils import get_user_name_slack, get_channel_name_slack
import discord

load_dotenv()

# slack side needs two tokens due to socket mode

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SLACK_TOKEN = os.getenv("SLACK_TOKEN")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN")

# validate env vars
_missing = [
    name for name, val in (
        ("DISCORD_TOKEN", DISCORD_TOKEN),
        ("SLACK_TOKEN", SLACK_TOKEN),
        ("SLACK_APP_TOKEN", SLACK_APP_TOKEN),
    ) if not val
]
if _missing:
    raise RuntimeError(
        "Missing required environment variables: " + ", ".join(_missing)
    )

def main() -> None:
    # Rename lol
    message_read_limit = 200
    discord_side = DiscordHandler(token=DISCORD_TOKEN, message_read_limit=message_read_limit)
    slack_side = SlackHandler(
        bot_token=SLACK_TOKEN,
        app_token=SLACK_APP_TOKEN,
        message_read_limit=message_read_limit, 
    )

    # Bridge: Discord -> Slack (create)
    async def on_discord_message(message: discord.Message, channel_name: str) -> None:
        author_name = message.author.name
        content = message.content
        slack_message_text = f"[From Discord] {author_name}: {content}"
        await slack_side.send_text(slack_message_text, channel_name)

    discord_side.set_on_message(on_discord_message)

    # Bridge: Discord -> Slack (delete)
    async def on_discord_delete(message: discord.Message, channel_name: str) -> None:
        author_name = message.author.name
        content = message.content
        # Refactor this
        slack_message_text = f"[From Discord] {author_name}: {content}"
        await slack_side.delete_text(slack_message_text, channel_name)


    discord_side.set_on_delete(on_discord_delete)

    # Bridge: Slack -> Discord
    async def on_slack_message(user_id: str, text: str, channel_id: str) -> None:
        user_name = await get_user_name_slack(user_id=user_id, client=slack_side.async_client)
        channel_name = await get_channel_name_slack(
            channel_id=channel_id,
            client=slack_side.async_client,
            dm_fallback_user_name=user_name,
        )
        formatted = f"[From Slack] {user_name}: {text}"
        discord_side.schedule_send_text(formatted, channel_name=channel_name)


    slack_side.set_on_message(on_slack_message)

    async def on_slack_delete(user_id: str, text: str, channel_id: str) -> None:
        # Not implemented yet for Discord side. Placeholder to satisfy linter.
        user_name = await get_user_name_slack(user_id=user_id, client=slack_side.async_client)
        channel_name = await get_channel_name_slack(
            channel_id=channel_id,
            client=slack_side.async_client,
            dm_fallback_user_name=user_name,
        )
        discord_message_text = f"[From Slack] {user_name}: {text}"
        # Schedule deletion on the Discord event loop
        discord_side.schedule_delete_text(discord_message_text, channel_name)

    slack_side.set_on_delete(on_slack_delete)






    # Start Slack Socket Mode after Discord is ready
    def start_slack():
        discord_side.ready_event.wait()
        slack_side.start_listening()

    slack_thread = threading.Thread(target=start_slack, daemon=True)
    slack_thread.start()

    # Run Discord (blocking)
    discord_side.run()


if __name__ == "__main__":
    main()

