"""API-owned, in-memory screenshot bytes for one demo-process lifetime."""
from __future__ import annotations

import base64
import binascii
import hashlib


_MAX_IMAGE_BYTES = 10 * 1024 * 1024
_IMAGE_MAGIC = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff", b"RIFF")


class SessionImageStore:
    def __init__(self) -> None:
        self._images: dict[str, bytes] = {}

    def add_b64(self, payload: str) -> str:
        try:
            image = base64.b64decode(payload, validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError("image_b64 must be valid Base64") from error
        if not image or len(image) > _MAX_IMAGE_BYTES:
            raise ValueError("image_b64 must contain 1 byte to 10 MiB")
        if not image.startswith(_IMAGE_MAGIC):
            raise ValueError("image_b64 must be PNG, JPEG, or WebP")
        reference = f"image:sha256:{hashlib.sha256(image).hexdigest()}"
        self._images[reference] = image
        return reference

    def resolve(self, reference: str) -> bytes:
        try:
            return self._images[reference]
        except KeyError as error:
            raise KeyError(f"unknown session image: {reference}") from error
