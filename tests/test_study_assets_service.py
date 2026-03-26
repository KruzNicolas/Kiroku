from app.modules.study_assets.application.service import StudyAssetsService


class StubNotionSaveLayer:
    def __init__(self):
        self.last_command = None
        self.last_upload = None

    def create_page(self, command):
        self.last_command = command
        return "study_page_123"

    def upload_file(self, *, content: bytes, filename: str, content_type: str):
        self.last_upload = {
            "content": content,
            "filename": filename,
            "content_type": content_type,
        }
        return "upload-file-123"


def test_create_japanese_asset_success(monkeypatch):
    monkeypatch.setenv("NOTION_DATABASE_ID_STUDY_ASSETS_JAPANESE", "db_jp_123")

    from app.shared.config.settings import get_settings

    get_settings.cache_clear()

    notion_layer = StubNotionSaveLayer()
    service = StudyAssetsService(notion_save_layer=notion_layer)

    result = service.create_japanese_asset(
        image_bytes=b"fake_image",
        image_content_type="image/png",
        notes="test notes",
    )

    assert result["status"] == "ok"
    assert result["page_id"] == "study_page_123"
    assert result["language"] == "japanese"
    assert result["asset_id"]
    assert result["title"].startswith("JP Asset ")
    assert notion_layer.last_upload is not None
    assert notion_layer.last_upload["content"] == b"fake_image"
    assert notion_layer.last_upload["content_type"] == "image/png"
    assert notion_layer.last_command is not None
    assert notion_layer.last_command.properties["Status"]["select"]["name"] == "Pending"
    assert (
        notion_layer.last_command.properties["Image"]["files"][0]["type"]
        == "file_upload"
    )
    assert notion_layer.last_command.properties["Image"]["files"][0]["file_upload"] == {
        "id": "upload-file-123"
    }
    assert notion_layer.last_command.properties["Image"]["files"][0]["name"].endswith(
        ".png"
    )
    assert notion_layer.last_command.properties["Added at"]["date"]["start"]
    assert notion_layer.last_command.upsert is None
    assert (
        notion_layer.last_command.properties["Note"]["rich_text"][0]["text"]["content"]
        == "test notes"
    )

    monkeypatch.delenv("NOTION_DATABASE_ID_STUDY_ASSETS_JAPANESE", raising=False)
    get_settings.cache_clear()


def test_create_japanese_asset_without_db_raises(monkeypatch):
    monkeypatch.setenv("NOTION_DATABASE_ID_STUDY_ASSETS_JAPANESE", "")

    from app.shared.config.settings import get_settings

    get_settings.cache_clear()

    service = StudyAssetsService(notion_save_layer=StubNotionSaveLayer())

    try:
        service.create_japanese_asset(
            image_bytes=b"fake_image", image_content_type="image/jpeg"
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert str(exc) == "NOTION_DATABASE_ID_STUDY_ASSETS_JAPANESE is required"

    get_settings.cache_clear()


def test_create_japanese_asset_without_note_sets_empty_rich_text(monkeypatch):
    monkeypatch.setenv("NOTION_DATABASE_ID_STUDY_ASSETS_JAPANESE", "db_jp_123")

    from app.shared.config.settings import get_settings

    get_settings.cache_clear()

    notion_layer = StubNotionSaveLayer()
    service = StudyAssetsService(notion_save_layer=notion_layer)

    service.create_japanese_asset(
        image_bytes=b"fake_image",
        image_content_type="image/jpeg",
    )

    assert notion_layer.last_command is not None
    assert notion_layer.last_command.properties["Note"]["rich_text"] == []

    monkeypatch.delenv("NOTION_DATABASE_ID_STUDY_ASSETS_JAPANESE", raising=False)
    get_settings.cache_clear()
