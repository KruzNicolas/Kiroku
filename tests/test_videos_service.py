import app.modules.videos.application.service as videos_service_module
from app.modules.videos.application.service import VideosService
from app.modules.videos.domain.models import (
    CategoryEnum,
    InferenceResult,
    PriorityEnum,
    VideoMetadata,
)


class StubExtractor:
    def extract(self, url: str, manual_priority: PriorityEnum | None = None):
        return VideoMetadata(
            url=url,
            title="Sample Title",
            channel="Sample Channel",
            description="Sample Description",
            tags=["dev"],
            game_category=None,
            manual_priority=manual_priority,
        )


class StubInferencer:
    def infer(self, metadata: VideoMetadata):
        return InferenceResult(
            category=CategoryEnum.DEV,
            priority=PriorityEnum.MEDIUM,
            rationale=f"Based on title {metadata.title}",
            confidence=0.9,
        )


class StubNotionSaveLayer:
    def __init__(self):
        self.last_command = None

    def upsert_page(self, command):
        self.last_command = command
        return "page_test_123"


def _patch_added_at_date(monkeypatch, value: str = "2026-03-23"):
    monkeypatch.setattr(
        videos_service_module,
        "current_added_at_iso_date",
        lambda: value,
    )


def _build_service(notion_layer: StubNotionSaveLayer | None = None) -> VideosService:
    notion_layer = notion_layer or StubNotionSaveLayer()
    return VideosService(
        extractor=StubExtractor(),
        inferencer=StubInferencer(),
        notion_save_layer=notion_layer,
    )


def test_process_url_success_with_manual_priority(monkeypatch):
    from app.shared.config.settings import get_settings

    get_settings.cache_clear()

    # Ensure deterministic Added at date from shared date helper
    _patch_added_at_date(monkeypatch, "2026-03-23")

    service = _build_service()
    result = service.create_video("https://youtube.com/watch?v=test1 later")

    assert result["status"] == "ok"
    assert result["page_id"] == "page_test_123"
    assert result["url"] == "https://youtube.com/watch?v=test1"

    assert service.notion_save_layer.last_command is not None
    assert (
        service.notion_save_layer.last_command.properties["Added at"]["date"]["start"]
        == "2026-03-23"
    )
    assert service.notion_save_layer.last_command.upsert is not None
    assert service.notion_save_layer.last_command.upsert.property_name == "URL"
    assert service.notion_save_layer.last_command.upsert.property_type == "url"
    assert (
        service.notion_save_layer.last_command.upsert.equals
        == "https://youtube.com/watch?v=test1"
    )

    get_settings.cache_clear()


def test_create_video_preserves_url_for_upsert_descriptor():
    service = _build_service()
    result = service.create_video("https://youtube.com/watch?v=test-upsert&t=30s")

    assert result["status"] == "ok"
    assert service.notion_save_layer.last_command is not None
    assert service.notion_save_layer.last_command.upsert is not None
    assert service.notion_save_layer.last_command.upsert.property_name == "URL"
    assert service.notion_save_layer.last_command.upsert.property_type == "url"
    assert (
        service.notion_save_layer.last_command.upsert.equals
        == "https://youtube.com/watch?v=test-upsert&t=30s"
    )


def test_process_bulk_mixed_inputs():
    service = _build_service()
    result = service.create_videos_bulk(
        [
            "https://youtube.com/watch?v=test1",
            "https://youtube.com/watch?v=test2 low",
        ],
        max_workers=2,
    )

    assert result["status"] == "ok"
    assert result["total"] == 2
    assert result["success_count"] == 2
    assert result["fail_count"] == 0
    assert result["failed_urls"] == []
    assert len(result["results"]) == 2


def test_process_bulk_empty_inputs_raises_value_error():
    service = _build_service()

    try:
        service.create_videos_bulk([])
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert str(exc) == "inputs cannot be empty"


def test_process_url_forces_test_confidence_below_point_8(monkeypatch):
    monkeypatch.setenv("APP_TEST_WRITE_MODE", "true")

    from app.shared.config.settings import get_settings

    get_settings.cache_clear()
    _patch_added_at_date(monkeypatch, "2026-03-23")

    notion_layer = StubNotionSaveLayer()
    service = _build_service(notion_layer=notion_layer)
    result = service.create_video("https://youtube.com/watch?v=test3")

    assert result["status"] == "ok"
    assert notion_layer.last_command is not None
    assert notion_layer.last_command.properties["Confidence"]["number"] < 0.8

    monkeypatch.delenv("APP_TEST_WRITE_MODE", raising=False)
    get_settings.cache_clear()


class FailOnSpecificUrlNotionLayer(StubNotionSaveLayer):
    def upsert_page(self, command):
        self.last_command = command
        if command.upsert and "fail" in str(command.upsert.equals):
            raise RuntimeError("Simulated DB failure")
        return "page_test_123"


def test_create_videos_bulk_returns_failed_urls_on_errors():
    notion_layer = FailOnSpecificUrlNotionLayer()
    service = _build_service(notion_layer=notion_layer)

    result = service.create_videos_bulk(
        [
            "https://youtube.com/watch?v=ok1",
            "https://youtube.com/watch?v=fail2",
        ],
        max_workers=2,
    )

    assert result["status"] == "ok"
    assert result["total"] == 2
    assert result["success_count"] == 1
    assert result["fail_count"] == 1
    assert result["failed_urls"] == ["https://youtube.com/watch?v=fail2"]


def test_added_at_uses_configured_timezone(monkeypatch):
    monkeypatch.setenv("VIDEOS_ADDED_AT_TIMEZONE", "America/Bogota")

    from app.shared.config.settings import get_settings

    get_settings.cache_clear()
    _patch_added_at_date(monkeypatch, "2026-03-23")

    notion_layer = StubNotionSaveLayer()
    service = _build_service(notion_layer=notion_layer)
    result = service.create_video("https://youtube.com/watch?v=test-timezone")

    assert result["status"] == "ok"
    assert notion_layer.last_command is not None
    assert (
        notion_layer.last_command.properties["Added at"]["date"]["start"]
        == "2026-03-23"
    )

    monkeypatch.delenv("VIDEOS_ADDED_AT_TIMEZONE", raising=False)
    get_settings.cache_clear()
