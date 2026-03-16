from notion_client import Client
from notion_client.errors import APIResponseError
from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
)
from .models import FinalPayload
from .config import config


class NotionWriterError(Exception):
    pass


class NotionWriter:
    def __init__(self):
        # We assume the config is already validated
        # Enforce API version 2022-06-28 to maintain compatibility with databases/{id}/query
        self.client = Client(auth=config.NOTION_TOKEN, notion_version="2022-06-28")
        self.database_id = config.NOTION_DATABASE_ID

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(APIResponseError),
        reraise=True,
    )
    def upsert_page(self, payload: FinalPayload) -> str:
        """
        Creates or updates a notion page.
        Returns the Notion page ID.
        """
        properties = {
            "Title": {"title": [{"text": {"content": payload.metadata.title}}]},
            "URL": {"url": payload.metadata.url},
            "Category": {"select": {"name": payload.inference.category.value}},
            "Priority": {"select": {"name": payload.final_priority.value}},
            "Confidence": {"number": payload.inference.confidence},
        }

        children = [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "AI Rationale"}}]
                },
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [
                        {
                            "type": "text",
                            "text": {"content": payload.inference.rationale},
                        }
                    ]
                },
            },
        ]

        try:
            # Query if page already exists with this URL
            query_response = self.client.request(
                path=f"databases/{self.database_id}/query",
                method="POST",
                body={
                    "filter": {
                        "property": "URL",
                        "url": {"equals": payload.metadata.url},
                    }
                },
            )

            results = query_response.get("results", [])

            if results:
                # Update existing page (upsert)
                page_id = results[0]["id"]
                self.client.pages.update(page_id=page_id, properties=properties)

                # We do not append new children blocks when updating in v1
                # to avoid duplicated "AI Rationale" blocks if ran multiple times.
                # A proper update would require deleting old blocks and adding new ones,
                # but for simplicity, we just update properties.

                return page_id
            else:
                # Create new page
                response = self.client.pages.create(  # type: ignore
                    parent={"database_id": self.database_id},
                    properties=properties,
                    children=children,
                )
                if isinstance(response, dict):
                    return response["id"]
                return "unknown_id"

        except APIResponseError as e:
            # Re-raise for tenacity to catch and retry if it's a rate limit (429) or transient error
            raise e
        except Exception as e:
            raise NotionWriterError(f"Failed to upsert Notion page: {str(e)}")
