from dataclasses import dataclass
from typing import Any, Literal


NotionFilterPropertyType = Literal["url", "rich_text", "title", "number", "select"]


@dataclass(frozen=True)
class NotionUpsertDescriptor:
    property_name: str
    property_type: NotionFilterPropertyType
    equals: str | int | float


@dataclass(frozen=True)
class NotionSaveCommand:
    database_id: str
    properties: dict[str, Any]
    children: list[dict[str, Any]] | None = None
    upsert: NotionUpsertDescriptor | None = None
