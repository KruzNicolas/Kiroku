import yt_dlp
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


class HybridVideoExtractor:
    def __init__(self, primary: YouTubeApiExtractor, fallback: "MetadataExtractor"):
        self.primary = primary
        self.fallback = fallback

    def extract(
        self,
        url: str,
        manual_priority: PriorityEnum | None = None,
    ) -> VideoMetadata:
        try:
            return self.primary.extract(url, manual_priority=manual_priority)
        except NonRetryableExtractionError as exc:
            # If API key is missing in hybrid mode, fallback to yt-dlp.
            if "YOUTUBE_API_KEY is required" in str(exc):
                logger.info(
                    "youtube api key missing, falling back to yt-dlp extractor",
                    extra={
                        "request_id": "-",
                        "method": "-",
                        "path": "-",
                        "source": "yt_dlp_fallback",
                        "source_message_id": "-",
                        "source_user_id": "-",
                    },
                )
                return self.fallback.extract(url, manual_priority=manual_priority)
            raise
        except Exception:
            logger.info(
                "youtube api extractor failed, falling back to yt-dlp",
                extra={
                    "request_id": "-",
                    "method": "-",
                    "path": "-",
                    "source": "yt_dlp_fallback",
                    "source_message_id": "-",
                    "source_user_id": "-",
                },
            )
            return self.fallback.extract(url, manual_priority=manual_priority)


def build_video_extractor():
    settings = get_settings()
    mode = settings.video_extractor_mode

    ytdlp_extractor = MetadataExtractor()
    youtube_extractor = YouTubeApiExtractor()

    if mode == "youtube_api":
        return youtube_extractor
    if mode == "yt_dlp":
        return ytdlp_extractor
    # default and recommended: YouTube API primary with yt-dlp fallback.
    return HybridVideoExtractor(primary=youtube_extractor, fallback=ytdlp_extractor)


class MetadataExtractor:
    def __init__(self):
        settings = get_settings()
        self.ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
        }
        if settings.ytdlp_cookie_file:
            self.ydl_opts["cookiefile"] = settings.ytdlp_cookie_file

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
            message = str(exc)
            lowered = message.lower()
            anti_bot_markers = (
                "sign in to confirm you",
                "not a bot",
                "captcha",
                "cookies-from-browser",
                "--cookies",
            )
            if any(marker in lowered for marker in anti_bot_markers):
                raise NonRetryableExtractionError(
                    "YouTube anti-bot blocked metadata extraction. "
                    "Configure YTDLP_COOKIE_FILE with valid exported browser cookies. "
                    f"Original error: {message}"
                ) from exc
            raise ExtractionError(f"Failed to extract info from {url}: {exc}") from exc
