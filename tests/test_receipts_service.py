from app.modules.receipts.application.service import ReceiptsService
from app.modules.receipts.domain.models import ReceiptExtractionResult, ReceiptItem
from app.modules.receipts.infrastructure.sheets_writer import _normalize_sheet_date


class StubReceiptsInferencer:
    def extract(self, payload, source: str = "unknown"):
        return ReceiptExtractionResult(
            items=[
                ReceiptItem(
                    date="03/07/2026",
                    category="Groceries",
                    store=payload.store_hint or "Inferred Store",
                    product="Milk",
                    quantity=2,
                    price=2.5,
                )
            ]
        )


class StubSheetsWriter:
    def append_rows(self, items, request_id: str | None = None, source: str = "unknown"):
        return {
            "status": "sent",
            "rows_received": len(items),
            "request_id": request_id or "generated-id",
        }


def test_create_receipt_entries_success():
    service = ReceiptsService(
        inferencer=StubReceiptsInferencer(),
        sheets_writer=StubSheetsWriter(),
    )

    result = service.create_receipt_entries(
        image_base64="ZmFrZV9pbWFnZQ==",
        store_hint="Falabella",
        request_id="req-123",
    )

    assert result["status"] == "ok"
    assert result["items_count"] == 1
    assert result["items"][0]["store"] == "Falabella"
    assert result["items"][0].get("batch_id") is None
    assert result["items"][0]["quantity"] == 2.0
    assert result["sheets"]["status"] == "sent"
    assert result["sheets"]["request_id"] == "req-123"


def test_create_receipt_entries_applies_batch_category_override():
    service = ReceiptsService(
        inferencer=StubReceiptsInferencer(),
        sheets_writer=StubSheetsWriter(),
    )

    result = service.create_receipt_entries(
        image_base64="ZmFrZV9pbWFnZQ==",
        store_hint="Ara",
        request_id="req-124",
        batch_category="Groceries",
    )

    assert result["items_count"] == 1
    assert result["items"][0]["category"] == "Groceries"


def test_create_receipt_entries_rejects_invalid_batch_category():
    service = ReceiptsService(
        inferencer=StubReceiptsInferencer(),
        sheets_writer=StubSheetsWriter(),
    )

    try:
        service.create_receipt_entries(
            image_base64="ZmFrZV9pbWFnZQ==",
            store_hint="Ara",
            request_id="req-125",
            batch_category="Food",
        )
        assert False, "Expected ValueError"
    except ValueError as exc:
        assert "Invalid batch_category" in str(exc)


def test_receipt_item_supports_decimal_quantity_and_numeric_strings():
    item = ReceiptItem(
        date="03/19/2026",
        category="Groceries",
        store="Jeronimo",
        product="Cebolla",
        quantity="0,335",
        price="3.990",
    )

    assert item.quantity == 0.335
    assert item.price == 3990.0


def test_receipt_item_preserves_decimal_quantity_without_rounding():
    item = ReceiptItem(
        date="03/19/2026",
        category="Groceries",
        store="Jeronimo",
        product="Filete",
        quantity=1.5,
        price=24280,
    )

    assert item.quantity == 1.5


def test_normalize_sheet_date_supports_mm_dd_yyyy():
    assert _normalize_sheet_date("03/19/2026") == "2026-03-19"


def test_normalize_sheet_date_supports_iso_date():
    assert _normalize_sheet_date("2026-03-19") == "2026-03-19"


def test_normalize_sheet_date_supports_dd_mm_yyyy_when_day_is_unambiguous():
    assert _normalize_sheet_date("24/03/2026") == "2026-03-24"


def test_create_manual_receipt_entries_success():
    service = ReceiptsService(
        inferencer=StubReceiptsInferencer(),
        sheets_writer=StubSheetsWriter(),
    )

    result = service.create_manual_receipt_entries(
        date="2026-03-24",
        category="Others",
        store="MercadoLibre",
        items=[
            {"product": "Keyboard X", "quantity": 1, "price": 400000},
        ],
        request_id="req-manual-1",
    )

    assert result["status"] == "ok"
    assert result["items_count"] == 1
    assert result["items"][0]["category"] == "Others"
    assert result["items"][0]["product"] == "Keyboard X"


def test_receipt_price_scales_decimal_to_cop_thousands_when_needed():
    item = ReceiptItem(
        date="2026-03-19",
        category="Groceries",
        store="Ara",
        product="Leche",
        quantity=1,
        price=2.95,
    )

    assert item.price == 2950.0
