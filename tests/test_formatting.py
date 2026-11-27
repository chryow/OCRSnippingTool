"""Tests for smart multilingual paragraph unwrapping."""

from __future__ import annotations

from ocr_snip.formatting import unwrap_paragraphs


def test_unwrap_english_pdf_paragraphs_and_hyphens() -> None:
    raw = (
        "This is a multi-\n"
        "lingual OCR tool that\n"
        "wraps across lines.\n"
        "\n"
        "Second paragraph continues\n"
        "smoothly here."
    )
    expected = (
        "This is a multilingual OCR tool that wraps across lines.\n\n"
        "Second paragraph continues smoothly here."
    )
    assert unwrap_paragraphs(raw) == expected


def test_unwrap_preserves_bullet_and_numbered_lists() -> None:
    raw = "Items:\n- First item\n- Second item\n1. Step one\n2. Step two"
    assert unwrap_paragraphs(raw) == "Items:\n- First item\n- Second item\n1. Step one\n2. Step two"


def test_unwrap_cjk_without_injecting_spaces() -> None:
    raw = "日本語のテキストを\n自然に結合します。"
    assert unwrap_paragraphs(raw) == "日本語のテキストを自然に結合します。"
