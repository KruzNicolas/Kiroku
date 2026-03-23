import yt_dlp
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.modules.videos.domain.models import PriorityEnum, VideoMetadata


class ExtractionError(Exception):
    pass


class MetadataExtractor:
    def __init__(self):
        self.ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
        }

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(ExtractionError),
    )
    def extract(
        self,
        url: str,
        manual_priority: PriorityEnum | None = None,
    ) -> VideoMetadata:
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    raise ExtractionError(f"Could not extract metadata for URL: {url}")

                tags = info.get("tags", [])
                categories = info.get("categories", [])
                channel = (
                    info.get("uploader") or info.get("channel") or "Unknown Channel"
                )
                game_category = categories[0] if categories else None
                title = info.get("title") or "Unknown Title"

                return VideoMetadata(
                    url=url,
                    title=title,
                    channel=channel,
                    description=info.get("description") or "",
                    tags=tags if tags else [],
                    game_category=game_category,
                    manual_priority=manual_priority,
                )
        except Exception as exc:
            raise ExtractionError(f"Failed to extract info from {url}: {exc}") from exc
