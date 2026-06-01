from fastapi.testclient import TestClient

from app.main import app
from app.modules.receipts.api.router import get_receipts_service
from app.shared.security.state import idempotency_store, rate_limiter


class StubReceiptsService:
    def create_receipt_entries(
        self,
        image_base64: str,
        store_hint: str | None = None,
        request_id: str | None = None,
        batch_category: str | None = None,
        source: str = "unknown",
    ):
        return {
            "status": "ok",
            "items_count": 1,
            "items": [
                {
                    "date": "03/07/2026",
                    "category": batch_category or "Groceries",
                    "store": store_hint or "Inferred Store",
                    "product": "Milk",
                    "quantity": 2,
                    "price": 2.5,
                }
            ],
            "sheets": {
                "status": "sent",
                "rows_received": 1,
                "request_id": request_id or "generated-id",
            },
        }

    def create_manual_receipt_entries(
        self,
        date: str,
        category: str,
        store: str,
        items: list[dict],
        request_id: str | None = None,
        source: str = "unknown",
    ):
        return {
            "status": "ok",
            "items_count": len(items),
            "items": [
                {
                    "date": date,
                    "category": category,
                    "store": store,
                    "product": items[0]["product"],
                    "quantity": 1,
                    "price": items[0]["price"],
                }
            ],
            "sheets": {
                "status": "sent",
                "rows_received": len(items),
                "request_id": request_id or "generated-id",
            },
        }


def _override_service() -> StubReceiptsService:
    return StubReceiptsService()


def _auth_headers(idempotency_key: str):
    return {
        "Authorization": "Bearer test-internal-token",
        "X-Source": "telegram-bot",
        "X-Source-Message-Id": "msg-1",
        "X-Source-User-Id": "user-1",
        "Idempotency-Key": idempotency_key,
    }


def test_create_receipt_entries_endpoint_contract():
    from app.shared.config.settings import get_settings

    get_settings.cache_clear()
    idempotency_store.clear()
    rate_limiter.clear()

    app.dependency_overrides[get_receipts_service] = _override_service
    client = TestClient(app)

    response = client.post(
        "/api/v1/receipts",
        data={
            "store_hint": "Falabella",
            "request_id": "req-456",
            "batch_category": "Groceries",
        },
        files={"receipt_image": ("receipt.jpg", b"fake-image", "image/jpeg")},
        headers=_auth_headers("telegram:chat:update-1"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ok"
    assert body["items_count"] == 1
    assert body["items"][0]["store"] == "Falabella"
    assert body["items"][0]["category"] == "Groceries"
    assert body["items"][0].get("batch_id") is None
    assert body["sheets"]["status"] == "sent"
    assert body["sheets"]["request_id"] == "req-456"

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_create_receipt_entries_rejects_unsupported_mime_type():
    from app.shared.config.settings import get_settings

    get_settings.cache_clear()
    idempotency_store.clear()
    rate_limiter.clear()

    app.dependency_overrides[get_receipts_service] = _override_service
    client = TestClient(app)

    response = client.post(
        "/api/v1/receipts",
        data={
            "store_hint": "Falabella",
            "request_id": "req-457",
        },
        files={"receipt_image": ("receipt.heic", b"fake-image", "image/heic")},
        headers=_auth_headers("telegram:chat:update-2"),
    )

    assert response.status_code == 400
    body = response.json()
    assert "Unsupported receipt image type" in body["detail"]

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_receipts_api_surfaces_google_sheets_rejection_message():
    from app.shared.config.settings import get_settings

    class RejectingReceiptsService:
        def create_receipt_entries(
            self,
            image_base64,
            store_hint=None,
            request_id=None,
            batch_category=None,
            source="unknown",
        ):
            from app.modules.receipts.infrastructure.sheets_writer import (
                GoogleSheetsWriterError,
            )

            raise GoogleSheetsWriterError(
                "Google Sheets rejected payload: Item 0: date must be YYYY-MM-DD."
            )

    get_settings.cache_clear()
    idempotency_store.clear()
    rate_limiter.clear()

    app.dependency_overrides[get_receipts_service] = lambda: RejectingReceiptsService()
    client = TestClient(app)

    response = client.post(
        "/api/v1/receipts",
        data={
            "store_hint": "Falabella",
            "request_id": "req-458",
        },
        files={"receipt_image": ("receipt.jpg", b"fake-image", "image/jpeg")},
        headers=_auth_headers("telegram:chat:update-3"),
    )

    assert response.status_code == 502
    body = response.json()
    assert "date must be YYYY-MM-DD" in body["detail"]

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_create_manual_receipt_entries_endpoint_contract():
    from app.shared.config.settings import get_settings

    get_settings.cache_clear()
    idempotency_store.clear()
    rate_limiter.clear()

    app.dependency_overrides[get_receipts_service] = _override_service
    client = TestClient(app)

    response = client.post(
        "/api/v1/receipts/manual",
        json={
            "date": "2026-03-24",
            "category": "Others",
            "store": "MercadoLibre",
            "items": [
                {"product": "Keyboard X", "quantity": 1, "price": 400000},
            ],
            "request_id": "req-manual-2",
        },
        headers=_auth_headers("telegram:chat:update-manual-1"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ok"
    assert body["items_count"] == 1
    assert body["items"][0]["category"] == "Others"
    assert body["items"][0]["product"] == "Keyboard X"

    app.dependency_overrides.clear()
    get_settings.cache_clear()
