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
    # AI settings (global defaults — can be overridden per module)
    ai_base_url: str
    ai_api_key: str
    ai_model_video: str
    ai_model_receipts: str
    # Per-module overrides (optional — fall back to global AI_* when unset)
    videos_ai_base_url: str
    receipts_ai_base_url: str
    receipts_google_sheets_url: str
    receipts_google_sheets_api_token: str
    videos_added_at_tz: str
    internal_api_token: str
    idempotency_ttl_seconds: int
    rate_limit_videos_per_min: int
    rate_limit_videos_batch_per_min: int
    rate_limit_receipts_per_min: int
    rate_limit_study_assets_jp_per_min: int
    youtube_api_key: str
    youtube_api_base_url: str
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

    # AI settings (global defaults)
    ai_base_url = os.getenv("AI_BASE_URL", "https://opencode.ai/zen/go/v1")
    ai_api_key = os.getenv("AI_API_KEY", "")
    ai_model_video = os.getenv("AI_MODEL_VIDEO", "mimo-v2.5")
    ai_model_receipts = os.getenv("AI_MODEL_RECEIPTS", "mimo-v2.5-pro")
    # Per-module base URL overrides (optional — fall back to AI_BASE_URL when unset)
    videos_ai_base_url = os.getenv("VIDEOS_AI_BASE_URL", "")
    receipts_ai_base_url = os.getenv("RECEIPTS_AI_BASE_URL", "")

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
    youtube_api_key = os.getenv("YOUTUBE_API_KEY", "")
    youtube_api_base_url = os.getenv(
        "YOUTUBE_API_BASE_URL", "https://www.googleapis.com/youtube/v3"
    )
    app_test_write_mode = _as_bool(os.getenv("APP_TEST_WRITE_MODE"))

    return Settings(
        notion_token=notion_token,
        notion_database_id_videos=videos_db_id,
        notion_database_id_study_assets_japanese=study_assets_japanese_db_id,
        ai_base_url=ai_base_url,
        ai_api_key=ai_api_key,
        ai_model_video=ai_model_video,
        ai_model_receipts=ai_model_receipts,
        videos_ai_base_url=videos_ai_base_url,
        receipts_ai_base_url=receipts_ai_base_url,
        receipts_google_sheets_url=receipts_google_sheets_url,
        receipts_google_sheets_api_token=receipts_google_sheets_api_token,
        videos_added_at_tz=videos_added_at_tz,
        internal_api_token=internal_api_token,
        idempotency_ttl_seconds=idempotency_ttl_seconds,
        rate_limit_videos_per_min=rate_limit_videos_per_min,
        rate_limit_videos_batch_per_min=rate_limit_videos_batch_per_min,
        rate_limit_receipts_per_min=rate_limit_receipts_per_min,
        rate_limit_study_assets_jp_per_min=rate_limit_study_assets_jp_per_min,
        youtube_api_key=youtube_api_key,
        youtube_api_base_url=youtube_api_base_url,
        app_test_write_mode=app_test_write_mode,
    )
