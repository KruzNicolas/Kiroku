from datetime import UTC, datetime
from uuid import uuid4

from app.modules.study_assets.domain.models import JapaneseStudyAssetInput
from app.shared.config.dates import current_added_at_iso_date
from app.shared.config.settings import get_settings
from app.shared.notion.contracts import NotionSaveCommand


class StudyAssetsService:
    def __init__(self, notion_save_layer):
        self.notion_save_layer = notion_save_layer

    def create_japanese_asset(
        self,
        image_bytes: bytes,
        image_content_type: str,
        notes: str | None = None,
    ) -> dict:
        payload = JapaneseStudyAssetInput(
            image_bytes=image_bytes,
            image_content_type=image_content_type,
            notes=notes,
        )
        settings = get_settings()

        database_id = settings.notion_database_id_study_assets_japanese
        if not database_id:
            raise ValueError("NOTION_DATABASE_ID_STUDY_ASSETS_JAPANESE is required")

        asset_id = self._generate_asset_id()
        title = f"JP Asset {asset_id}"
        image_filename = (
            f"{asset_id}.{self._extension_from_mime(payload.image_content_type)}"
        )
        file_upload_id = self.notion_save_layer.upload_file(
            content=payload.image_bytes,
            filename=image_filename,
            content_type=payload.image_content_type,
        )

        properties = {
            "Title": {
                "title": [
                    {
                        "text": {
                            "content": title,
                        }
                    }
                ]
            },
            "Image": {
                "files": [
                    {
                        "type": "file_upload",
                        "name": image_filename,
                        "file_upload": {"id": file_upload_id},
                    }
                ]
            },
            "Status": {"select": {"name": "Pending"}},
            "Note": {"rich_text": self._to_rich_text(payload.notes)},
            "Added at": {"date": {"start": current_added_at_iso_date()}},
        }

        command = NotionSaveCommand(
            database_id=database_id,
            properties=properties,
        )
        page_id = self.notion_save_layer.create_page(command)

        return {
            "status": "ok",
            "page_id": page_id,
            "language": "japanese",
            "asset_id": asset_id,
            "title": title,
        }

    def _generate_asset_id(self) -> str:
        ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        suffix = uuid4().hex[:6]
        return f"{ts}-{suffix}"

    def _to_rich_text(self, note: str | None) -> list[dict]:
        if not note:
            return []
        return [{"type": "text", "text": {"content": note}}]

    def _extension_from_mime(self, content_type: str) -> str:
        if content_type == "image/jpeg":
            return "jpg"
        if content_type == "image/png":
            return "png"
        return "bin"
