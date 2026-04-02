import pytest

from app.modules.videos.infrastructure.extractors import (
    ExtractionError,
    HybridVideoExtractor,
    MetadataExtractor,
    NonRetryableExtractionError,
    YouTubeApiExtractor,
    build_video_extractor,
)


class _StubYDL:
    def __init__(self, _opts, should_fail: Exception | None = None):
        self.should_fail = should_fail

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, _url, download=False):
        assert download is False
        if self.should_fail:
            raise self.should_fail
        return {
            "title": "T",
            "uploader": "C",
            "description": "D",
            "tags": ["x"],
            "categories": ["Game"],
        }


def test_extractor_uses_cookiefile_when_configured(monkeypatch):
    monkeypatch.setenv("YTDLP_COOKIE_FILE", "/tmp/yt.cookies")
    from app.shared.config.settings import get_settings

    get_settings.cache_clear()
    extractor = MetadataExtractor()

    assert extractor.ydl_opts.get("cookiefile") == "/tmp/yt.cookies"

    get_settings.cache_clear()
    monkeypatch.delenv("YTDLP_COOKIE_FILE", raising=False)


def test_extractor_raises_non_retryable_for_youtube_antibot(monkeypatch):
    from app.modules.videos.infrastructure import extractors as ext_mod

    class _YDLFactory:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return _StubYDL(
                self.opts,
                should_fail=Exception(
                    "Sign in to confirm you're not a bot. Use --cookies"
                ),
            )

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(ext_mod.yt_dlp, "YoutubeDL", _YDLFactory)

    extractor = MetadataExtractor()
    with pytest.raises(NonRetryableExtractionError):
        extractor.extract("https://youtube.com/watch?v=abc")


def test_extractor_raises_retryable_extraction_error_for_generic_failure(monkeypatch):
    from app.modules.videos.infrastructure import extractors as ext_mod

    class _YDLFactory:
        def __init__(self, opts):
            self.opts = opts

        def __enter__(self):
            return _StubYDL(self.opts, should_fail=Exception("network timeout"))

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(ext_mod.yt_dlp, "YoutubeDL", _YDLFactory)

    extractor = MetadataExtractor()
    with pytest.raises(ExtractionError):
        extractor.extract("https://youtube.com/watch?v=abc")


def test_youtube_api_extractor_parses_supported_url_formats(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "k")
    from app.shared.config.settings import get_settings

    get_settings.cache_clear()
    extractor = YouTubeApiExtractor()

    assert (
        extractor._extract_video_id("https://www.youtube.com/watch?v=Af3NmSP6h_E")
        == "Af3NmSP6h_E"
    )
    assert extractor._extract_video_id("https://youtu.be/Af3NmSP6h_E") == "Af3NmSP6h_E"
    assert (
        extractor._extract_video_id("https://www.youtube.com/shorts/Af3NmSP6h_E")
        == "Af3NmSP6h_E"
    )


def test_youtube_api_extractor_maps_response_to_metadata(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "k")
    from app.shared.config.settings import get_settings

    get_settings.cache_clear()
    extractor = YouTubeApiExtractor()

    class _Resp:
        status_code = 200

        @staticmethod
        def json():
            return {
                "items": [
                    {
                        "snippet": {
                            "title": "Title",
                            "channelTitle": "Channel",
                            "description": "Desc",
                            "tags": ["a", "b"],
                        }
                    }
                ]
            }

    from app.modules.videos.infrastructure import extractors as ext_mod

    def _fake_get(url, params, timeout):
        assert url.endswith("/videos")
        assert params.get("part") == "snippet"
        assert params.get("key") == "k"
        assert timeout == 20
        return _Resp()

    monkeypatch.setattr(ext_mod.requests, "get", _fake_get)

    metadata = extractor.extract("https://www.youtube.com/watch?v=Af3NmSP6h_E")
    assert metadata.title == "Title"
    assert metadata.channel == "Channel"
    assert metadata.description == "Desc"
    assert metadata.tags == ["a", "b"]


def test_hybrid_falls_back_to_ytdlp_when_api_key_missing(monkeypatch):
    from app.shared.config.settings import get_settings

    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    get_settings.cache_clear()

    class _Primary:
        def extract(self, url, manual_priority=None):
            raise NonRetryableExtractionError("YOUTUBE_API_KEY is required")

    class _Fallback:
        def extract(self, url, manual_priority=None):
            return _StubYDL({}, None)  # sentinel-like object for assertion

    hybrid = HybridVideoExtractor(primary=_Primary(), fallback=_Fallback())
    result = hybrid.extract("https://www.youtube.com/watch?v=Af3NmSP6h_E")
    assert isinstance(result, _StubYDL)


def test_build_video_extractor_defaults_to_hybrid(monkeypatch):
    monkeypatch.setenv("VIDEO_EXTRACTOR_MODE", "hybrid")
    monkeypatch.setenv("YOUTUBE_API_KEY", "k")
    from app.shared.config.settings import get_settings

    get_settings.cache_clear()
    extractor = build_video_extractor()
    assert isinstance(extractor, HybridVideoExtractor)


def test_build_video_extractor_yt_mode(monkeypatch):
    monkeypatch.setenv("VIDEO_EXTRACTOR_MODE", "yt_dlp")
    from app.shared.config.settings import get_settings

    get_settings.cache_clear()
    extractor = build_video_extractor()
    assert isinstance(extractor, MetadataExtractor)
