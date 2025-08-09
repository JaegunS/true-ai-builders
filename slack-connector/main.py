import threading
import os

from dotenv import load_dotenv

from discord_handler import DiscordHandler
from slack_handler import SlackHandler
from slack_sdk.errors import SlackApiError
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
    discord_side = DiscordHandler(token=DISCORD_TOKEN)
    slack_side = SlackHandler(
        bot_token=SLACK_TOKEN,
        app_token=SLACK_APP_TOKEN,
    )

    # Bridge: Discord -> Slack
    async def on_discord_message(message: discord.Message, channel_name: str) -> None:
        author_name = message.author.name
        content = message.content
        slack_message_text = f"[From Discord] {author_name}: {content}"
        await slack_side.send_text(slack_message_text, channel_name)

    discord_side.set_on_message(on_discord_message)

    # Bridge: Slack -> Discord
    async def on_slack_message(user_id: str, text: str, channel_id: str) -> None:
        # pull username
        try:
            user_info = await slack_side.async_client.users_info(user=user_id)
            if user_info.get("ok"):
                user_name = user_info["user"].get("name", "unknown")
            else:
                user_name = "unknown"
        except SlackApiError as e:
            print(f"Slack API error getting user info: {e}")
            user_name = "unknown"

        # pull channel name
        try:
            channel_info = await slack_side.async_client.conversations_info(channel=channel_id)
            if channel_info.get("ok"):
                channel_obj = channel_info["channel"]
                channel_name = channel_obj.get("name")
                if not channel_name and channel_obj.get("is_im"):
                    channel_name = user_name  # DM fallback
            else:
                channel_name = "unknown"
        except SlackApiError as e:
            print(f"Slack API error getting channel info: {e}")
            channel_name = "unknown"

        formatted = f"[From Slack] {user_name}: {text}"
        discord_side.schedule_send_text(formatted, channel_name=channel_name)


    slack_side.set_on_message(on_slack_message)

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

