from notion_client import Client

from app.shared.config.settings import get_settings

# Use stable API version compatible with notion-client SDK
_NOTION_API_VERSION = "2022-06-28"


def build_notion_client() -> Client:
    settings = get_settings()
    return Client(auth=settings.notion_token, notion_version=_NOTION_API_VERSION)
