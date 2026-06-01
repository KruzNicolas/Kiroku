ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png"}


def validate_image_type(content_type: str, context: str = "image") -> None:
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError(
            f"Unsupported {context} type. Use image/jpeg or image/png (convert HEIC/HEIF before sending)."
        )
