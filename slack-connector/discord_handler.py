import asyncio
import threading
from typing import Awaitable, Callable, Optional

import discord
from utils import is_discord_bot_message

class DiscordHandler:
    """
    Encapsulates Discord client lifecycle and message handling for a single channel.
    """

    def __init__(self, token: str, message_read_limit: int) -> None:
        intents = discord.Intents.default()
        intents.message_content = True

        self.token: str = token
        self.client: discord.Client = discord.Client(intents=intents)
        self.message_read_limit = message_read_limit

        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.ready_event: threading.Event = threading.Event()

        self._on_message_callback: Optional[Callable[[discord.Message, str], Awaitable[None]]] = None
        self._on_delete_callback: Optional[Callable[[str, str, str], Awaitable[None]]] = None
        self._on_edit_callback: Optional[Callable[[str, str, str, str], Awaitable[None]]] = None

        self._register_events()

    def _register_events(self) -> None:
        @self.client.event
        async def on_ready() -> None:  # type: ignore
            self.loop = asyncio.get_running_loop()
            self.ready_event.set()
            print(f"Logged in as {self.client.user}")

        @self.client.event
        async def on_message(message: discord.Message) -> None:  # type: ignore
            if is_discord_bot_message(message):
                return
            
            channel_name = message.channel.name

            if self._on_message_callback is not None:
                await self._on_message_callback(message, channel_name)

        @self.client.event
        async def on_message_delete(message: discord.Message) -> None:  # type: ignore
            # Ignore our own bot's deletions
            try:
                if is_discord_bot_message(message):
                    return
            except Exception:
                # In rare cases message.author may not be available
                pass

            channel_name = getattr(getattr(message, "channel", None), "name", "unknown")

            print(channel_name)
            if self._on_delete_callback is not None:
                await self._on_delete_callback(message.content, message.author.name, channel_name)

        @self.client.event
        async def on_message_edit(before: discord.Message, after: discord.Message) -> None:  # type: ignore
            # Ignore our own bot edits to avoid feedback loops
            try:
                if is_discord_bot_message(after):
                    return
            except Exception:
                pass

            channel_name = getattr(getattr(after, "channel", None), "name", "unknown")
            if self._on_edit_callback is not None:
                await self._on_edit_callback(before.content, after.content, after.author.name, channel_name)


    # --- Set up callbacks ---

    def set_on_message(
        self, callback: Callable[[discord.Message, str], Awaitable[None]]
    ) -> None:
        """Set an async callback invoked when a new message arrives in any channel."""
        self._on_message_callback = callback

    def set_on_delete(
        self, callback: Callable[[str, str, str], Awaitable[None]]
    ) -> None:
        """Set an async callback invoked when a message is deleted in any channel."""
        self._on_delete_callback = callback

    def set_on_edit(
        self, callback: Callable[[str, str, str, str], Awaitable[None]]
    ) -> None:
        """Set an async callback invoked when a message is edited in any channel."""
        self._on_edit_callback = callback

    # --- Set up the actual functions ---

    async def send_text(self, message_content: str, author_name: str, channel_name: str, message_text: str = None) -> None:
        """
        Send a message to the configured Discord channel with author attribution.
        If message_text is provided, send as a reply to that message.
        """

        if message_text is not None:
            # If message_text is provided, find the message and reply to it
            await self.send_reply(message_content, channel_name, message_text, author_name)
        else:
            # Send as a new message
            channel = discord.utils.get(self.client.get_all_channels(), name=channel_name)

            if channel is None:
                print(f"Channel '{channel_name}' not found; dropping message")
                return
            
            # Format the message with author attribution
            formatted_message = f"[From Slack] {author_name}: {message_content}"
            await channel.send(formatted_message)

    async def send_reply(self, reply_text: str, channel_name: str, message_text: str, author_name: str) -> None:
        """
        Find a message containing the specified text and send a reply to it.
        
        Args:
            reply_text: The text to send as a reply
            channel_name: The name of the channel to search in
            message_text: The text to search for in existing messages
            author_name: The name of the author sending the reply
        """
        channel = discord.utils.get(self.client.get_all_channels(), name=channel_name)

        if channel is None:
            print(f"Channel '{channel_name}' not found; dropping reply")
            return

        if not hasattr(channel, "history"):
            print(f"Channel '{channel_name}' does not support history; cannot send reply")
            return

        try:
            # Handle the [From Discord] prefix if present
            search_text = message_text
            if message_text.startswith("[From Discord]"):
                search_text = "".join(message_text.split(":")[1:]).strip()

            # Search for the message to reply to
            async for message in channel.history(limit=self.message_read_limit):
                if search_text in message.content:
                    # Found the message, send a reply
                    formatted_reply = f"[From Slack] {author_name}: {reply_text}"
                    await message.reply(formatted_reply)
                    return

            print(f"Could not find message to reply to in '{channel_name}'")

        except Exception as e:
            print(f"Error sending reply in '{channel_name}': {e}")

    async def delete_text(self, message_content: str, author_name: str, channel_name: str) -> None:
        """Delete recent messages in a Discord channel that match the author and content."""
        channel = discord.utils.get(self.client.get_all_channels(), name=channel_name)

        if channel is None:
            print(f"Channel '{channel_name}' not found; cannot delete message")
            return

        # Some channel types (e.g., voice) don't have history
        if not hasattr(channel, "history"):
            print(f"Channel '{channel_name}' does not support history; cannot delete message")
            return
        
        try:
            async for message in channel.history(limit=self.message_read_limit):
                content = getattr(message, "content", "") or ""
                author = getattr(message, "author", None)
                
                # Check if message content and author match
                if (message_content in content and 
                    author and 
                    getattr(author, "name", "") == author_name):
                    try:
                        await message.delete()
                        return
                    except Exception as e:
                        print(f"Error deleting message in '{channel_name}': {e}")
        except Exception as e:
            print(f"Error fetching history for '{channel_name}': {e}")

    async def edit_text(self, old_message: str, new_message: str, author_name: str, channel_name: str) -> None:
        """Edit the most recent message from the specified author containing old_message."""
        channel = discord.utils.get(self.client.get_all_channels(), name=channel_name)

        if channel is None:
            print(f"Channel '{channel_name}' not found; cannot edit message")
            return

        if not hasattr(channel, "history"):
            print(f"Channel '{channel_name}' does not support history; cannot edit message")
            return

        try:
            async for message in channel.history(limit=self.message_read_limit):
                content = getattr(message, "content", "") or ""
                author = getattr(message, "author", None)
                
                # Check if message content and author match
                if (old_message in content and 
                    author and 
                    getattr(author, "name", "") == author_name):
                    try:
                        await message.edit(content=new_message)
                        return
                    except Exception as e:
                        print(f"Error editing message in '{channel_name}': {e}")
                    finally:
                        break
        except Exception as e:
            print(f"Error fetching history for '{channel_name}': {e}")

    # --- Schedule discord events --- #

    def schedule_send_text(self, message_content: str, author_name: str, channel_name: str, message_text: str = None) -> None:
        """
        Schedule sending a message to Discord from another thread.
        If message_text is provided, send as a reply to that message.
        """
        if self.loop is None:
            print("Discord event loop not ready; dropping message")
            return
        asyncio.run_coroutine_threadsafe(self.send_text(message_content, author_name, channel_name, message_text), self.loop)

    def schedule_send_reply(self, reply_text: str, channel_name: str, message_text: str, author_name: str) -> None:
        """
        Schedule sending a reply to Discord from another thread.
        """
        if self.loop is None:
            print("Discord event loop not ready; dropping reply")
            return
        asyncio.run_coroutine_threadsafe(self.send_reply(reply_text, channel_name, message_text, author_name), self.loop)

    def schedule_delete_text(self, message_content: str, author_name: str, channel_name: str) -> None:
        """Schedule deletion of a message from another thread."""
        if self.loop is None:
            print("Discord event loop not ready; cannot delete message")
            return
        asyncio.run_coroutine_threadsafe(self.delete_text(message_content, author_name, channel_name), self.loop)

    def schedule_edit_text(self, old_message: str, new_message: str, author_name: str, channel_name: str) -> None:
        """Schedule editing of a message from another thread."""
        if self.loop is None:
            print("Discord event loop not ready; cannot edit message")
            return
        asyncio.run_coroutine_threadsafe(self.edit_text(old_message, new_message, author_name, channel_name), self.loop)

    def run(self) -> None:
        """Run the Discord client (blocking)."""
        self.client.run(self.token)
