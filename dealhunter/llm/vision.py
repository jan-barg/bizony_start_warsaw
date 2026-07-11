"""Resolver boundary for API-owned image bytes."""
from __future__ import annotations

import base64
import hashlib
import re
from typing import Protocol


_IMAGE_REFERENCE = re.compile(r"^image:sha256:([0-9a-f]{64})$")


class ImageResolver(Protocol):
    def resolve(self, reference: str) -> bytes:
        """Return API-owned validated bytes for a digest reference."""
        ...


class ImageResolutionError(ValueError):
    pass


def image_data_url(reference: str, resolver: ImageResolver | None) -> str:
    match = _IMAGE_REFERENCE.fullmatch(reference)
    if match is None:
        raise ImageResolutionError("malformed image reference")
    if resolver is None:
        raise ImageResolutionError("image resolver is required")
    try:
        data = resolver.resolve(reference)
    except (KeyError, LookupError) as error:
        raise ImageResolutionError("image reference not found") from error
    if not isinstance(data, bytes) or not data:
        raise ImageResolutionError("image resolver returned no bytes")
    if hashlib.sha256(data).hexdigest() != match.group(1):
        raise ImageResolutionError("image digest mismatch")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        mime_type = "image/png"
    elif data.startswith(b"\xff\xd8\xff"):
        mime_type = "image/jpeg"
    elif data.startswith((b"GIF87a", b"GIF89a")):
        mime_type = "image/gif"
    else:
        raise ImageResolutionError("unsupported image format")
    return f"data:{mime_type};base64,{base64.b64encode(data).decode()}"
