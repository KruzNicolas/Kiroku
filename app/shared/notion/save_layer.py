from notion_client import Client
from notion_client.errors import APIResponseError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.shared.notion.contracts import NotionSaveCommand


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
            query_response = self.client.request(
                path=f"databases/{command.database_id}/query",
                method="POST",
                body={
                    "filter": {
                        "property": "URL",
                        "url": {"equals": command.unique_url},
                    }
                },
            )

            results = query_response.get("results", [])
            if results:
                page_id = results[0]["id"]
                self.client.pages.update(page_id=page_id, properties=command.properties)
                return page_id

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
