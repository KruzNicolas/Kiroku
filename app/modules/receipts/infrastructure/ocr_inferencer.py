import json
import logging

from tenacity import retry, stop_after_attempt, wait_exponential

from app.modules.receipts.domain.models import (
    ReceiptExtractionInput,
    ReceiptExtractionResult,
)
from app.shared.infrastructure.ai_client import AIClientError
from app.shared.infrastructure.ai_factory import build_ai_client


class ReceiptsInferenceError(Exception):
    pass


class ReceiptInferencer:
    def __init__(self):
        self.client = build_ai_client("receipts")
        self.logger = logging.getLogger("kiroku.receipts.ocr")

    def _build_prompt(self, payload: ReceiptExtractionInput) -> str:
        return f"""
You will receive an image of a purchase receipt encoded in base64.

Optional store hint: {payload.store_hint or "N/A"}

Extract receipt line items and return ONLY valid JSON with this exact schema:
{{
  "items": [
    {{
      "date": "MM/DD/YYYY",
      "category": "Groceries|Pharmacy|Others",
      "store": "string",
      "product": "string",
      "quantity": 1,
      "price": 2950
    }}
  ]
}}

Rules:
- Do not include batch_id.
- Infer store from receipt if store_hint is not provided.
- If quantity is missing, default to 1.
- quantity can be decimal for weighted products (e.g., 0.335 KG, 0.714 KG).
- price MUST be the unit price for one item/unit (never line total, subtotal, or receipt total).
- If only line total is visible and quantity > 0, compute unit price as line_total / quantity and return that unit value.
- Currency is COP (Colombian Peso).
- Return price in COP whole units (no decimal cents), e.g. 2.950 -> 2950.
- price must be an INTEGER, not decimal. The example shows 2950, not 2950.0.
- Prefer numeric values only (no currency symbols).
- Exclude non-product lines such as totals, payment summaries, loyalty info, barcodes, cashier data.
- Do not return total; total is calculated downstream in spreadsheet formulas.
- Return JSON only.
"""

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
    )
    def extract(
        self, payload: ReceiptExtractionInput, source: str = "unknown"
    ) -> ReceiptExtractionResult:
        prompt = self._build_prompt(payload)
        response_text = ""
        try:
            self.logger.info(
                "ai generate started",
                extra={
                    "request_id": "-",
                    "method": "-",
                    "path": "/api/v1/receipts",
                    "source": source,
                    "source_message_id": "-",
                    "source_user_id": "-",
                },
            )
            response_text = self.client.generate_json(
                prompt=prompt,
                images=[payload.image_base64],
            )
            self.logger.info(
                "ai generate completed",
                extra={
                    "request_id": "-",
                    "method": "-",
                    "path": "/api/v1/receipts",
                    "source": source,
                    "source_message_id": "-",
                    "source_user_id": "-",
                },
            )
            response_text = (
                response_text.replace("```json", "").replace("```", "").strip()
            )
            parsed = json.loads(response_text)
            self.logger.info(
                "ai response parsed",
                extra={
                    "request_id": "-",
                    "method": "-",
                    "path": "/api/v1/receipts",
                    "source": source,
                    "source_message_id": "-",
                    "source_user_id": "-",
                },
            )
            return ReceiptExtractionResult(**parsed)
        except AIClientError as exc:
            self.logger.exception("ai response error")
            raise ReceiptsInferenceError(
                f"AI API request failed: {exc}"
            ) from exc
        except json.JSONDecodeError as exc:
            self.logger.exception("ai json decode error")
            msg = f"Failed to parse receipt JSON output: {exc}"
            if response_text:
                msg += f"\nRaw output: {response_text}"
            raise ReceiptsInferenceError(msg) from exc
        except Exception as exc:
            self.logger.exception("receipts extraction unexpected error")
            raise ReceiptsInferenceError(f"Receipt extraction error: {exc}") from exc
