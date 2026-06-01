from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl, field_validator

from app.modules.videos.application.service import VideosService
from app.modules.videos.infrastructure.extractors import (
    ExtractionError,
    build_video_extractor,
)
from app.modules.videos.infrastructure.inferencer import (
    InferenceError,
    VideoInferencer,
)
from app.shared.notion.client import build_notion_client
from app.shared.notion.save_layer import NotionSaveLayer, NotionSaveLayerError

router = APIRouter(prefix="/videos", tags=["videos"])


class ProcessVideoRequest(BaseModel):
    url: str = Field(max_length=2048)
    manual_priority: str | None = Field(default=None, max_length=32)

    @field_validator("url")
    @classmethod
    def _validate_url(cls, v: str) -> str:
        HttpUrl(v)
        return v

    @field_validator("manual_priority")
    @classmethod
    def validate_priority(cls, v: str | None) -> str | None:
        if v is None:
            return v
        allowed = {"high", "medium", "low", "later"}
        if v.lower() not in allowed:
            raise ValueError(f"manual_priority must be one of: {allowed}")
        return v.lower()


class ProcessVideoResponse(BaseModel):
    status: str
    page_id: str
    url: str


class BulkVideoRequest(BaseModel):
    items: list[ProcessVideoRequest] = Field(max_length=15)
    max_workers: int = Field(default=3, ge=1, le=3)


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
        inferencer=VideoInferencer(),
        notion_save_layer=notion_save_layer,
    )


@router.post("", response_model=ProcessVideoResponse, status_code=201)
async def create_video(
    request: ProcessVideoRequest,
    service = Depends(get_videos_service),
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
    service = Depends(get_videos_service),
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
