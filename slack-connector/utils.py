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

