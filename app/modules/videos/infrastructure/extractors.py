import requests
import logging
from urllib.parse import parse_qs, urlparse
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.modules.videos.domain.models import PriorityEnum, VideoMetadata
from app.shared.config.settings import get_settings


logger = logging.getLogger("kiroku.videos.extractor")


class ExtractionError(Exception):
    pass


class NonRetryableExtractionError(ExtractionError):
    pass


class YouTubeApiExtractor:
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.youtube_api_key
        self.base_url = settings.youtube_api_base_url.rstrip("/")

    def _extract_video_id(self, url: str) -> str:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        path = parsed.path or ""

        if "youtu.be" in host:
            candidate = path.strip("/")
            if candidate:
                return candidate

        if "youtube.com" in host:
            if path == "/watch":
                query = parse_qs(parsed.query)
                values = query.get("v") or []
                if values and values[0]:
                    return values[0]
            if path.startswith("/shorts/"):
                candidate = path.split("/shorts/", 1)[1].split("/", 1)[0]
                if candidate:
                    return candidate

        raise ValueError(f"Unsupported YouTube URL format: {url}")

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception(
            lambda exc: (
                isinstance(exc, ExtractionError)
                and not isinstance(exc, NonRetryableExtractionError)
            )
        ),
        reraise=True,
    )
    def extract(
        self,
        url: str,
        manual_priority: PriorityEnum | None = None,
    ) -> VideoMetadata:
        if not self.api_key:
            raise NonRetryableExtractionError(
                "YOUTUBE_API_KEY is required for YouTube API extractor"
            )

        try:
            video_id = self._extract_video_id(url)
            logger.info(
                "extracting metadata via youtube data api",
                extra={
                    "request_id": "-",
                    "method": "-",
                    "path": "-",
                    "source": "youtube_api",
                    "source_message_id": "-",
                    "source_user_id": "-",
                },
            )
            response = requests.get(
                f"{self.base_url}/videos",
                params={"part": "snippet", "id": video_id, "key": self.api_key},
                timeout=20,
            )

            if response.status_code >= 500:
                raise ExtractionError(
                    f"YouTube API temporary failure ({response.status_code})"
                )
            if response.status_code >= 400:
                raise NonRetryableExtractionError(
                    "YouTube API rejected metadata request "
                    f"({response.status_code}): {response.text}"
                )

            payload = response.json()
            items = payload.get("items") or []
            if not items:
                raise NonRetryableExtractionError(
                    f"YouTube API returned no metadata for video id: {video_id}"
                )

            snippet = items[0].get("snippet") or {}
            return VideoMetadata(
                url=url,
                title=snippet.get("title") or "Unknown Title",
                channel=snippet.get("channelTitle") or "Unknown Channel",
                description=snippet.get("description") or "",
                tags=snippet.get("tags") or [],
                game_category=None,
                manual_priority=manual_priority,
            )
        except NonRetryableExtractionError:
            raise
        except ValueError as exc:
            raise NonRetryableExtractionError(str(exc)) from exc
        except Exception as exc:
            raise ExtractionError(
                f"YouTube API extraction failed for {url}: {exc}"
            ) from exc


def build_video_extractor():
    return YouTubeApiExtractor()
