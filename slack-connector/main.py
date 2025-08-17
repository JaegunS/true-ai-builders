import threading
import os

from dotenv import load_dotenv

from discord_handler import DiscordHandler
from slack_handler import SlackHandler
from utils import get_user_name_slack, get_channel_name_slack, is_discord_bot_message
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
        # Extract message content and author name
        content = message.content
        author_name = message.author.name

        if message.reference:
            try:
                replied_message = await message.channel.fetch_message(message.reference.message_id)

                # check if the message was sent by a bot
                if is_discord_bot_message(replied_message):
                    # If the replied message is from a bot, we need to construct the search text
                    # Look for the bot's message content in the channel
                    message_to_reply = replied_message.content
                else:
                    author_name = replied_message.author.name
                    content = replied_message.content
                    message_to_reply = f"[From Discord] {author_name}: {content}"

                # Send as a reply to the specific message
                await slack_side.send_text(content, author_name, channel_name, message_to_reply)
            except Exception as e:
                print(f"Error handling Discord reply: {e}")
                # Fallback to regular message if reply handling fails
                await slack_side.send_text(content, author_name, channel_name)
        else:
            # Not a reply, send as regular message
            await slack_side.send_text(content, author_name, channel_name)

    # Bridge: Discord -> Slack (delete)
    async def on_discord_delete(message: discord.Message, channel_name: str) -> None:
        author_name = message.author.name
        content = message.content
        # Refactor this
        # OLD: slack_message_text = f"[From Discord] {author_name}: {content}"
        await slack_side.delete_text(content, author_name, channel_name)

    # Bridge: Discord -> Slack (edit)
    async def on_discord_edit(before: discord.Message, after: discord.Message, channel_name: str) -> None:
        author_name = after.author.name
        old_content = before.content
        new_content = after.content

        await slack_side.edit_text(old_content, new_content, author_name, channel_name)

    discord_side.set_on_message(on_discord_message)
    discord_side.set_on_delete(on_discord_delete)
    discord_side.set_on_edit(on_discord_edit)

    # Bridge: Slack -> Discord
    async def on_slack_message(user_id: str, text: str, channel_id: str) -> None:
        user_name = await get_user_name_slack(user_id=user_id, client=slack_side.async_client)
        channel_name = await get_channel_name_slack(
            channel_id=channel_id,
            client=slack_side.async_client,
            dm_fallback_user_name=user_name,
        )
        
        # Pass message content and author separately instead of formatted string
        discord_side.schedule_send_text(text, user_name, channel_name)

    async def on_slack_delete(user_id: str, text: str, channel_id: str) -> None:
        user_name = await get_user_name_slack(user_id=user_id, client=slack_side.async_client)
        channel_name = await get_channel_name_slack(
            channel_id=channel_id,
            client=slack_side.async_client,
            dm_fallback_user_name=user_name,
        )

        # Pass message content and author separately instead of formatted string
        discord_side.schedule_delete_text(text, user_name, channel_name)

    async def on_slack_edit(user_id: str, old_text: str, new_text: str, channel_id: str) -> None:
        user_name = await get_user_name_slack(user_id=user_id, client=slack_side.async_client)
        channel_name = await get_channel_name_slack(
            channel_id=channel_id,
            client=slack_side.async_client,
            dm_fallback_user_name=user_name,
        )
        
        # Pass old message, new message, and author separately instead of formatted strings
        discord_side.schedule_edit_text(old_text, new_text, user_name, channel_name)

    slack_side.set_on_message(on_slack_message)
    slack_side.set_on_delete(on_slack_delete)
    slack_side.set_on_edit(on_slack_edit)

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

