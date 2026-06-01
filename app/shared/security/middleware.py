from __future__ import annotations

import hmac
import json

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.shared.config.settings import get_settings
from app.shared.security.state import idempotency_store, rate_limiter


class BotGatewayHardeningMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api/v1"):
            return await call_next(request)

        settings = get_settings()

        auth_header = request.headers.get("authorization", "")
        expected = settings.internal_api_token
        if not expected:
            return JSONResponse(
                status_code=500,
                content={"detail": "INTERNAL_API_TOKEN is not configured"},
            )

        if not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

        token = auth_header.removeprefix("Bearer ").strip()
        if not hmac.compare_digest(token, expected):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

        ALLOWED_SOURCES = {"discord-bot", "telegram-bot"}
        raw_source = request.headers.get("x-source")
        if raw_source is not None and raw_source not in ALLOWED_SOURCES:
            return JSONResponse(
                status_code=400,
                content={"detail": f"Invalid X-Source header. Allowed: {', '.join(sorted(ALLOWED_SOURCES))}"},
            )
        source = raw_source if raw_source is not None else "unknown"
        source_message_id = request.headers.get("x-source-message-id", "-")
        source_user_id = request.headers.get("x-source-user-id", "-")

        request.state.source = source
        request.state.source_message_id = source_message_id
        request.state.source_user_id = source_user_id

        idempotency_key = request.headers.get("Idempotency-Key")
        stored_key = f"{source}:{idempotency_key}" if idempotency_key else None

        if stored_key:
            record = idempotency_store.get(stored_key)
            if record:
                return JSONResponse(
                    status_code=record.status_code,
                    content=record.body,
                    headers={"X-Idempotency-Replayed": "true"},
                )

        limit = self._resolve_limit(request.url.path, settings)
        if limit is not None:
            allowed, retry_after = rate_limiter.check(
                source=source, path=request.url.path, limit_per_min=limit
            )
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded"},
                    headers={"Retry-After": str(retry_after)},
                )

        response = await call_next(request)

        if limit is not None and response.status_code < 500:
            rate_limiter.increment(source=source, path=request.url.path)

        if stored_key and 200 <= response.status_code < 500:
            response = await self._capture_and_store_response(
                response=response,
                store_key=stored_key,
                ttl_seconds=settings.idempotency_ttl_seconds,
            )

        return response

    @staticmethod
    def _resolve_limit(path: str, settings) -> int | None:
        limits: dict[str, int] = {
            "/api/v1/videos": settings.rate_limit_videos_per_min,
            "/api/v1/videos/batch": settings.rate_limit_videos_batch_per_min,
            "/api/v1/receipts": settings.rate_limit_receipts_per_min,
            "/api/v1/study-assets/japanese": settings.rate_limit_study_assets_jp_per_min,
        }
        return limits.get(path)

    @staticmethod
    async def _capture_and_store_response(
        response: Response,
        store_key: str,
        ttl_seconds: int,
    ) -> Response:
        body_bytes = b""
        async for chunk in response.body_iterator:
            body_bytes += chunk

        content_type = response.headers.get("content-type", "")
        body_obj = None
        if "application/json" in content_type:
            try:
                body_obj = json.loads(body_bytes.decode("utf-8"))
            except Exception:
                body_obj = None

        if body_obj is not None:
            idempotency_store.set(
                key=store_key,
                status_code=response.status_code,
                body=body_obj,
                ttl_seconds=ttl_seconds,
            )

        headers = dict(response.headers)
        return Response(
            content=body_bytes,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )
