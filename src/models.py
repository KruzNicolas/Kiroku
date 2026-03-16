from enum import Enum
from typing import List, Optional
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
    description: str = Field(default="")
    tags: List[str] = Field(default_factory=list)
    game_category: Optional[str] = None
    force_later: bool = Field(
        default=False,
        description="Flag indicating if the manual 'later' override was present",
    )


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
        if self.metadata.force_later:
            return PriorityEnum.LATER
        return self.inference.priority
