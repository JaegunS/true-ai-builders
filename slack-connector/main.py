import threading
import os

from dotenv import load_dotenv

from discord_handler import DiscordHandler
from slack_handler import SlackHandler
import discord

# Load environment variables from a .env file if present
load_dotenv()

# Required configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SLACK_TOKEN = os.getenv("SLACK_TOKEN")

# Validate presence
_missing = [
    name for name, val in (
        ("DISCORD_TOKEN", DISCORD_TOKEN),
        ("SLACK_TOKEN", SLACK_TOKEN),
    ) if not val
]
if _missing:
    raise RuntimeError(
        "Missing required environment variables: " + ", ".join(_missing)
    )

def main() -> None:
    discord_side = DiscordHandler(token=DISCORD_TOKEN)  # type: ignore[arg-type]
    slack_side = SlackHandler(token=SLACK_TOKEN)  # type: ignore[arg-type]

    # Bridge: Discord -> Slack
    async def on_discord_message(message: discord.Message) -> None:

        author_name = message.author.name
        content = message.content
        channel_name = message.channel.name

        slack_message_text = f"[From Discord] {author_name}: {content}"

        # TODO: Add validation code
        
        await slack_side.send_text(slack_message_text, channel_name)

    # The Discord handler will format the message; we only forward raw text here
    discord_side.set_on_message(
        lambda message: on_discord_message(f"[From Discord] {message.author.name}: {message.content}")
    )

    # Bridge: Slack -> Discord
    def on_slack_message(user_id: str, text: str, channel_name: str) -> None:
        formatted = f"[From Slack] {user_id}: {text}"
        discord_side.schedule_send_text(formatted, channel_name)

    slack_side.set_on_message(on_slack_message)

    # Start Slack RTM in a background thread after Discord is ready
    def start_slack():
        discord_side.ready_event.wait()
        slack_side.start_listening()

    slack_thread = threading.Thread(target=start_slack, daemon=True)
    slack_thread.start()

    # Run Discord (blocking)
    discord_side.run()


if __name__ == "__main__":
    main()
