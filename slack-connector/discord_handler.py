import asyncio
import threading
from typing import Awaitable, Callable, Optional

import discord

class DiscordHandler:
    """
    Encapsulates Discord client lifecycle and message handling for a single channel.
    """

    def __init__(self, token: str) -> None:
        intents = discord.Intents.default()
        intents.message_content = True

        self.token: str = token
        self.client: discord.Client = discord.Client(intents=intents)

        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.ready_event: threading.Event = threading.Event()

        self._on_message_callback: Optional[Callable[[discord.Message, str], Awaitable[None]]] = None

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

    def set_on_message(
        self, callback: Callable[[discord.Message, str], Awaitable[None]]
    ) -> None:
        """Set an async callback invoked when a new message arrives in any channel."""
        self._on_message_callback = callback

    async def send_text(self, text: str, channel_name: str) -> None:
        """Send a message to the configured Discord channel."""
        channel = discord.utils.get(self.client.get_all_channels(), name=channel_name)

        if channel is None:
            print(f"Channel '{channel_name}' not found; dropping message")
            return
        await channel.send(text)  # type: ignore[arg-type]

    def schedule_send_text(self, text: str, channel_name: str) -> None:
        """
        Schedule sending a message to Discord from another thread.
        """
        if self.loop is None:
            print("Discord event loop not ready; dropping message")
            return
        asyncio.run_coroutine_threadsafe(self.send_text(text, channel_name), self.loop)

    def run(self) -> None:
        """Run the Discord client (blocking)."""
        self.client.run(self.token)
