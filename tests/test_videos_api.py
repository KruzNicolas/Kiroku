from fastapi.testclient import TestClient

from app.main import app
from app.modules.videos.api.router import get_videos_service


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


def test_health_endpoint_returns_ok():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_process_video_endpoint_contract():
    app.dependency_overrides[get_videos_service] = _override_service
    client = TestClient(app)

    response = client.post(
        "/api/v1/videos",
        json={
            "url": "https://youtube.com/watch?v=123",
            "manual_priority": "later",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "ok"
    assert body["page_id"] == "abc123"
    assert body["url"] == "https://youtube.com/watch?v=123"

    app.dependency_overrides.clear()


def test_process_bulk_endpoint_contract():
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


def test_process_bulk_endpoint_returns_failed_urls():
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
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["total"] == 2
    assert body["success_count"] == 1
    assert body["fail_count"] == 1
    assert body["failed_urls"] == ["https://youtube.com/watch?v=fail2"]

    app.dependency_overrides.clear()
