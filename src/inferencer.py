import json
import requests
from tenacity import retry, wait_exponential, stop_after_attempt
from .models import VideoMetadata, InferenceResult, CategoryEnum, PriorityEnum
from .config import config


class InferenceError(Exception):
    pass


class OllamaInferencer:
    def __init__(self):
        self.base_url = config.OLLAMA_BASE_URL.rstrip("/")
        self.model = config.OLLAMA_MODEL

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

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }

        response_text = ""
        try:
            response = requests.post(
                f"{self.base_url}/api/generate", json=payload, timeout=30
            )
            response.raise_for_status()

            result_json = response.json()
            response_text = result_json.get("response", "")

            # Clean up response if the model accidentally included markdown
            response_text = (
                response_text.replace("```json", "").replace("```", "").strip()
            )

            parsed_data = json.loads(response_text)
            return InferenceResult(**parsed_data)

        except requests.exceptions.RequestException as e:
            raise InferenceError(f"Ollama API request failed: {str(e)}")
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse model JSON output: {str(e)}"
            if "response_text" in locals():
                error_msg += f"\nRaw output: {response_text}"
            raise InferenceError(error_msg)
        except Exception as e:
            raise InferenceError(f"Validation or Inference error: {str(e)}")
