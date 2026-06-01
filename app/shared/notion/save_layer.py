from notion_client import Client
from notion_client.errors import APIResponseError
import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.shared.notion.contracts import NotionSaveCommand, NotionUpsertDescriptor
from app.shared.notion.client import _NOTION_API_VERSION
from app.shared.config.settings import get_settings


class NotionSaveLayerError(Exception):
    pass


class NotionSaveLayer:
    def __init__(self, client: Client):
        self.client = client

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(APIResponseError),
        reraise=True,
    )
    def upsert_page(self, command: NotionSaveCommand) -> str:
        try:
            existing_page_id = self._find_existing_page_id(command)
            if existing_page_id:
                self.client.pages.update(
                    page_id=existing_page_id,
                    properties=command.properties,
                )
                return existing_page_id

            response = self.client.pages.create(  # type: ignore[arg-type]
                parent={"database_id": command.database_id},
                properties=command.properties,
                children=command.children or [],
            )
            if isinstance(response, dict):
                return response.get("id", "unknown_id")
            return "unknown_id"
        except APIResponseError:
            raise
        except Exception as exc:  # pragma: no cover
            raise NotionSaveLayerError(f"Failed to upsert Notion page: {exc}") from exc

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(APIResponseError),
        reraise=True,
    )
    def create_page(self, command: NotionSaveCommand) -> str:
        try:
            response = self.client.pages.create(  # type: ignore[arg-type]
                parent={"database_id": command.database_id},
                properties=command.properties,
                children=command.children or [],
            )
            if isinstance(response, dict):
                return response.get("id", "unknown_id")
            return "unknown_id"
        except APIResponseError:
            raise
        except Exception as exc:  # pragma: no cover
            raise NotionSaveLayerError(f"Failed to create Notion page: {exc}") from exc

    def upload_file(self, *, content: bytes, filename: str, content_type: str) -> str:
        try:
            create_response = self._create_file_upload(
                filename=filename,
                content_type=content_type,
            )
            file_upload_id = create_response.get("id")
            if not file_upload_id:
                raise NotionSaveLayerError("Notion file upload did not return id")

            self._send_file_upload(file_upload_id, content, filename, content_type)

            uploaded = self._retrieve_file_upload(file_upload_id)
            status = uploaded.get("status")
            if status != "uploaded":
                raise NotionSaveLayerError(
                    f"Notion file upload failed with status: {status}"
                )
            return str(file_upload_id)
        except APIResponseError:
            raise
        except NotionSaveLayerError:
            raise
        except Exception as exc:  # pragma: no cover
            raise NotionSaveLayerError(
                f"Failed to upload file to Notion: {exc}"
            ) from exc

    def _create_file_upload(self, *, filename: str, content_type: str) -> dict:
        response = requests.post(
            "https://api.notion.com/v1/file_uploads",
            headers=self._notion_upload_headers(),
            json={
                "mode": "single_part",
                "filename": filename,
                "content_type": content_type,
            },
            timeout=30,
        )
        if response.status_code >= 400:
            raise NotionSaveLayerError(
                "Notion file upload create failed "
                f"with status {response.status_code}: {response.text}"
            )
        return response.json()

    def _retrieve_file_upload(self, file_upload_id: str) -> dict:
        response = requests.get(
            f"https://api.notion.com/v1/file_uploads/{file_upload_id}",
            headers=self._notion_upload_headers(),
            timeout=30,
        )
        if response.status_code >= 400:
            raise NotionSaveLayerError(
                "Notion file upload retrieve failed "
                f"with status {response.status_code}: {response.text}"
            )
        return response.json()

    def _notion_upload_headers(self) -> dict[str, str]:
        settings = get_settings()
        return {
            "Authorization": f"Bearer {settings.notion_token}",
            "Notion-Version": _NOTION_API_VERSION,
        }

    def _send_file_upload(
        self,
        file_upload_id: str,
        content: bytes,
        filename: str,
        content_type: str,
    ) -> None:
        send_url = f"https://api.notion.com/v1/file_uploads/{file_upload_id}/send"

        response = requests.post(
            send_url,
            headers=self._notion_upload_headers(),
            files={"file": (filename, content, content_type)},
            timeout=30,
        )
        if response.status_code >= 400:
            raise NotionSaveLayerError(
                "Notion file upload send failed "
                f"with status {response.status_code}: {response.text}"
            )

    def _find_existing_page_id(self, command: NotionSaveCommand) -> str | None:
        if command.upsert is None:
            return None

        query_response = self.client.request(
            path=f"databases/{command.database_id}/query",
            method="POST",
            body={"filter": self._build_upsert_filter(command.upsert)},
        )
        results = query_response.get("results", [])
        if not results:
            return None
        return results[0].get("id")

    def _build_upsert_filter(self, upsert: NotionUpsertDescriptor) -> dict:
        if upsert.property_type == "number" and not isinstance(
            upsert.equals, (int, float)
        ):
            raise NotionSaveLayerError(
                "Upsert filter value for number properties must be int or float"
            )

        filter_by_type = {
            "url": {"equals": str(upsert.equals)},
            "rich_text": {"equals": str(upsert.equals)},
            "title": {"equals": str(upsert.equals)},
            "number": {"equals": upsert.equals},
            "select": {"equals": str(upsert.equals)},
        }

        notion_filter = filter_by_type.get(upsert.property_type)
        if notion_filter is None:
            raise NotionSaveLayerError(
                f"Unsupported upsert filter property type: {upsert.property_type}"
            )

        return {
            "property": upsert.property_name,
            upsert.property_type: notion_filter,
        }
