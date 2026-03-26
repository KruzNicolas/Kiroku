import os
from dataclasses import dataclass
from functools import lru_cache
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    notion_token: str
    notion_database_id_videos: str
    notion_database_id_study_assets_japanese: str
    ollama_base_url: str
    ollama_api_key: str
    ollama_model_video: str
    ollama_model_receipts: str
    receipts_google_sheets_url: str
    receipts_google_sheets_api_token: str
    videos_added_at_tz: str
    internal_api_token: str
    idempotency_ttl_seconds: int
    rate_limit_videos_per_min: int
    rate_limit_videos_batch_per_min: int
    rate_limit_receipts_per_min: int
    rate_limit_study_assets_jp_per_min: int
    app_test_write_mode: bool


def _as_bool(value: str | None) -> bool:
    if not value:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_int(value: str | None, default: int) -> int:
    if value is None or value.strip() == "":
        return default
    try:
        parsed = int(value)
        return parsed if parsed > 0 else default
    except Exception:
        return default


def _resolve_timezone(tz_name: str) -> str:
    try:
        ZoneInfo(tz_name)
        return tz_name
    except Exception:
        return "America/Bogota"


@lru_cache
def get_settings() -> Settings:
    load_dotenv()

    notion_token = os.getenv("NOTION_TOKEN", "")
    videos_db_id = os.getenv("NOTION_DATABASE_ID_VIDEOS") or os.getenv(
        "NOTION_DATABASE_ID", ""
    )
    study_assets_japanese_db_id = os.getenv(
        "NOTION_DATABASE_ID_STUDY_ASSETS_JAPANESE", ""
    )
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "https://ollama.com")
    ollama_api_key = os.getenv("OLLAMA_API_KEY", "")
    ollama_model_video = os.getenv(
        "OLLAMA_MODEL_VIDEO", os.getenv("OLLAMA_MODEL", "minimax-m2.5:cloud")
    )
    ollama_model_receipts = os.getenv(
        "OLLAMA_MODEL_RECEIPTS",
        os.getenv("OLLAMA_MODEL_FINANCIAL", ollama_model_video),
    )
    receipts_google_sheets_url = os.getenv(
        "RECEIPTS_GOOGLE_SHEETS_URL",
        os.getenv("FINANCIAL_GOOGLE_SHEETS_URL", ""),
    )
    receipts_google_sheets_api_token = os.getenv("RECEIPTS_GOOGLE_SHEETS_API_TOKEN", "")
    videos_added_at_tz = _resolve_timezone(
        os.getenv("VIDEOS_ADDED_AT_TIMEZONE", "America/Bogota")
    )
    internal_api_token = os.getenv("INTERNAL_API_TOKEN", "")
    idempotency_ttl_seconds = _as_int(os.getenv("IDEMPOTENCY_TTL_SECONDS"), 86400)
    rate_limit_videos_per_min = _as_int(os.getenv("RATE_LIMIT_VIDEOS_PER_MIN"), 20)
    rate_limit_videos_batch_per_min = _as_int(
        os.getenv("RATE_LIMIT_VIDEOS_BATCH_PER_MIN"), 10
    )
    rate_limit_receipts_per_min = _as_int(os.getenv("RATE_LIMIT_RECEIPTS_PER_MIN"), 5)
    rate_limit_study_assets_jp_per_min = _as_int(
        os.getenv("RATE_LIMIT_STUDY_ASSETS_JP_PER_MIN"), 15
    )
    app_test_write_mode = _as_bool(os.getenv("APP_TEST_WRITE_MODE"))

    return Settings(
        notion_token=notion_token,
        notion_database_id_videos=videos_db_id,
        notion_database_id_study_assets_japanese=study_assets_japanese_db_id,
        ollama_base_url=ollama_base_url,
        ollama_api_key=ollama_api_key,
        ollama_model_video=ollama_model_video,
        ollama_model_receipts=ollama_model_receipts,
        receipts_google_sheets_url=receipts_google_sheets_url,
        receipts_google_sheets_api_token=receipts_google_sheets_api_token,
        videos_added_at_tz=videos_added_at_tz,
        internal_api_token=internal_api_token,
        idempotency_ttl_seconds=idempotency_ttl_seconds,
        rate_limit_videos_per_min=rate_limit_videos_per_min,
        rate_limit_videos_batch_per_min=rate_limit_videos_batch_per_min,
        rate_limit_receipts_per_min=rate_limit_receipts_per_min,
        rate_limit_study_assets_jp_per_min=rate_limit_study_assets_jp_per_min,
        app_test_write_mode=app_test_write_mode,
    )
