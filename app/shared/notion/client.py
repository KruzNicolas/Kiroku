from notion_client import Client

from app.shared.config.settings import get_settings


def build_notion_client() -> Client:
    settings = get_settings()
    return Client(auth=settings.notion_token, notion_version="2022-06-28")
