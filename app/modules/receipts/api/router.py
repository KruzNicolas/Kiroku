import base64
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.modules.receipts.application.service import ReceiptsService
from app.modules.receipts.infrastructure.ocr_inferencer import (
    ReceiptOCRInferencer,
    ReceiptsInferenceError,
)
from app.modules.receipts.infrastructure.sheets_writer import (
    GoogleSheetsWriter,
    GoogleSheetsWriterError,
)

router = APIRouter(prefix="/receipts", tags=["receipts"])
logger = logging.getLogger("kiroku.receipts.api")


class CreateReceiptResponse(BaseModel):
    status: str
    items_count: int
    items: list[dict]
    sheets: dict


class ManualReceiptItemInput(BaseModel):
    product: str
    quantity: float
    price: float


class ManualReceiptRequest(BaseModel):
    date: str
    category: str
    store: str
    items: list[ManualReceiptItemInput]
    request_id: str | None = None


def get_receipts_service() -> ReceiptsService:
    return ReceiptsService(
        inferencer=ReceiptOCRInferencer(),
        sheets_writer=GoogleSheetsWriter(),
    )


@router.post("", response_model=CreateReceiptResponse, status_code=201)
async def create_receipt_entries(
    receipt_image: UploadFile = File(...),
    store_hint: str | None = Form(default=None),
    request_id: str | None = Form(default=None),
    batch_category: str | None = Form(default=None),
    service: ReceiptsService = Depends(get_receipts_service),
) -> CreateReceiptResponse:
    try:
        logger.info(
            "receipts request received",
            extra={
                "request_id": request_id or "-",
                "method": "POST",
                "path": "/api/v1/receipts",
                "source": "-",
                "source_message_id": "-",
                "source_user_id": "-",
            },
        )

        content_type = (receipt_image.content_type or "").strip().lower()
        if content_type not in {"image/jpeg", "image/png"}:
            raise ValueError(
                "Unsupported receipt image type. Use image/jpeg or image/png (convert HEIC/HEIF before sending)."
            )

        image_bytes = await receipt_image.read()
        if not image_bytes:
            raise ValueError("receipt_image is empty")

        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        logger.info(
            "receipt image read and encoded",
            extra={
                "request_id": request_id or "-",
                "method": "POST",
                "path": "/api/v1/receipts",
                "source": "-",
                "source_message_id": "-",
                "source_user_id": "-",
            },
        )

        result = service.create_receipt_entries(
            image_base64=image_base64,
            store_hint=store_hint,
            request_id=request_id,
            batch_category=batch_category,
        )
        logger.info(
            "receipts request completed",
            extra={
                "request_id": request_id or "-",
                "method": "POST",
                "path": "/api/v1/receipts",
                "source": "-",
                "source_message_id": "-",
                "source_user_id": "-",
            },
        )
        return CreateReceiptResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ReceiptsInferenceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except GoogleSheetsWriterError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=500,
            detail="Unexpected receipt processing error",
        ) from exc


@router.post("/manual", response_model=CreateReceiptResponse, status_code=201)
async def create_manual_receipt_entries(
    request: ManualReceiptRequest,
    service: ReceiptsService = Depends(get_receipts_service),
) -> CreateReceiptResponse:
    try:
        result = service.create_manual_receipt_entries(
            date=request.date,
            category=request.category,
            store=request.store,
            items=[item.model_dump() for item in request.items],
            request_id=request.request_id,
        )
        return CreateReceiptResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GoogleSheetsWriterError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=500,
            detail="Unexpected manual receipt processing error",
        ) from exc


import logging
