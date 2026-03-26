import re

from pydantic import BaseModel, Field, field_validator


class ReceiptExtractionInput(BaseModel):
    image_base64: str = Field(min_length=1)
    store_hint: str | None = None


class ReceiptItem(BaseModel):
    date: str
    category: str
    store: str
    product: str
    quantity: float
    price: float

    @field_validator("quantity", mode="before")
    @classmethod
    def normalize_quantity(cls, value):
        parsed = None
        if isinstance(value, (int, float)):
            parsed = float(value)

        elif isinstance(value, str):
            parsed = _parse_quantity(value)

        if parsed is None:
            raise ValueError("Invalid numeric field")

        if parsed <= 0:
            return 1.0

        return float(parsed)

    @field_validator("price", mode="before")
    @classmethod
    def normalize_price(cls, value):
        parsed = None
        if isinstance(value, (int, float)):
            parsed = float(value)

        elif isinstance(value, str):
            parsed = _parse_money(value)

        if parsed is None:
            raise ValueError("Invalid numeric field")

        return _normalize_cop_price(parsed)


class ReceiptExtractionResult(BaseModel):
    items: list[ReceiptItem]


def _sanitize_numeric(raw: str) -> str:
    s = raw.strip()
    if not s:
        raise ValueError("Empty numeric value")

    # Keep only digits, sign, comma and dot. Remove currency symbols/letters.
    s = re.sub(r"[^0-9,.-]", "", s)
    if not s:
        raise ValueError("No numeric content")

    return s


def _parse_quantity(raw: str) -> float:
    s = _sanitize_numeric(raw)

    has_dot = "." in s
    has_comma = "," in s

    if has_dot and has_comma:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif has_comma:
        s = s.replace(",", ".")

    return float(s)


def _parse_money(raw: str) -> float:
    s = _sanitize_numeric(raw)

    has_dot = "." in s
    has_comma = "," in s

    if has_dot and has_comma:
        # Use the rightmost separator as decimal marker.
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif has_comma:
        parts = s.split(",")
        right = parts[-1]
        if len(parts) == 2 and len(right) <= 2:
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    elif has_dot:
        parts = s.split(".")
        right = parts[-1]
        if len(parts) == 2 and len(right) <= 2:
            pass
        else:
            s = s.replace(".", "")

    return float(s)


def _normalize_cop_price(value: float) -> float:
    if value < 0:
        raise ValueError("price must be non-negative")

    # For COP receipts we expect whole currency units.
    # If model returns decimal values like 2.95 for 2.950, scale to thousands.
    if not float(value).is_integer():
        if value < 1000:
            return float(round(value * 1000))
        return float(round(value))

    return float(value)
