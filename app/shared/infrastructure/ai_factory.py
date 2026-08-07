from app.shared.config.settings import get_settings
from app.shared.infrastructure.ai_client import AIClient


def build_ai_client(module: str) -> AIClient:
    """Build an AIClient for a specific module.

    Uses per-module env vars (VIDEOS_AI_*, RECEIPTS_AI_*) when present,
    falling back to global AI_* vars for backward compatibility.
    """
    settings = get_settings()

    if module == "videos":
        base_url = settings.videos_ai_base_url or settings.ai_base_url
        model = settings.ai_model_video
    elif module == "receipts":
        base_url = settings.receipts_ai_base_url or settings.ai_base_url
        model = settings.ai_model_receipts
    else:
        raise ValueError(f"Unknown AI module: {module}")

    return AIClient(
        api_key=settings.ai_api_key,
        base_url=base_url,
        model=model,
    )
