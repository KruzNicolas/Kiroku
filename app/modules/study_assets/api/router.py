from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.modules.study_assets.application.service import StudyAssetsService
from app.shared.notion.client import build_notion_client
from app.shared.notion.save_layer import NotionSaveLayer, NotionSaveLayerError
from app.shared.security.validators import validate_image_type

router = APIRouter(
    prefix="/study-assets",
    tags=["study-assets"],
)


class CreateJapaneseAssetResponse(BaseModel):
    status: str
    page_id: str
    language: str
    asset_id: str
    title: str


def get_study_assets_service() -> StudyAssetsService:
    notion_client = build_notion_client()
    notion_save_layer = NotionSaveLayer(notion_client)
    return StudyAssetsService(notion_save_layer=notion_save_layer)


@router.post("/japanese", response_model=CreateJapaneseAssetResponse, status_code=201)
async def create_japanese_asset(
    image: UploadFile = File(...),
    note: str | None = Form(default=None, max_length=1024),
    service = Depends(get_study_assets_service),
) -> CreateJapaneseAssetResponse:
    try:
        content_type = (image.content_type or "").strip().lower()
        validate_image_type(content_type, context="study asset image")

        image_bytes = await image.read()
        if len(image_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Image too large. Max 10MB.")
        if not image_bytes:
            raise ValueError("image is empty")

        result = service.create_japanese_asset(
            image_bytes=image_bytes,
            image_content_type=content_type,
            notes=note,
        )
        return CreateJapaneseAssetResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except NotionSaveLayerError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=500,
            detail="Unexpected study asset processing error",
        ) from exc
