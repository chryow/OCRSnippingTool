"""Tests for multilingual script and language detection."""

from __future__ import annotations

import pytest

from ocr_snip.language import detect_languages, detect_scripts


@pytest.mark.parametrize(
    ("text", "expected_code"),
    [
        ("The quick brown fox jumps over the lazy dog.", "en"),
        ("Bonjour tout le monde, comment allez-vous aujourd'hui?", "fr"),
        ("Hola amigos, bienvenidos a nuestra nueva aplicación.", "es"),
        ("こんにちは、世界！日本語のテキスト認識テストです。", "ja"),
        ("你好世界，这是一个多语言文字识别工具。", "zh"),
        ("안녕하세요, 한국어 텍스트 추출 테스트입니다.", "ko"),
        ("Привет мир, это тест распознавания русского текста.", "ru"),
        ("مرحبا بالعالم، هذا اختبار لاستخراج النص العربي.", "ar"),
        ("नमस्ते दुनिया, यह हिंदी पाठ पहचान परीक्षण है।", "hi"),
        ("สวัสดีชาวโลก นี่คือการทดสอบภาษาไทย", "th"),
        ("Γεια σου κόσμε, αυτό είναι ένα τεστ.", "el"),
        ("שלום עולם", "he"),
    ],
)
def test_detect_diverse_world_languages(text: str, expected_code: str) -> None:
    langs = detect_languages(text)
    assert langs, f"Expected a language for: {text}"
    assert langs[0].code.startswith(expected_code), (
        f"Expected code starting with {expected_code!r}, got {langs[0]}"
    )


def test_detect_mixed_scripts() -> None:
    text = "Welcome to Tokyo! 東京へようこそ、楽しい旅を！"
    langs = detect_languages(text)
    codes = {lang.code for lang in langs}
    assert "ja" in codes
    assert any(c.startswith("en") or lang.script == "Latin" for c, lang in zip(codes, langs))


def test_short_snippet_script_fallback() -> None:
    langs = detect_languages("안녕")
    assert langs and langs[0].code == "ko"

    langs_th = detect_languages("ไทย")
    assert langs_th and langs_th[0].code == "th"


def test_empty_or_numeric_only() -> None:
    assert detect_languages("") == []
    assert detect_languages("   12345 !@# ") == []
    assert detect_scripts("2026-11-26") == {}
