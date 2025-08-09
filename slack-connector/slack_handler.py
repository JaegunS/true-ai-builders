# slack_handler.py

import asyncio
from typing import Callable, Optional, Awaitable

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse

from utils import get_channel_id_from_name_slack


class SlackHandler:
    """
    Slack handler using Socket Mode (WebSocket) only.
    """

    def __init__(self, bot_token: str, app_token: str, message_read_limit: int) -> None:
        self.bot_token = bot_token # xoxb-...
        self.app_token = app_token # xapp-...
        self.async_client = AsyncWebClient(token=self.bot_token)
        self._socket_client: Optional[SocketModeClient] = None
        self.message_read_limit = message_read_limit

        self._on_message_callback: Optional[Callable[[str, str, str], Awaitable[None]]] = None
        self._on_delete_callback: Optional[Callable[[str, str, str], Awaitable[None]]] = None

    def set_on_message(
        self, callback: Callable[[str, str, str], Awaitable[None]]
    ) -> None:
        """Set an async callback invoked when a new message arrives in any channel."""
        self._on_message_callback = callback

    def set_on_delete(
        self, callback: Callable[[str, str, str], Awaitable[None]]
    ) -> None:
        """Set an async callback invoked when a new message arrives in any channel."""
        self._on_delete_callback = callback

    async def send_text(self, text: str, channel_name: str) -> None:
        try:
            channel_id = await get_channel_id_from_name_slack(channel_name, self.async_client)
            await self.async_client.chat_postMessage(channel=channel_id, text=text)
        except SlackApiError as e:
            print(f"Slack error while sending: {e}")

    async def delete_text(self, text: str, channel_name: str) -> None:
        try:
            channel_id = await get_channel_id_from_name_slack(channel_name, self.async_client)
            resp = await self.async_client.conversations_history(channel=channel_id, limit=self.message_read_limit)
            for msg in resp.get("messages", []):
                if text in msg.get("text", ""):
                    await self.async_client.chat_delete(channel=channel_id, ts=msg["ts"])
        except SlackApiError as e:
            print(f"Slack error while deleting: {e}")

    async def _socket_mode_loop(self) -> None:
        self._socket_client = SocketModeClient(
            app_token=self.app_token,
            web_client=self.async_client,
        )

        async def handle_requests(client: SocketModeClient, req: SocketModeRequest):
            await client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))

            if req.type == "events_api":
                event = req.payload.get("event", {})
                if event.get("type") == "message" and "bot_id" not in event:

                    user_id = event.get("user", "unknown")
                    text = event.get("text", "")
                    channel = event.get("channel", "")
                    
                    # If slack message is a deletion
                    if event.get("subtype") == "message_deleted":
                        
                        # Bot deletion event
                        user_id = event.get("previous_message").get("user")

                        # Check if the previous code was sent by a bot
                        # Cheeky bastard code
                        if event.get("previous_message").get("user", "unknown") == "unknown":
                            return
                        
                        if self._on_delete_callback:
                            await self._on_delete_callback(user_id, text, channel)
                    else:
                        if self._on_message_callback:
                            await self._on_message_callback(user_id, text, channel)

        # register the request listener
        self._socket_client.socket_mode_request_listeners.append(handle_requests)

        # connect (keeps the websocket alive)
        await self._socket_client.connect()

        # sleep forever to keep the task alive
        await asyncio.Future()

    def start_listening(self) -> None:
        try:
            asyncio.run(self._socket_mode_loop())
        except Exception as e:
            print(f"Error in Socket Mode: {e}")
            raise

