import json

from ollama import Client, ResponseError
from tenacity import retry, stop_after_attempt, wait_exponential

from app.modules.videos.domain.models import InferenceResult, VideoMetadata
from app.shared.config.settings import get_settings


class InferenceError(Exception):
    pass


class OllamaInferencer:
    def __init__(self):
        settings = get_settings()
        headers: dict[str, str] = {}
        if settings.ollama_api_key:
            headers["Authorization"] = f"Bearer {settings.ollama_api_key}"

        self.model = settings.ollama_model
        self.client = Client(
            host=settings.ollama_base_url.rstrip("/"),
            headers=headers if headers else None,
        )

    def _build_prompt(self, metadata: VideoMetadata) -> str:
        return f"""
Analyze the following video metadata and classify it strictly according to the rules below.

Title: {metadata.title}
Description: {metadata.description}
Tags: {", ".join(metadata.tags)}
Game Category: {metadata.game_category}

Categories (choose EXACTLY ONE):
- 日本語: Japanese studies (Kanji, Anki, grammar, exam preparation, Noken, N4, N3, N2, N1).
- Dev: Software engineering, automation, blockchain, backend, data, and new AI/tech tools.
- Maths: Pure mathematics or university-level academic content.
- Valorant: Tactical gameplay/content specifically about Valorant.
- Leisure: General gameplays, entertainment, and non-essential chill content.
- Talks: Video essays, podcasts, long-form commentary/background content.

Priorities (choose EXACTLY ONE):
- High: Hot content (new AI tools, urgent programming/data news, immediate workflow gains).
- Medium: Important long-term growth content (math, system design, data) without urgency.
- Low: General entertainment, gameplays, or casual leisure.
- Later: Background talks, long essays, watch-later backlog.

Disambiguation Rules:
- CRITICAL: If the content is heavily about software engineering, data science, data analytics, programming, or AI tools, ALWAYS classify it as 'Dev' BEFORE considering it as a podcast or talk.
- If game_category indicates Valorant or tags/title include 'valorant', 'vct', 'radiant', 'aim routine', strongly bias to Valorant.
- If game-related but non-Valorant and primarily entertainment, classify as Leisure.
- If it's a podcast, essay, commentary or interview AND NOT about Dev/Data/Tech topics, classify as Talks.
- Explicit academic mathematics is Maths.
- Japanese study workflows are 日本語.

Output strictly in JSON format matching this schema:
{{
  "category": "日本語 | Dev | Maths | Valorant | Leisure | Talks",
  "priority": "High | Medium | Low | Later",
  "rationale": "Short explanation for the classification",
  "confidence": <float between 0.0 and 1.0 representing your confidence in this classification>
}}

Do not include any markdown formatting, backticks, or extra text. Output ONLY valid JSON.
"""

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3)
    )
    def infer(self, metadata: VideoMetadata) -> InferenceResult:
        prompt = self._build_prompt(metadata)
        response_text = ""
        try:
            response = self.client.generate(
                model=self.model,
                prompt=prompt,
                format="json",
                stream=False,
            )

            response_text = (
                response.response
                if hasattr(response, "response")
                else response.get("response", "")
            )
            response_text = (
                response_text.replace("```json", "").replace("```", "").strip()
            )

            parsed_data = json.loads(response_text)
            return InferenceResult(**parsed_data)
        except ResponseError as exc:
            raise InferenceError(f"Ollama API request failed: {exc.error}") from exc
        except json.JSONDecodeError as exc:
            error_msg = f"Failed to parse model JSON output: {exc}"
            if response_text:
                error_msg += f"\nRaw output: {response_text}"
            raise InferenceError(error_msg) from exc
        except Exception as exc:
            raise InferenceError(f"Validation or Inference error: {exc}") from exc
