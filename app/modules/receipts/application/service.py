import logging
from typing import Protocol

from app.modules.receipts.domain.models import ReceiptExtractionInput, ReceiptItem


ALLOWED_RECEIPT_CATEGORIES = {
    "Groceries",
    "Pharmacy",
    "Transport",
    "Utilities",
    "Subscriptions",
    "Debt",
    "Leisure",
    "Others",
}


class OCRInferencerPort(Protocol):
    def extract(self, payload: ReceiptExtractionInput, source: str = "unknown"): ...


class SheetsWriterPort(Protocol):
    def append_rows(
        self, items: list, request_id: str | None = None, source: str = "unknown"
    ): ...


class ReceiptsService:
    def __init__(
        self,
        inferencer: OCRInferencerPort,
        sheets_writer: SheetsWriterPort,
    ):
        self.inferencer = inferencer
        self.sheets_writer = sheets_writer
        self.logger = logging.getLogger("kiroku.receipts.service")

    def create_receipt_entries(
        self,
        image_base64: str,
        store_hint: str | None = None,
        request_id: str | None = None,
        batch_category: str | None = None,
        source: str = "unknown",
    ) -> dict:
        self.logger.info(
            "receipts workflow started",
            extra={
                "request_id": request_id or "-",
                "method": "-",
                "path": "/api/v1/receipts",
                "source": source,
                "source_message_id": "-",
                "source_user_id": "-",
            },
        )

        payload = ReceiptExtractionInput(
            image_base64=image_base64,
            store_hint=store_hint,
        )

        self.logger.info(
            "receipts ocr extraction started",
            extra={
                "request_id": request_id or "-",
                "method": "-",
                "path": "/api/v1/receipts",
                "source": source,
                "source_message_id": "-",
                "source_user_id": "-",
            },
        )
        extraction = self.inferencer.extract(payload, source=source)

        normalized_items = self._apply_batch_category_override(
            extraction.items,
            batch_category=batch_category,
        )
        self.logger.info(
            "receipts ocr extraction completed",
            extra={
                "request_id": request_id or "-",
                "method": "-",
                "path": "/api/v1/receipts",
                "source": source,
                "source_message_id": "-",
                "source_user_id": "-",
            },
        )

        self.logger.info(
            "receipts sheets sync started",
            extra={
                "request_id": request_id or "-",
                "method": "-",
                "path": "/api/v1/receipts",
                "source": source,
                "source_message_id": "-",
                "source_user_id": "-",
            },
        )
        sheets_result = self.sheets_writer.append_rows(
            normalized_items, request_id=request_id, source=source
        )
        self.logger.info(
            "receipts sheets sync completed",
            extra={
                "request_id": request_id or "-",
                "method": "-",
                "path": "/api/v1/receipts",
                "source": source,
                "source_message_id": "-",
                "source_user_id": "-",
            },
        )

        return {
            "status": "ok",
            "items_count": len(normalized_items),
            "items": [item.model_dump() for item in normalized_items],
            "sheets": sheets_result,
        }

    def create_manual_receipt_entries(
        self,
        date: str,
        category: str,
        store: str,
        items: list[dict],
        request_id: str | None = None,
        source: str = "unknown",
    ) -> dict:
        if not items:
            raise ValueError("items cannot be empty")

        normalized_category = category.strip().title()
        if normalized_category not in ALLOWED_RECEIPT_CATEGORIES:
            allowed = ", ".join(sorted(ALLOWED_RECEIPT_CATEGORIES))
            raise ValueError(
                f"Invalid category '{category}'. Allowed values: {allowed}"
            )

        receipt_items: list[ReceiptItem] = []
        for item in items:
            receipt_items.append(
                ReceiptItem(
                    date=date,
                    category=normalized_category,
                    store=store,
                    product=item["product"],
                    quantity=item["quantity"],
                    price=item["price"],
                )
            )

        sheets_result = self.sheets_writer.append_rows(
            receipt_items, request_id=request_id, source=source
        )
        return {
            "status": "ok",
            "items_count": len(receipt_items),
            "items": [item.model_dump() for item in receipt_items],
            "sheets": sheets_result,
        }

    def _apply_batch_category_override(
        self,
        items: list[ReceiptItem],
        batch_category: str | None,
    ) -> list[ReceiptItem]:
        if not batch_category:
            return items

        normalized = batch_category.strip().title()
        if normalized not in ALLOWED_RECEIPT_CATEGORIES:
            allowed = ", ".join(sorted(ALLOWED_RECEIPT_CATEGORIES))
            raise ValueError(
                f"Invalid batch_category '{batch_category}'. Allowed values: {allowed}"
            )

        return [item.model_copy(update={"category": normalized}) for item in items]
