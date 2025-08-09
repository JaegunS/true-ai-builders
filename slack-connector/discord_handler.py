import asyncio
import threading
from typing import Awaitable, Callable, Optional

import discord

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
        self._on_delete_callback: Optional[Callable[[discord.Message, str], Awaitable[None]]] = None
        self._on_edit_callback: Optional[Callable[[discord.Message, discord.Message, str], Awaitable[None]]] = None

        self._register_events()

    def _register_events(self) -> None:
        @self.client.event
        async def on_ready() -> None:  # type: ignore
            self.loop = asyncio.get_running_loop()
            self.ready_event.set()
            print(f"Logged in as {self.client.user}")

        @self.client.event
        async def on_message(message: discord.Message) -> None:  # type: ignore
            if message.author == self.client.user:
                return
            
            channel_name = message.channel.name

            if self._on_message_callback is not None:
                await self._on_message_callback(message, channel_name)

        @self.client.event
        async def on_message_delete(message: discord.Message) -> None:  # type: ignore
            # Ignore our own bot's deletions
            try:
                if message.author == self.client.user:
                    return
            except Exception:
                # In rare cases message.author may not be available
                pass

            channel_name = getattr(getattr(message, "channel", None), "name", "unknown")

            print(channel_name)
            if self._on_delete_callback is not None:
                await self._on_delete_callback(message, channel_name)

        @self.client.event
        async def on_message_edit(before: discord.Message, after: discord.Message) -> None:  # type: ignore
            # Ignore our own bot edits to avoid feedback loops
            try:
                if after.author == self.client.user:
                    return
            except Exception:
                pass

            channel_name = getattr(getattr(after, "channel", None), "name", "unknown")
            if self._on_edit_callback is not None:
                await self._on_edit_callback(before, after, channel_name)


    # --- Set up callbacks ---

    def set_on_message(
        self, callback: Callable[[discord.Message, str], Awaitable[None]]
    ) -> None:
        """Set an async callback invoked when a new message arrives in any channel."""
        self._on_message_callback = callback

    def set_on_delete(
        self, callback: Callable[[discord.Message, str], Awaitable[None]]
    ) -> None:
        """Set an async callback invoked when a message is deleted in any channel."""
        self._on_delete_callback = callback

    def set_on_edit(
        self, callback: Callable[[discord.Message, discord.Message, str], Awaitable[None]]
    ) -> None:
        """Set an async callback invoked when a message is edited in any channel."""
        self._on_edit_callback = callback

    # --- Set up the actual functions ---

    async def send_text(self, text: str, channel_name: str) -> None:
        """Send a message to the configured Discord channel."""
        channel = discord.utils.get(self.client.get_all_channels(), name=channel_name)

        if channel is None:
            print(f"Channel '{channel_name}' not found; dropping message")
            return
        await channel.send(text)  # type: ignore[arg-type]

    async def delete_text(self, text: str, channel_name: str) -> None:
        """Delete recent messages in a Discord channel that contain the given text."""
        channel = discord.utils.get(self.client.get_all_channels(), name=channel_name)

        if channel is None:
            print(f"Channel '{channel_name}' not found; cannot delete message")
            return

        # Some channel types (e.g., voice) don't have history
        if not hasattr(channel, "history"):
            print(f"Channel '{channel_name}' does not support history; cannot delete message")
            return
        
        try:
            async for message in channel.history(limit=self.message_read_limit):  # type: ignore[attr-defined]
                if text in (getattr(message, "content", "") or ""):
                    try:
                        await message.delete()
                        return
                    except Exception as e:
                        print(f"Error deleting message in '{channel_name}': {e}")
        except Exception as e:
            print(f"Error fetching history for '{channel_name}': {e}")

    async def edit_text(self, old_text: str, new_text: str, channel_name: str) -> None:
        """Edit the most recent bot-authored message containing old_text to new_text."""
        channel = discord.utils.get(self.client.get_all_channels(), name=channel_name)

        if channel is None:
            print(f"Channel '{channel_name}' not found; cannot edit message")
            return

        if not hasattr(channel, "history"):
            print(f"Channel '{channel_name}' does not support history; cannot edit message")
            return

        try:
            async for message in channel.history(limit=self.message_read_limit):  # type: ignore[attr-defined]
                content = getattr(message, "content", "") or ""
                if old_text in content:
                    # Only attempt to edit messages authored by this bot
                    try:
                        if getattr(message, "author", None) == self.client.user:
                            await message.edit(content=new_text)
                            return
                        else:
                            # Not our message; skip
                            pass
                    except Exception as e:
                        print(f"Error editing message in '{channel_name}': {e}")
                    finally:
                        break
        except Exception as e:
            print(f"Error fetching history for '{channel_name}': {e}")

    # --- Schedule discord events --- #

    def schedule_send_text(self, text: str, channel_name: str) -> None:
        """
        Schedule sending a message to Discord from another thread.
        """
        if self.loop is None:
            print("Discord event loop not ready; dropping message")
            return
        asyncio.run_coroutine_threadsafe(self.send_text(text, channel_name), self.loop)

    def schedule_delete_text(self, text: str, channel_name: str) -> None:
        """Schedule deletion of a message from another thread."""
        if self.loop is None:
            print("Discord event loop not ready; cannot delete message")
            return
        asyncio.run_coroutine_threadsafe(self.delete_text(text, channel_name), self.loop)

    def schedule_edit_text(self, old_text: str, new_text: str, channel_name: str) -> None:
        """Schedule editing of a message from another thread."""
        if self.loop is None:
            print("Discord event loop not ready; cannot edit message")
            return
        asyncio.run_coroutine_threadsafe(self.edit_text(old_text, new_text, channel_name), self.loop)

    def run(self) -> None:
        """Run the Discord client (blocking)."""
        self.client.run(self.token)
