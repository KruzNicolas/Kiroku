from fastapi.testclient import TestClient

from app.main import app
from app.modules.study_assets.api.router import get_study_assets_service
from app.shared.security.state import idempotency_store, rate_limiter


class StubStudyAssetsService:
    def create_japanese_asset(
        self,
        image_bytes: bytes,
        image_content_type: str,
        notes: str | None = None,
    ):
        return {
            "status": "ok",
            "page_id": "study_page_123",
            "language": "japanese",
            "asset_id": "20260324-120000-abc123",
            "title": "JP Asset 20260324-120000-abc123",
        }


def _override_service() -> StubStudyAssetsService:
    return StubStudyAssetsService()


def _auth_headers(idempotency_key: str):
    return {
        "Authorization": "Bearer test-internal-token",
        "X-Source": "discord-bot",
        "X-Source-Message-Id": "msg-1",
        "X-Source-User-Id": "user-1",
        "Idempotency-Key": idempotency_key,
    }


def test_create_japanese_asset_endpoint_contract():
    from app.shared.config.settings import get_settings

    get_settings.cache_clear()
    idempotency_store.clear()
    rate_limiter.clear()

    app.dependency_overrides[get_study_assets_service] = _override_service
    client = TestClient(app)

    response = client.post(
        "/api/v1/study-assets/japanese",
        data={"note": "for future anki cards"},
        files={"image": ("study.png", b"fake-image", "image/png")},
        headers=_auth_headers("discord:g:c:m-study-1"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ok"
    assert body["page_id"] == "study_page_123"
    assert body["language"] == "japanese"
    assert body["asset_id"] == "20260324-120000-abc123"
    assert body["title"] == "JP Asset 20260324-120000-abc123"

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_create_japanese_asset_rejects_unsupported_mime_type():
    from app.shared.config.settings import get_settings

    get_settings.cache_clear()
    idempotency_store.clear()
    rate_limiter.clear()

    app.dependency_overrides[get_study_assets_service] = _override_service
    client = TestClient(app)

    response = client.post(
        "/api/v1/study-assets/japanese",
        data={"note": "for future anki cards"},
        files={"image": ("study.heic", b"fake-image", "image/heic")},
        headers=_auth_headers("discord:g:c:m-study-2"),
    )

    assert response.status_code == 400
    body = response.json()
    assert "Unsupported study asset image type" in body["detail"]

    app.dependency_overrides.clear()
    get_settings.cache_clear()
