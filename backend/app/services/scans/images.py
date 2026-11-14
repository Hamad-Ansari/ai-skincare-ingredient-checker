"""Bounded Pillow decoding and metadata-free JPEG normalization for scan uploads."""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError


class ImageValidationError(Exception):
    """Safe, client-displayable image intake failure."""

    def __init__(self, code: str, message: str, status_code: int) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


@dataclass(frozen=True)
class SanitizedImage:
    """Validated, orientation-corrected JPEG with metadata removed."""

    data: bytes
    width: int
    height: int
    content_type: str = "image/jpeg"


def _unsupported() -> ImageValidationError:
    return ImageValidationError(
        "unsupported_image",
        "Upload a single-frame JPEG, PNG, or WebP image.",
        415,
    )


def _too_large() -> ImageValidationError:
    return ImageValidationError(
        "image_too_large",
        "The image exceeds the configured byte or pixel limit.",
        413,
    )


def sanitize_image(data: bytes, *, max_bytes: int, max_pixels: int) -> SanitizedImage:
    """Decode actual image bytes, enforce resource limits, and re-encode without metadata.

    The caller-provided filename and MIME type are intentionally not accepted by this
    function; the format is determined by Pillow from the bytes themselves.
    """
    if not data:
        raise ImageValidationError("invalid_image", "The uploaded file is empty.", 422)
    if len(data) > max_bytes:
        raise _too_large()

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as probe:
                if probe.format not in {"JPEG", "PNG", "WEBP"}:
                    raise _unsupported()
                if getattr(probe, "n_frames", 1) != 1:
                    raise _unsupported()
                width, height = probe.size
                if width <= 0 or height <= 0 or width * height > max_pixels:
                    raise _too_large()
                probe.verify()

            with Image.open(BytesIO(data)) as decoded:
                if decoded.format not in {"JPEG", "PNG", "WEBP"}:
                    raise _unsupported()
                if getattr(decoded, "n_frames", 1) != 1:
                    raise _unsupported()
                decoded.load()
                oriented = ImageOps.exif_transpose(decoded)
                try:
                    width, height = oriented.size
                    if width <= 0 or height <= 0 or width * height > max_pixels:
                        raise _too_large()

                    if "A" in oriented.getbands() or "transparency" in oriented.info:
                        rgba = oriented.convert("RGBA")
                        clean = Image.new("RGB", rgba.size, (255, 255, 255))
                        clean.paste(rgba, mask=rgba.getchannel("A"))
                        rgba.close()
                    else:
                        clean = oriented.convert("RGB")

                    try:
                        output = BytesIO()
                        clean.save(
                            output,
                            format="JPEG",
                            quality=88,
                            optimize=True,
                            progressive=False,
                        )
                        encoded = output.getvalue()
                    finally:
                        clean.close()
                finally:
                    if oriented is not decoded:
                        oriented.close()

    except ImageValidationError:
        raise
    except Image.DecompressionBombError as exc:
        raise _too_large() from exc
    except Image.DecompressionBombWarning as exc:
        raise _too_large() from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, EOFError) as exc:
        raise ImageValidationError(
            "invalid_image", "The uploaded file is not a valid supported image.", 422
        ) from exc

    if not encoded:
        raise ImageValidationError("invalid_image", "The image could not be re-encoded.", 422)
    if len(encoded) > max_bytes:
        raise _too_large()
    return SanitizedImage(data=encoded, width=width, height=height)
