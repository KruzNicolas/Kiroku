import logging
from typing import Any

from openai import OpenAI, APIError
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger("kiroku.ai_client")


class AIClientError(Exception):
    """Raised when the AI client encounters an error during generation."""
    pass


class AIClient:
    def __init__(self, api_key: str, base_url: str, model: str):
        self.model = model
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
        )

    def _build_messages(self, prompt: str, images: list[str] | None = None) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        if images:
            for image_b64 in images:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_b64}",
                    },
                })
        return [{"role": "user", "content": content}]

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def generate_json(self, prompt: str, images: list[str] | None = None) -> str:
        messages = self._build_messages(prompt, images)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            if content is None:
                raise AIClientError("AI response content is None")
            return content.strip()
        except APIError as exc:
            logger.exception("AI API error")
            raise AIClientError(f"AI API request failed: {exc}") from exc
        except Exception as exc:
            logger.exception("AI client unexpected error")
            raise AIClientError(f"AI client error: {exc}") from exc
