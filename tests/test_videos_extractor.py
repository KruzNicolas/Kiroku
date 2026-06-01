import pytest

from app.modules.videos.infrastructure.extractors import (
    ExtractionError,
    NonRetryableExtractionError,
    YouTubeApiExtractor,
    build_video_extractor,
)


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


def test_build_video_extractor_returns_youtube_api_extractor(monkeypatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "k")
    from app.shared.config.settings import get_settings

    get_settings.cache_clear()
    extractor = build_video_extractor()
    assert isinstance(extractor, YouTubeApiExtractor)
