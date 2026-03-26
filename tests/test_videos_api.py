from fastapi.testclient import TestClient

from app.main import app
from app.modules.videos.api.router import get_videos_service
from app.shared.security.state import idempotency_store, rate_limiter


class StubVideosService:
    def create_video(self, raw_input: str):
        return {
            "status": "ok",
            "page_id": "abc123",
            "url": raw_input.split()[0],
        }

    def create_videos_bulk(self, raw_inputs: list[str], max_workers: int = 3):
        failed_urls = [
            item.split()[0] for item in raw_inputs if "fail" in item.split()[0]
        ]
        success_count = len(raw_inputs) - len(failed_urls)
        return {
            "status": "ok",
            "total": len(raw_inputs),
            "success_count": success_count,
            "fail_count": len(failed_urls),
            "failed_urls": failed_urls,
            "results": [
                {
                    "success": "fail" not in item.split()[0],
                    "url": item.split()[0],
                    "page_id": (
                        f"page-{index}" if "fail" not in item.split()[0] else None
                    ),
                    "error": (
                        None if "fail" not in item.split()[0] else "Simulated failure"
                    ),
                }
                for index, item in enumerate(raw_inputs)
            ],
        }


def _override_service() -> StubVideosService:
    return StubVideosService()


def _auth_headers(
    source: str = "discord-bot",
    idempotency_key: str = "discord:g:c:m1",
):
    return {
        "Authorization": "Bearer test-internal-token",
        "X-Source": source,
        "X-Source-Message-Id": "msg-1",
        "X-Source-User-Id": "user-1",
        "Idempotency-Key": idempotency_key,
    }


def test_health_endpoint_returns_ok():
    from app.shared.config.settings import get_settings

    get_settings.cache_clear()
    idempotency_store.clear()
    rate_limiter.clear()

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_process_video_endpoint_contract():
    from app.shared.config.settings import get_settings

    get_settings.cache_clear()
    idempotency_store.clear()
    rate_limiter.clear()

    app.dependency_overrides[get_videos_service] = _override_service
    client = TestClient(app)

    response = client.post(
        "/api/v1/videos",
        json={
            "url": "https://youtube.com/watch?v=123",
            "manual_priority": "later",
        },
        headers=_auth_headers(idempotency_key="discord:g:c:m-video-1"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ok"
    assert body["page_id"] == "abc123"
    assert body["url"] == "https://youtube.com/watch?v=123"

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_process_bulk_endpoint_contract():
    from app.shared.config.settings import get_settings

    get_settings.cache_clear()
    idempotency_store.clear()
    rate_limiter.clear()

    app.dependency_overrides[get_videos_service] = _override_service
    client = TestClient(app)

    response = client.post(
        "/api/v1/videos/batch",
        json={
            "items": [
                {"url": "https://youtube.com/watch?v=1"},
                {
                    "url": "https://youtube.com/watch?v=2",
                    "manual_priority": "later",
                },
            ],
            "max_workers": 2,
        },
        headers=_auth_headers(idempotency_key="discord:g:c:m-batch-1"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["total"] == 2
    assert body["success_count"] == 2
    assert body["fail_count"] == 0
    assert body["failed_urls"] == []
    assert len(body["results"]) == 2

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_process_bulk_endpoint_returns_failed_urls():
    from app.shared.config.settings import get_settings

    get_settings.cache_clear()
    idempotency_store.clear()
    rate_limiter.clear()

    app.dependency_overrides[get_videos_service] = _override_service
    client = TestClient(app)

    response = client.post(
        "/api/v1/videos/batch",
        json={
            "items": [
                {"url": "https://youtube.com/watch?v=ok1"},
                {"url": "https://youtube.com/watch?v=fail2"},
            ],
            "max_workers": 2,
        },
        headers=_auth_headers(idempotency_key="discord:g:c:m-batch-2"),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["total"] == 2
    assert body["success_count"] == 1
    assert body["fail_count"] == 1
    assert body["failed_urls"] == ["https://youtube.com/watch?v=fail2"]

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_requires_internal_api_token():
    from app.shared.config.settings import get_settings

    get_settings.cache_clear()
    idempotency_store.clear()
    rate_limiter.clear()

    client = TestClient(app)
    response = client.post(
        "/api/v1/videos",
        json={"url": "https://youtube.com/watch?v=123"},
    )
    assert response.status_code == 401


def test_idempotency_replays_response_without_reprocessing():
    from app.shared.config.settings import get_settings

    get_settings.cache_clear()
    idempotency_store.clear()
    rate_limiter.clear()

    app.dependency_overrides[get_videos_service] = _override_service
    client = TestClient(app)

    headers = _auth_headers(idempotency_key="discord:g:c:m-idem-1")

    first = client.post(
        "/api/v1/videos",
        json={"url": "https://youtube.com/watch?v=123"},
        headers=headers,
    )
    second = client.post(
        "/api/v1/videos",
        json={"url": "https://youtube.com/watch?v=123"},
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.headers.get("X-Idempotency-Replayed") == "true"
    assert first.json() == second.json()

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_rate_limit_blocks_when_exceeded():
    from app.shared.config.settings import get_settings

    get_settings.cache_clear()
    idempotency_store.clear()
    rate_limiter.clear()

    app.dependency_overrides[get_videos_service] = _override_service
    client = TestClient(app)

    last_response = None
    for idx in range(21):
        last_response = client.post(
            "/api/v1/videos",
            json={"url": f"https://youtube.com/watch?v={idx}"},
            headers=_auth_headers(idempotency_key=f"discord:g:c:m-rl-{idx}"),
        )

    assert last_response is not None
    assert last_response.status_code == 429
    assert last_response.headers.get("Retry-After") is not None

    app.dependency_overrides.clear()
    get_settings.cache_clear()
