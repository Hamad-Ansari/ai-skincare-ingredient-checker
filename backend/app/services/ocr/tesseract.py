"""Replaceable local Tesseract CLI adapter with TSV confidence parsing."""

from __future__ import annotations

import csv
import io
import math
import subprocess
from dataclasses import dataclass
from typing import Protocol


class OcrUnavailableError(Exception):
    """Raised when the configured local OCR executable cannot be started."""


class OcrTimeoutError(Exception):
    """Raised when the OCR process exceeds its configured wall-clock limit."""


class OcrProcessingError(Exception):
    """Raised for a failed OCR invocation or malformed engine output."""


@dataclass(frozen=True)
class OcrBoundingBox:
    """Word rectangle in pixels, as reported by Tesseract TSV."""

    left: int
    top: int
    width: int
    height: int


@dataclass(frozen=True)
class OcrToken:
    """One unconfirmed OCR word with optional engine confidence and geometry."""

    text: str
    confidence: float | None
    box: OcrBoundingBox | None


@dataclass(frozen=True)
class OcrResult:
    """Text plus per-word metadata from a local OCR engine."""

    text: str
    tokens: tuple[OcrToken, ...]
    confidence: float | None
    engine: str
    engine_version: str | None = None


class OcrEngine(Protocol):
    """Minimal interface that permits a different on-device OCR adapter later."""

    def extract(self, image_bytes: bytes) -> OcrResult:
        """Extract text and available OCR metadata from an already sanitized image."""


def _parse_nonnegative_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed >= 0 else None


def parse_tesseract_tsv(tsv_text: str) -> OcrResult:
    """Parse Tesseract's TSV output without inventing missing confidences."""
    reader = csv.DictReader(io.StringIO(tsv_text), delimiter="\t")
    required = {"level", "text", "conf", "page_num", "block_num", "par_num", "line_num"}
    if reader.fieldnames is None or not required.issubset(reader.fieldnames):
        raise OcrProcessingError("Tesseract returned malformed TSV output")

    tokens: list[OcrToken] = []
    lines: list[list[str]] = []
    previous_line: tuple[str | None, ...] | None = None
    confidences: list[float] = []

    try:
        for row in reader:
            if row.get("level") != "5":
                continue
            word = (row.get("text") or "").strip()
            if not word:
                continue

            confidence: float | None
            try:
                raw_confidence = float(row.get("conf", ""))
                confidence = (
                    raw_confidence
                    if math.isfinite(raw_confidence) and 0 <= raw_confidence <= 100
                    else None
                )
            except (TypeError, ValueError):
                confidence = None
            if confidence is not None:
                confidences.append(confidence)

            left = _parse_nonnegative_int(row.get("left"))
            top = _parse_nonnegative_int(row.get("top"))
            width = _parse_nonnegative_int(row.get("width"))
            height = _parse_nonnegative_int(row.get("height"))
            box = (
                OcrBoundingBox(left=left, top=top, width=width, height=height)
                if None not in (left, top, width, height)
                else None
            )
            tokens.append(OcrToken(text=word, confidence=confidence, box=box))

            line_id = tuple(
                row.get(field) for field in ("page_num", "block_num", "par_num", "line_num")
            )
            if line_id != previous_line:
                lines.append([])
                previous_line = line_id
            lines[-1].append(word)
    except csv.Error as exc:
        raise OcrProcessingError("Tesseract returned malformed TSV output") from exc

    text = "\n".join(" ".join(words) for words in lines)
    confidence = sum(confidences) / len(confidences) if confidences else None
    return OcrResult(
        text=text,
        tokens=tuple(tokens),
        confidence=confidence,
        engine="tesseract",
    )


class TesseractOcrEngine:
    """Run Tesseract against stdin, with no shell, temporary input path, or cloud call."""

    def __init__(self, command: str, language: str, timeout_seconds: int) -> None:
        self.command = command
        self.language = language
        self.timeout_seconds = timeout_seconds

    def extract(self, image_bytes: bytes) -> OcrResult:
        if not image_bytes:
            raise OcrProcessingError("No image bytes were supplied to the OCR engine")

        command = [
            self.command,
            "stdin",
            "stdout",
            "-l",
            self.language,
            "--psm",
            "6",
            "tsv",
        ]
        try:
            result = subprocess.run(
                command,
                input=image_bytes,
                capture_output=True,
                check=False,
                timeout=self.timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise OcrUnavailableError("Configured Tesseract executable is unavailable") from exc
        except subprocess.TimeoutExpired as exc:
            raise OcrTimeoutError("Tesseract exceeded the configured time limit") from exc
        except OSError as exc:
            raise OcrProcessingError("Tesseract could not process the image") from exc

        if result.returncode != 0:
            raise OcrProcessingError("Tesseract returned a non-zero exit status")
        try:
            tsv_text = result.stdout.decode("utf-8", errors="replace")
        except AttributeError as exc:
            raise OcrProcessingError("Tesseract returned an invalid output stream") from exc
        return parse_tesseract_tsv(tsv_text)
