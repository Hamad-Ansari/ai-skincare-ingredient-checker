"""Parser and adapter tests that never require a live Tesseract executable."""

import subprocess
from types import SimpleNamespace
from uuid import uuid4

import pytest

from backend.app.services.ocr.tesseract import (
    OcrProcessingError,
    OcrUnavailableError,
    TesseractOcrEngine,
    parse_tesseract_tsv,
)

TSV = (
    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
    "5\t1\t1\t1\t1\t1\t12\t8\t20\t9\t95.0\tAqua\n"
    "5\t1\t1\t1\t1\t2\t35\t8\t26\t9\t-1\tWater\n"
    "5\t1\t1\t1\t2\t1\t12\t30\t34\t10\t80.0\tGlycerin\n"
)


def test_tesseract_tsv_parser_keeps_lines_boxes_and_available_confidence() -> None:
    result = parse_tesseract_tsv(TSV)

    assert result.text == "Aqua Water\nGlycerin"
    assert result.engine == "tesseract"
    assert result.confidence == 87.5
    assert [token.text for token in result.tokens] == ["Aqua", "Water", "Glycerin"]
    assert result.tokens[0].confidence == 95.0
    assert result.tokens[1].confidence is None
    assert result.tokens[0].box is not None
    assert result.tokens[0].box.left == 12
    assert result.tokens[2].box is not None
    assert result.tokens[2].box.top == 30


def test_tesseract_adapter_invokes_local_cli_on_stdin_without_shell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        captured["command"] = command
        captured.update(kwargs)
        return SimpleNamespace(returncode=0, stdout=TSV.encode(), stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    adapter = TesseractOcrEngine("/local/tesseract", "eng", 12)
    result = adapter.extract(b"synthetic-sanitized-image")

    assert captured["command"] == [
        "/local/tesseract",
        "stdin",
        "stdout",
        "-l",
        "eng",
        "--psm",
        "6",
        "tsv",
    ]
    assert captured["input"] == b"synthetic-sanitized-image"
    assert captured["capture_output"] is True
    assert captured["timeout"] == 12
    assert "shell" not in captured
    assert result.text == "Aqua Water\nGlycerin"


def test_missing_tesseract_is_explicit_and_testable() -> None:
    missing_command = f"clarity-test-no-tesseract-{uuid4().hex}"
    adapter = TesseractOcrEngine(missing_command, "eng", 1)

    with pytest.raises(OcrUnavailableError):
        adapter.extract(b"synthetic-sanitized-image")


def test_malformed_tesseract_output_is_not_treated_as_ocr_text() -> None:
    with pytest.raises(OcrProcessingError):
        parse_tesseract_tsv("not a TSV table")
