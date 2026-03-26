import json
import logging

from ollama import Client, ResponseError
from tenacity import retry, stop_after_attempt, wait_exponential

from app.modules.receipts.domain.models import (
    ReceiptExtractionInput,
    ReceiptExtractionResult,
)
from app.shared.config.settings import get_settings


class ReceiptsInferenceError(Exception):
    pass


class ReceiptOCRInferencer:
    def __init__(self):
        settings = get_settings()
        headers: dict[str, str] = {}
        if settings.ollama_api_key:
            headers["Authorization"] = f"Bearer {settings.ollama_api_key}"

        self.model = settings.ollama_model_receipts
        self.client = Client(
            host=settings.ollama_base_url.rstrip("/"),
            headers=headers if headers else None,
        )
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
      "price": 0.0
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
- Prefer numeric values only (no currency symbols).
- Exclude non-product lines such as totals, payment summaries, loyalty info, barcodes, cashier data.
- Do not return total; total is calculated downstream in spreadsheet formulas.
- Return JSON only.
"""

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
    )
    def extract(self, payload: ReceiptExtractionInput) -> ReceiptExtractionResult:
        prompt = self._build_prompt(payload)
        response_text = ""
        try:
            self.logger.info(
                "ollama generate started",
                extra={
                    "request_id": "-",
                    "method": "-",
                    "path": "/api/v1/receipts",
                    "source": "-",
                    "source_message_id": "-",
                    "source_user_id": "-",
                },
            )
            response = self.client.generate(
                model=self.model,
                prompt=prompt,
                images=[payload.image_base64],
                format="json",
                stream=False,
            )
            self.logger.info(
                "ollama generate completed",
                extra={
                    "request_id": "-",
                    "method": "-",
                    "path": "/api/v1/receipts",
                    "source": "-",
                    "source_message_id": "-",
                    "source_user_id": "-",
                },
            )
            response_text = (
                response.response
                if hasattr(response, "response")
                else response.get("response", "")
            )
            response_text = (
                response_text.replace("```json", "").replace("```", "").strip()
            )
            parsed = json.loads(response_text)
            self.logger.info(
                "ollama response parsed",
                extra={
                    "request_id": "-",
                    "method": "-",
                    "path": "/api/v1/receipts",
                    "source": "-",
                    "source_message_id": "-",
                    "source_user_id": "-",
                },
            )
            return ReceiptExtractionResult(**parsed)
        except ResponseError as exc:
            self.logger.exception("ollama response error")
            raise ReceiptsInferenceError(
                f"Ollama API request failed: {exc.error}"
            ) from exc
        except json.JSONDecodeError as exc:
            self.logger.exception("ollama json decode error")
            msg = f"Failed to parse receipt JSON output: {exc}"
            if response_text:
                msg += f"\nRaw output: {response_text}"
            raise ReceiptsInferenceError(msg) from exc
        except Exception as exc:
            self.logger.exception("receipts extraction unexpected error")
            raise ReceiptsInferenceError(f"Receipt extraction error: {exc}") from exc
