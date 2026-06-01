import uuid
import logging
from datetime import datetime

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.modules.receipts.domain.models import ReceiptItem
from app.shared.config.settings import get_settings


class GoogleSheetsWriterError(Exception):
    pass


class GoogleSheetsWriter:
    """Writer for Google Apps Script doPost endpoint integration."""

    def append_rows(
        self,
        items: list[ReceiptItem],
        request_id: str | None = None,
        source: str = "unknown",
    ) -> dict:
        logger = logging.getLogger("kiroku.receipts.sheets")
        settings = get_settings()

        if not settings.receipts_google_sheets_url:
            return {
                "status": "pending",
                "message": "Google Sheets URL is not configured",
                "target_url": settings.receipts_google_sheets_url,
                "rows_received": len(items),
            }

        if not settings.receipts_google_sheets_api_token:
            return {
                "status": "pending",
                "message": "Google Sheets API token is not configured",
                "target_url": settings.receipts_google_sheets_url,
                "rows_received": len(items),
            }

        payload = {
            "token": settings.receipts_google_sheets_api_token,
            "requestId": request_id or str(uuid.uuid4()),
            "purchaseData": [
                {
                    "date": _normalize_sheet_date(item.date),
                    "category": item.category,
                    "store": item.store,
                    "product": item.product,
                    "quantity": item.quantity,
                    "price": item.price,
                }
                for item in items
            ],
        }

        try:
            logger.info(
                "google sheets post started",
                extra={
                    "request_id": payload["requestId"],
                    "method": "POST",
                    "path": settings.receipts_google_sheets_url or "-",
                    "source": source,
                    "source_message_id": "-",
                    "source_user_id": "-",
                },
            )
            response = self._post_payload(
                settings.receipts_google_sheets_url, payload
            )
            logger.info(
                "google sheets post completed",
                extra={
                    "request_id": payload["requestId"],
                    "method": "POST",
                    "path": settings.receipts_google_sheets_url or "-",
                    "source": source,
                    "source_message_id": "-",
                    "source_user_id": "-",
                },
            )

            response_json = None
            try:
                response_json = response.json()
            except Exception:
                response_json = {"raw": response.text}

            if isinstance(response_json, dict):
                status_code = response_json.get("statusCode")
                ok_flag = response_json.get("ok")
                if status_code and isinstance(status_code, int) and status_code >= 400:
                    raise GoogleSheetsWriterError(
                        f"Google Sheets rejected payload: {response_json.get('error', 'unknown error')}"
                    )
                if ok_flag is False:
                    raise GoogleSheetsWriterError(
                        f"Google Sheets rejected payload: {response_json.get('error', 'unknown error')}"
                    )

            return {
                "status": "sent",
                "target_url": settings.receipts_google_sheets_url,
                "rows_received": len(items),
                "request_id": payload["requestId"],
                "upstream_status_code": response.status_code,
                "upstream_response": response_json,
            }
        except requests.RequestException as exc:
            logger.exception("google sheets post failed")
            raise GoogleSheetsWriterError(
                f"Failed to send rows to Google Sheets: {exc}"
            ) from exc

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(requests.RequestException),
        reraise=True,
    )
    def _post_payload(self, url: str, payload: dict) -> requests.Response:
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
        return response


def _normalize_sheet_date(raw_date: str) -> str:
    value = (raw_date or "").strip()
    if not value:
        raise GoogleSheetsWriterError("Missing date for spreadsheet payload")

    # Already ISO date
    if len(value) == 10 and value[4] == "-" and value[7] == "-":
        return value

    # Canonical parse for slash-based formats
    if "/" in value:
        parts = value.split("/")
        if len(parts) == 3:
            a, b, c = parts
            try:
                year = int(c)
                first = int(a)
                second = int(b)
            except Exception as exc:
                raise GoogleSheetsWriterError(
                    f"Unsupported date format for spreadsheet payload: {raw_date}"
                ) from exc

            if len(c) == 2:
                year = 2000 + year

            # If first token is > 12 assume DD/MM/YYYY, otherwise default to MM/DD/YYYY.
            if first > 12:
                day = first
                month = second
            else:
                month = first
                day = second

            try:
                dt = datetime(year=year, month=month, day=day)
            except Exception as exc:
                raise GoogleSheetsWriterError(
                    f"Unsupported date format for spreadsheet payload: {raw_date}"
                ) from exc
            return dt.strftime("%Y-%m-%d")

    raise GoogleSheetsWriterError(
        f"Unsupported date format for spreadsheet payload: {raw_date}"
    )
