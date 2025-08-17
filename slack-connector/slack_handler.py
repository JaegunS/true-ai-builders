# slack_handler.py

import asyncio
from typing import Callable, Optional, Awaitable

from slack_sdk.errors import SlackApiError
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.socket_mode.aiohttp import SocketModeClient
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.socket_mode.response import SocketModeResponse

from utils import get_channel_id_from_name_slack, is_slack_bot_event


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
        self._on_edit_callback: Optional[Callable[[str, str, str, str], Awaitable[None]]] = None

    # --- Set up callbacks ---

    def set_on_message(
        self, callback: Callable[[str, str, str], Awaitable[None]]
    ) -> None:
        """Set an async callback invoked when a new message arrives in any channel."""
        self._on_message_callback = callback

    def set_on_delete(
        self, callback: Callable[[str, str, str], Awaitable[None]]
    ) -> None:
        """Set an async callback invoked when a new message is deleted in any channel."""
        self._on_delete_callback = callback

    def set_on_edit(
        self, callback: Callable[[str, str, str, str], Awaitable[None]]
    ) -> None:
        """Set an async callback invoked when a new message is edited in any channel."""
        self._on_edit_callback = callback

    # --- Set up the actual functions ---

    async def send_text(self, message_content: str, author_name: str, channel_name: str, message_text: str = None) -> None:
        if message_text is not None:
            # If message_text is provided, find the message and reply to it
            await self.send_reply(message_content, channel_name, message_text, author_name)
        else:
            try:
                channel_id = await get_channel_id_from_name_slack(channel_name, self.async_client)
                # Format the message with author attribution
                formatted_message = f"[From Discord] {author_name}: {message_content}"
                await self.async_client.chat_postMessage(channel=channel_id, text=formatted_message)
            except SlackApiError as e:
                print(f"Slack error while sending: {e}")

    async def send_reply(self, reply_text: str, channel_name: str, message_text: str, author_name: str) -> None:
        """
        Find a message containing the specified text and send a reply to it.
        
        Args:
            reply_text: The text to send as a reply
            channel_name: The name of the channel to search in
            message_text: The text to search for in existing messages
        """
        # Find starting index for the author
        if message_text.startswith("[From Slack]"):
            message_text = "".join(message_text.split(":")[1:]).strip()

        try:
            channel_id = await get_channel_id_from_name_slack(channel_name, self.async_client)
            
            # Search for the message to reply to
            resp = await self.async_client.conversations_history(channel=channel_id, limit=self.message_read_limit)
            
            for msg in resp.get("messages", []):
                if message_text in msg.get("text", ""):
                    # Found the message, send a reply using thread_ts
                    await self.async_client.chat_postMessage(
                        channel=channel_id,
                        text=reply_text,
                        thread_ts=msg["ts"]  # This creates a thread reply
                    )
                    return

            print("Slack sent nothing?")

        except SlackApiError as e:
            print(f"Slack error while sending reply: {e}")
        except Exception as e:
            print(f"Unexpected error while sending reply: {e}")

    async def delete_text(self, message_content: str, author_name: str, channel_name: str) -> None:
        """Delete recent messages in a Slack channel that match the author and content."""
        try:
            channel_id = await get_channel_id_from_name_slack(channel_name, self.async_client)
            resp = await self.async_client.conversations_history(channel=channel_id, limit=self.message_read_limit)
            
            for msg in resp.get("messages", []):
                msg_text = msg.get("text", "")
                # Check if message content matches and format matches our expected pattern
                expected_format = f"[From Discord] {author_name}: {message_content}"
                if expected_format in msg_text:
                    await self.async_client.chat_delete(channel=channel_id, ts=msg["ts"])
                    return
        except SlackApiError as e:
            print(f"Slack error while deleting: {e}")

    async def edit_text(self, old_content: str, new_content: str, author_name: str, channel_name: str) -> None:
        """Edit the most recent message from the specified author containing old_content."""
        try:
            channel_id = await get_channel_id_from_name_slack(channel_name, self.async_client)
            resp = await self.async_client.conversations_history(channel=channel_id, limit=self.message_read_limit)
            
            for msg in resp.get("messages", []):
                msg_text = msg.get("text", "")
                # Check if message content matches and format matches our expected pattern
                expected_old_format = f"[From Discord] {author_name}: {old_content}"
                if expected_old_format in msg_text:
                    try:
                        new_formatted = f"[From Discord] {author_name}: {new_content}"
                        await self.async_client.chat_update(
                            channel=channel_id,
                            ts=msg["ts"],
                            text=new_formatted,
                        )
                        return
                    except SlackApiError as e:
                        print(f"Slack error while editing: {e}")
                    finally:
                        break
        except SlackApiError as e:
            print(f"Slack error while editing: {e}")

    # --- Socket Mode event loop ---

    async def _socket_mode_loop(self) -> None:
        self._socket_client = SocketModeClient(
            app_token=self.app_token,
            web_client=self.async_client,
        )

        async def handle_requests(client: SocketModeClient, req: SocketModeRequest):
            await client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))

            if req.type == "events_api":
                event = req.payload.get("event", {})
                if event.get("type") == "message":
                    # Ignore bot-authored messages (including edits/deletions by bots)
                    if is_slack_bot_event(event):
                        return

                    user_id = event.get("user", "unknown")
                    text = event.get("text", "")
                    channel = event.get("channel", "")
                    thread_ts = event["ts"]
                    #resp = client.conversations_history(channel=channel, latest=thread_ts, inclusive=True, limit=1)
                    #print(resp)

                    # delete a message
                    if event.get("subtype") == "message_deleted":
                        
                        # Bot deletion event
                        user_id = event.get("previous_message").get("user")
                        text = event.get("previous_message").get("text")

                        # Check if the previous code was sent by a bot
                        # Cheeky bastard code
                        if event.get("previous_message").get("user", "unknown") == "unknown":
                            return
                        
                        if self._on_delete_callback:
                            await self._on_delete_callback(user_id, text, channel)
                    # edit a message
                    elif event.get("subtype") == "message_changed":
                        previous_text = event.get("previous_message", {}).get("text", "")
                        new_text = event.get("message", {}).get("text", "")
                        # Try to resolve the editing user from nested payload
                        user_id = (
                            event.get("message", {}).get("user")
                            or event.get("previous_message", {}).get("user")
                            or user_id
                        )
                        if self._on_edit_callback:
                            await self._on_edit_callback(user_id, previous_text, new_text, channel)
                    # send a message
                    else:
                        if self._on_message_callback:
                            await self._on_message_callback(user_id, text, channel)

        # register the request listener
        self._socket_client.socket_mode_request_listeners.append(handle_requests)

        # connect (keeps the websocket alive)
        await self._socket_client.connect()

        # sleep forever to keep the task alive
        await asyncio.Future()

    # --- Start listening ---

    def start_listening(self) -> None:
        try:
            asyncio.run(self._socket_mode_loop())
        except Exception as e:
            print(f"Error in Socket Mode: {e}")
            raise

