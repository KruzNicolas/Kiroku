import base64
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, field_validator

from app.modules.receipts.application.service import ReceiptsService
from app.modules.receipts.domain.models import (
    _normalize_cop_price,
    _parse_money,
    _parse_quantity,
)
from app.modules.receipts.infrastructure.ocr_inferencer import (
    ReceiptInferencer,
    ReceiptsInferenceError,
)
from app.modules.receipts.infrastructure.sheets_writer import (
    GoogleSheetsWriter,
    GoogleSheetsWriterError,
)
from app.shared.security.validators import validate_image_type

router = APIRouter(prefix="/receipts", tags=["receipts"])
logger = logging.getLogger("kiroku.receipts.api")


class CreateReceiptResponse(BaseModel):
    status: str
    items_count: int
    items: list[dict]
    sheets: dict


class ManualReceiptItemInput(BaseModel):
    product: str
    quantity: str | float
    price: str | float

    @field_validator("quantity", mode="before")
    @classmethod
    def normalize_quantity(cls, value):
        parsed = None
        if isinstance(value, (int, float)):
            parsed = float(value)
        elif isinstance(value, str):
            parsed = _parse_quantity(value)
        if parsed is None:
            raise ValueError("Invalid numeric field")
        if parsed <= 0:
            return 1.0
        return float(parsed)

    @field_validator("price", mode="before")
    @classmethod
    def normalize_price(cls, value):
        parsed = None
        if isinstance(value, (int, float)):
            parsed = float(value)
        elif isinstance(value, str):
            parsed = _parse_money(value)
        if parsed is None:
            raise ValueError("Invalid numeric field")
        return _normalize_cop_price(parsed)


class ManualReceiptRequest(BaseModel):
    date: str
    category: str
    store: str
    items: list[ManualReceiptItemInput]
    request_id: str | None = None


def get_receipts_service() -> ReceiptsService:
    return ReceiptsService(
        inferencer=ReceiptInferencer(),
        sheets_writer=GoogleSheetsWriter(),
    )


@router.post("", response_model=CreateReceiptResponse, status_code=201)
async def create_receipt_entries(
    http_request: Request,
    receipt_image: UploadFile = File(...),
    store_hint: str | None = Form(default=None, max_length=256),
    batch_category: str | None = Form(default=None, max_length=256),
    request_id: str | None = Form(default=None, max_length=256),
    service = Depends(get_receipts_service),
) -> CreateReceiptResponse:
    source = getattr(http_request.state, "source", "unknown")
    try:
        logger.info(
            "receipts request received",
            extra={
                "request_id": request_id or "-",
                "method": "POST",
                "path": "/api/v1/receipts",
                "source": source,
                "source_message_id": "-",
                "source_user_id": "-",
            },
        )

        content_type = (receipt_image.content_type or "").strip().lower()
        validate_image_type(content_type, context="receipt image")

        image_bytes = await receipt_image.read()
        if len(image_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Image too large. Max 10MB.")
        if not image_bytes:
            raise ValueError("receipt_image is empty")

        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        logger.info(
            "receipt image read and encoded",
            extra={
                "request_id": request_id or "-",
                "method": "POST",
                "path": "/api/v1/receipts",
                "source": source,
                "source_message_id": "-",
                "source_user_id": "-",
            },
        )

        result = service.create_receipt_entries(
            image_base64=image_base64,
            store_hint=store_hint,
            request_id=request_id,
            batch_category=batch_category,
            source=source,
        )
        logger.info(
            "receipts request completed",
            extra={
                "request_id": request_id or "-",
                "method": "POST",
                "path": "/api/v1/receipts",
                "source": source,
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
    http_request: Request,
    service = Depends(get_receipts_service),
) -> CreateReceiptResponse:
    source = getattr(http_request.state, "source", "unknown")
    try:
        result = service.create_manual_receipt_entries(
            date=request.date,
            category=request.category,
            store=request.store,
            items=[item.model_dump() for item in request.items],
            request_id=request.request_id,
            source=source,
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
