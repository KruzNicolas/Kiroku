from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class CategoryEnum(str, Enum):
    NIHONGO = "日本語"
    DEV = "Dev"
    MATHS = "Maths"
    VALORANT = "Valorant"
    LEISURE = "Leisure"
    TALKS = "Talks"


class PriorityEnum(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    LATER = "Later"


class VideoMetadata(BaseModel):
    url: str
    title: str = Field(default="Unknown Title")
    channel: str = Field(default="Unknown Channel")
    description: str = Field(default="")
    tags: list[str] = Field(default_factory=list)
    game_category: Optional[str] = None
    manual_priority: Optional[PriorityEnum] = Field(default=None)


class InferenceResult(BaseModel):
    category: CategoryEnum
    priority: PriorityEnum
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)


class FinalPayload(BaseModel):
    metadata: VideoMetadata
    inference: InferenceResult

    @property
    def final_priority(self) -> PriorityEnum:
        if self.metadata.manual_priority:
            return self.metadata.manual_priority
        return self.inference.priority
