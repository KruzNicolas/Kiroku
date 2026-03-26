from pydantic import BaseModel, Field


class JapaneseStudyAssetInput(BaseModel):
    image_bytes: bytes = Field(min_length=1)
    image_content_type: str = Field(min_length=1)
    notes: str | None = None
