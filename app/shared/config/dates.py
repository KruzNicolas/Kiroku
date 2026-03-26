from datetime import datetime
from zoneinfo import ZoneInfo

from app.shared.config.settings import get_settings


def current_added_at_iso_date() -> str:
    """Return business date in configured timezone as YYYY-MM-DD."""
    settings = get_settings()
    return datetime.now(ZoneInfo(settings.videos_added_at_tz)).date().isoformat()
