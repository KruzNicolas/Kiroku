import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    notion_token: str
    notion_database_id_videos: str
    ollama_base_url: str
    ollama_api_key: str
    ollama_model: str
    app_test_write_mode: bool


def _as_bool(value: str | None) -> bool:
    if not value:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


@lru_cache
def get_settings() -> Settings:
    load_dotenv()

    notion_token = os.getenv("NOTION_TOKEN", "")
    videos_db_id = os.getenv("NOTION_DATABASE_ID_VIDEOS") or os.getenv(
        "NOTION_DATABASE_ID", ""
    )
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "https://ollama.com")
    ollama_api_key = os.getenv("OLLAMA_API_KEY", "")
    ollama_model = os.getenv("OLLAMA_MODEL", "minimax-m2.5:cloud")
    app_test_write_mode = _as_bool(os.getenv("APP_TEST_WRITE_MODE"))

    return Settings(
        notion_token=notion_token,
        notion_database_id_videos=videos_db_id,
        ollama_base_url=ollama_base_url,
        ollama_api_key=ollama_api_key,
        ollama_model=ollama_model,
        app_test_write_mode=app_test_write_mode,
    )
