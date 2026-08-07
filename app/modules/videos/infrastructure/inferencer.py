import json

from tenacity import retry, stop_after_attempt, wait_exponential

from app.modules.videos.domain.models import InferenceResult, VideoMetadata
from app.shared.infrastructure.ai_client import AIClientError
from app.shared.infrastructure.ai_factory import build_ai_client


class InferenceError(Exception):
    pass


class VideoInferencer:
    def __init__(self):
        self.client = build_ai_client("videos")

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

Examples (from real classifications):
- Title: "La IA es mi nuevo empleado | Claude Code", Channel: "Nate Gentile", Tags: ["AI", "programming", "Claude"] → {{"category": "Dev", "priority": "High", "rationale": "New AI tool demonstration with immediate workflow impact", "confidence": 0.95}}
- Title: "SER JUGADOR PROFESIONAL DE VALORANT ES HORRIBLE", Channel: "Nore", Tags: ["Valorant", "esports", "gaming"] → {{"category": "Valorant", "priority": "Low", "rationale": "Valorant entertainment content, not tactical/educational", "confidence": 0.92}}
- Title: "Stop Studying for JLPT N1 (Learn These 100 Words Instead)", Channel: "Kei Fujikawa", Tags: ["Japanese", "JLPT", "language learning", "N1"] → {{"category": "日本語", "priority": "Medium", "rationale": "Japanese study workflow and JLPT preparation", "confidence": 0.94}}
- Title: "Así es un pueblo poco conocido en Japón", Channel: "Chai Japon", Tags: ["Japan", "travel", "culture"] → {{"category": "Talks", "priority": "Later", "rationale": "Cultural commentary video essay, background content", "confidence": 0.88}}

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
            response_text = self.client.generate_json(prompt=prompt)
            response_text = (
                response_text.replace("```json", "").replace("```", "").strip()
            )

            parsed_data = json.loads(response_text)
            return InferenceResult(**parsed_data)
        except AIClientError as exc:
            raise InferenceError(f"AI API request failed: {exc}") from exc
        except json.JSONDecodeError as exc:
            error_msg = f"Failed to parse model JSON output: {exc}"
            if response_text:
                error_msg += f"\nRaw output: {response_text}"
            raise InferenceError(error_msg) from exc
        except Exception as exc:
            raise InferenceError(f"Validation or Inference error: {exc}") from exc
