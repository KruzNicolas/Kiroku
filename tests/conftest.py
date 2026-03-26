import pytest


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch):
    monkeypatch.setenv("INTERNAL_API_TOKEN", "test-internal-token")
    monkeypatch.setenv("IDEMPOTENCY_TTL_SECONDS", "86400")
    monkeypatch.setenv("RATE_LIMIT_VIDEOS_PER_MIN", "20")
    monkeypatch.setenv("RATE_LIMIT_VIDEOS_BATCH_PER_MIN", "10")
    monkeypatch.setenv("RATE_LIMIT_RECEIPTS_PER_MIN", "5")
    monkeypatch.setenv("RATE_LIMIT_STUDY_ASSETS_JP_PER_MIN", "15")

    from app.shared.config.settings import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
