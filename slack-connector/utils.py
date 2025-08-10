from typing import Optional

from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.errors import SlackApiError

_channel_cache: dict[str, str] = {}  # name → id

async def get_channel_id_from_name_slack(
    channel_name: str,
    client: AsyncWebClient
) -> str:
    """Look up a Slack channel ID by its name (without #)."""
    normalized = channel_name.lstrip("#").lower()

    if normalized in _channel_cache:
        return _channel_cache[normalized]

    try:
        cursor = None
        while True:
            resp = await client.conversations_list(
                types="public_channel,private_channel",
                limit=100,
                cursor=cursor
            )

            for ch in resp.get("channels", []):
                if ch.get("name", "").lower() == normalized:
                    _channel_cache[normalized] = ch["id"]
                    return ch["id"]

            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break

    except SlackApiError as e:
        raise RuntimeError(f"Slack API error while finding channel '{channel_name}': {e}")

    raise ValueError(f"Channel '{channel_name}' not found on Slack workspace")



async def get_user_name_slack(user_id: str, client: AsyncWebClient) -> str:
    """Resolve a Slack user's display name.

    Returns "unknown" on error or if not found.
    """
    try:
        user_info = await client.users_info(user=user_id)
        if user_info.get("ok"):
            return user_info["user"].get("name", "unknown")
    except SlackApiError as e:
        print(f"Slack API error getting user info: {e}")
    return "unknown"


async def get_channel_name_slack(
    channel_id: str,
    client: AsyncWebClient,
    dm_fallback_user_name: Optional[str] = None,
) -> str:
    """Resolve a Slack channel's name.

    If the channel is a DM (no name), falls back to dm_fallback_user_name if provided,
    otherwise "unknown".
    """
    try:
        channel_info = await client.conversations_info(channel=channel_id)
        if channel_info.get("ok"):
            channel_obj = channel_info["channel"]
            channel_name = channel_obj.get("name")
            if channel_name:
                return channel_name
            if channel_obj.get("is_im"):
                return dm_fallback_user_name or "unknown"
    except SlackApiError as e:
        print(f"Slack API error getting channel info: {e}")
    return "unknown"