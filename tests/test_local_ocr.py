"""End-to-end offline RapidOCR tests using synthetic PIL images and CLI mode."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ocr_snip.__main__ import main
from ocr_snip.ocr.local_rapidocr import LocalRapidOCREngine


def _render_text_image(
    lines: list[str],
    *,
    bg: str = "white",
    fg: str = "black",
    font_size: int = 34,
    padding: int = 24,
) -> Image.Image:
    font = ImageFont.load_default(size=font_size)
    line_height = font_size + 14
    width = max(len(line) for line in lines) * int(font_size * 0.68) + padding * 2
    height = len(lines) * line_height + padding * 2
    img = Image.new("RGB", (max(width, 200), max(height, 80)), bg)
    draw = ImageDraw.Draw(img)
    for idx, line in enumerate(lines):
        draw.text((padding, padding + idx * line_height), line, fill=fg, font=font)
    return img


def test_local_rapidocr_extracts_multiline_english() -> None:
    img = _render_text_image(["Hello OCR Snipping Tool", "Multilingual AI Extraction"])
    engine = LocalRapidOCREngine(default_script="auto")
    res = engine.recognize(img)

    assert res.ok
    assert "Hello OCR Snipping Tool" in res.text
    assert "Multilingual AI Extraction" in res.text
    assert res.confidence > 0.85
    assert res.languages and res.languages[0].code == "en"


def test_local_rapidocr_handles_dark_mode_snip() -> None:
    img = _render_text_image(["Dark Mode Screen Text"], bg="#11131a", fg="#f8fafc", padding=8)
    engine = LocalRapidOCREngine(default_script="auto")
    res = engine.recognize(img)

    assert res.ok
    assert "Dark Mode Screen Text" in res.text


def test_cli_image_json_mode(tmp_path: Path, capsys) -> None:
    img_path = tmp_path / "sample.png"
    _render_text_image(["Quick Brown Fox 2026"]).save(img_path)

    exit_code = main(["--image", str(img_path), "--mode", "local", "--json"])
    assert exit_code == 0

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["ok"] is True
    assert "Quick Brown Fox 2026" in payload["text"]
    assert payload["languages"][0]["code"] == "en"
