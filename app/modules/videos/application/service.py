from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Protocol

from app.modules.videos.domain.models import FinalPayload, PriorityEnum
from app.modules.videos.module_config import get_videos_database_id
from app.shared.config.dates import current_added_at_iso_date
from app.shared.config.settings import get_settings
from app.shared.notion.client import build_notion_client
from app.shared.notion.contracts import NotionSaveCommand, NotionUpsertDescriptor
from app.shared.notion.save_layer import NotionSaveLayer


class ExtractorPort(Protocol):
    def extract(self, url: str, manual_priority: PriorityEnum | None = None) -> Any: ...


class InferencerPort(Protocol):
    def infer(self, metadata: Any) -> Any: ...


class NotionSaveLayerPort(Protocol):
    def upsert_page(self, command: NotionSaveCommand) -> str: ...


class VideosService:
    def __init__(
        self,
        extractor: ExtractorPort,
        inferencer: InferencerPort,
        notion_save_layer: NotionSaveLayerPort,
    ):
        self.extractor = extractor
        self.inferencer = inferencer
        self.notion_save_layer = notion_save_layer

    def create_video(self, raw_input: str) -> dict[str, str]:
        parts = raw_input.strip().split()
        if not parts:
            raise ValueError("Empty input")

        url = parts[0]
        manual_priority = None
        if len(parts) > 1:
            prio_map = {
                "high": PriorityEnum.HIGH,
                "medium": PriorityEnum.MEDIUM,
                "low": PriorityEnum.LOW,
                "later": PriorityEnum.LATER,
            }
            manual_priority = prio_map.get(parts[1].lower())

        metadata = self.extractor.extract(url, manual_priority=manual_priority)
        inference = self.inferencer.infer(metadata)

        settings = get_settings()
        if settings.app_test_write_mode and inference.confidence >= 0.8:
            inference = inference.model_copy(update={"confidence": 0.79})

        payload = FinalPayload(metadata=metadata, inference=inference)
        added_at_iso_date = current_added_at_iso_date()

        properties = {
            "Title": {"title": [{"text": {"content": payload.metadata.title}}]},
            "Channel": {"rich_text": [{"text": {"content": payload.metadata.channel}}]},
            "URL": {"url": payload.metadata.url},
            "Category": {"select": {"name": payload.inference.category.value}},
            "Priority": {"select": {"name": payload.final_priority.value}},
            "Confidence": {"number": payload.inference.confidence},
            "Added at": {"date": {"start": added_at_iso_date}},
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

        command = NotionSaveCommand(
            database_id=get_videos_database_id(),
            properties=properties,
            children=children,
            upsert=NotionUpsertDescriptor(
                property_name="URL",
                property_type="url",
                equals=payload.metadata.url,
            ),
        )
        page_id = self.notion_save_layer.upsert_page(command)
        return {"status": "ok", "page_id": page_id, "url": payload.metadata.url}

    def create_videos_bulk(self, raw_inputs: list[str], max_workers: int = 3) -> dict:
        if not raw_inputs:
            raise ValueError("inputs cannot be empty")

        cleaned_inputs = [item.strip() for item in raw_inputs if item and item.strip()]
        if not cleaned_inputs:
            raise ValueError("inputs cannot be empty")

        max_workers = max(1, min(max_workers, 10))

        results: list[dict[str, str | bool]] = []
        success_count = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_input = {
                executor.submit(
                    _create_video_worker, item, self.extractor, self.inferencer
                ): item
                for item in cleaned_inputs
            }

            for future in as_completed(future_to_input):
                original_input = future_to_input[future]
                url = (
                    original_input.split()[0]
                    if original_input.split()
                    else original_input
                )
                try:
                    output = future.result(timeout=120)
                    if output.get("success"):
                        success_count += 1
                    results.append(output)
                except TimeoutError:
                    results.append(
                        {
                            "success": False,
                            "url": url,
                            "error": "Processing timed out after 120s",
                        }
                    )
                except Exception as exc:
                    results.append(
                        {
                            "success": False,
                            "url": url,
                            "error": str(exc),
                        }
                    )

        total = len(cleaned_inputs)
        fail_count = total - success_count
        failed_urls = [
            item["url"]
            for item in results
            if item.get("success") is False and isinstance(item.get("url"), str)
        ]
        return {
            "status": "ok",
            "total": total,
            "success_count": success_count,
            "fail_count": fail_count,
            "failed_urls": failed_urls,
            "results": results,
        }


def _create_video_worker(
    raw_input: str, extractor: ExtractorPort, inferencer: InferencerPort
) -> dict:
    """Thread-safe worker that creates its own NotionSaveLayer."""
    notion_client = build_notion_client()
    notion_save_layer = NotionSaveLayer(notion_client)
    service = VideosService(
        extractor=extractor,
        inferencer=inferencer,
        notion_save_layer=notion_save_layer,
    )
    try:
        result = service.create_video(raw_input)
        return {"success": True, **result}
    except Exception as exc:
        parts = raw_input.strip().split()
        url = parts[0] if parts else raw_input
        return {"success": False, "url": url, "error": str(exc)}
