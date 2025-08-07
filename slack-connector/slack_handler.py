import asyncio
from typing import Callable, Optional

from slack_sdk.errors import SlackApiError
from slack_sdk.rtm_v2 import RTMClient
from slack_sdk.web.async_client import AsyncWebClient

from utils import get_channel_id_from_name_slack

class SlackHandler:
    """
    Encapsulates Slack RTM client and async Web API for a single channel.
    """

    def __init__(self, token: str) -> None:
        self.token: str = token
        self.async_client: AsyncWebClient = AsyncWebClient(token=self.token)
        self.rtm_client: RTMClient = RTMClient(token=self.token)

        # Callback receives (user_id, text) and runs synchronously in RTM thread
        self._on_message_callback: Optional[Callable[[str, str], None]] = None

    def set_on_message(self, callback: Callable[[str, str], None]) -> None:
        self._on_message_callback = callback

    async def send_text(self, text: str, channel_name: str) -> None:
        try:
            channel_id = get_channel_id_from_name_slack(channel_name)
            await self.async_client.chat_postMessage(channel=channel_id, text=text)
        except SlackApiError as e:
            print(f"Slack error: {e}")

    def start_listening(self) -> None:
        @self.rtm_client.on("message")
        def _process_message(**payload):
            data = payload.get("data", {})

            # TODO: Confirm if this needs to be a hard whitelist
            if "bot_id" in data:
                return
            
            channel = data.get("channel")

            user_id = data.get("user", "unknown")
            text = data.get("text", "")

            if self._on_message_callback is not None:
                self._on_message_callback(user_id, text, channel)

        self.rtm_client.start()