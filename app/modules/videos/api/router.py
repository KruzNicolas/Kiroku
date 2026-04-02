from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.modules.videos.application.service import VideosService
from app.modules.videos.infrastructure.extractors import (
    ExtractionError,
    build_video_extractor,
)
from app.modules.videos.infrastructure.inferencer import (
    InferenceError,
    OllamaInferencer,
)
from app.shared.notion.client import build_notion_client
from app.shared.notion.save_layer import NotionSaveLayer, NotionSaveLayerError

router = APIRouter(prefix="/videos", tags=["videos"])


class ProcessVideoRequest(BaseModel):
    url: str
    manual_priority: str | None = None


class ProcessVideoResponse(BaseModel):
    status: str
    page_id: str
    url: str


class BulkVideoRequest(BaseModel):
    items: list[ProcessVideoRequest]
    max_workers: int = 3


class BulkVideoItemResult(BaseModel):
    success: bool
    url: str
    page_id: str | None = None
    error: str | None = None


class BulkVideoResponse(BaseModel):
    status: str
    total: int
    success_count: int
    fail_count: int
    failed_urls: list[str]
    results: list[BulkVideoItemResult]


def get_videos_service() -> VideosService:
    notion_client = build_notion_client()
    notion_save_layer = NotionSaveLayer(notion_client)
    return VideosService(
        extractor=build_video_extractor(),
        inferencer=OllamaInferencer(),
        notion_save_layer=notion_save_layer,
    )


@router.post("", response_model=ProcessVideoResponse, status_code=201)
async def create_video(
    request: ProcessVideoRequest,
    service: VideosService = Depends(get_videos_service),
) -> ProcessVideoResponse:
    try:
        raw_input = request.url
        if request.manual_priority:
            raw_input = f"{request.url} {request.manual_priority}"
        result = service.create_video(raw_input)
        return ProcessVideoResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (ExtractionError, InferenceError, NotionSaveLayerError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=500, detail="Unexpected processing error"
        ) from exc


@router.post("/batch", response_model=BulkVideoResponse)
async def create_videos_batch(
    request: BulkVideoRequest,
    service: VideosService = Depends(get_videos_service),
) -> BulkVideoResponse:
    try:
        raw_inputs: list[str] = []
        for item in request.items:
            raw_input = item.url
            if item.manual_priority:
                raw_input = f"{item.url} {item.manual_priority}"
            raw_inputs.append(raw_input)

        result = service.create_videos_bulk(raw_inputs, max_workers=request.max_workers)
        return BulkVideoResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=500, detail="Unexpected bulk processing error"
        ) from exc
