import yt_dlp
from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
)
from .models import VideoMetadata


from typing import Any, Dict


class ExtractionError(Exception):
    pass


class MetadataExtractor:
    def __init__(self):
        self.ydl_opts: Any = {
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
    def extract(self, url: str, force_later: bool = False) -> VideoMetadata:
        try:
            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                if not info:
                    raise ExtractionError(f"Could not extract metadata for URL: {url}")

                tags = info.get("tags", [])
                categories = info.get("categories", [])
                game_category = None

                # If "Gaming" is in categories, yt-dlp sometimes puts the game name in "track" or "chapters"
                # but "categories" is generally safe. We'll extract "categories" or specific game fields.
                # In YouTube, game name is often mapped to 'categories' or 'genre' or 'track'.
                if categories and "Gaming" in categories:
                    # simplistic fallback: the game name might be another category or we just keep it generic
                    pass

                # Another field yt-dlp captures for games is 'category' or 'categories'
                # For strict requirements: "Game Category (if present)"
                # Let's map it from 'categories' if available and not general.
                if len(categories) > 0:
                    game_category = categories[0]

                title = info.get("title")
                if not title:
                    title = "Unknown Title"

                return VideoMetadata(
                    url=url,
                    title=title,
                    description=info.get("description") or "",
                    tags=tags if tags else [],
                    game_category=game_category,
                    force_later=force_later,
                )
        except Exception as e:
            raise ExtractionError(f"Failed to extract info from {url}: {str(e)}")
