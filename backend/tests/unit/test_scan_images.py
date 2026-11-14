"""Synthetic-image tests for bounded decoding and metadata-stripping re-encode."""

from io import BytesIO

import pytest
from PIL import Image

from backend.app.services.scans.images import ImageValidationError, sanitize_image


def _image_bytes(
    image_format: str = "PNG",
    size: tuple[int, int] = (32, 24),
    *,
    exif: Image.Exif | None = None,
) -> bytes:
    image = Image.new("RGB", size, color=(120, 180, 220))
    output = BytesIO()
    save_options = {"exif": exif} if exif is not None else {}
    image.save(output, format=image_format, **save_options)
    image.close()
    return output.getvalue()


def test_sanitizer_reencodes_to_metadata_free_jpeg_and_applies_exif_orientation() -> None:
    exif = Image.Exif()
    exif[274] = 6
    exif[305] = "Synthetic test marker"
    source = _image_bytes("JPEG", (32, 24), exif=exif)

    sanitized = sanitize_image(source, max_bytes=1024 * 1024, max_pixels=10_000)

    assert sanitized.content_type == "image/jpeg"
    assert (sanitized.width, sanitized.height) == (24, 32)
    with Image.open(BytesIO(sanitized.data)) as decoded:
        assert decoded.format == "JPEG"
        assert decoded.size == (24, 32)
        assert not decoded.getexif()
        assert "exif" not in decoded.info


def test_sanitizer_detects_actual_format_and_rejects_unsupported_raster() -> None:
    tiff_bytes = _image_bytes("TIFF")

    with pytest.raises(ImageValidationError) as error:
        sanitize_image(tiff_bytes, max_bytes=1024 * 1024, max_pixels=10_000)

    assert error.value.code == "unsupported_image"
    assert error.value.status_code == 415


def test_sanitizer_rejects_invalid_bytes_and_enforces_byte_and_pixel_limits() -> None:
    with pytest.raises(ImageValidationError) as invalid:
        sanitize_image(b"not an image", max_bytes=1024, max_pixels=10_000)
    assert invalid.value.code == "invalid_image"

    valid = _image_bytes(size=(11, 10))
    with pytest.raises(ImageValidationError) as byte_limit:
        sanitize_image(valid, max_bytes=len(valid) - 1, max_pixels=10_000)
    assert byte_limit.value.code == "image_too_large"

    with pytest.raises(ImageValidationError) as pixel_limit:
        sanitize_image(valid, max_bytes=1024 * 1024, max_pixels=100)
    assert pixel_limit.value.code == "image_too_large"
