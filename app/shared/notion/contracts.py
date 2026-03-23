from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NotionSaveCommand:
    database_id: str
    unique_url: str
    properties: dict[str, Any]
    children: list[dict[str, Any]] | None = None
