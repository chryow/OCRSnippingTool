"""Unit tests for built-in 1-click Translator (Free Web + AI providers + fallback)."""

from __future__ import annotations

import httpx

from ocr_snip.config import AppConfig
from ocr_snip.translate import Translator


def test_translate_google_free_mocked(monkeypatch) -> None:
    def fake_get(self, url, **kwargs):
        assert "translate.googleapis.com" in url
        assert kwargs["params"]["tl"] == "en"
        assert "Mozilla/5.0" in kwargs["headers"]["User-Agent"]
        return httpx.Response(
            200,
            json=[[["Hello world", "こんにちは世界", None, None, 10]], None, "ja"],
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    cfg = AppConfig(translation_provider="google_free", translate_target_lang="en")
    res = Translator(cfg).translate("こんにちは世界")

    assert res.ok
    assert res.translated_text == "Hello world"
    assert res.source_language == "Japanese"
    assert res.target_language == "English"
    assert res.provider_name == "Free Translate"


def test_translate_free_falls_back_on_429_to_google_dict(monkeypatch) -> None:
    calls: list[str] = []

    def fake_get(self, url, **kwargs):
        calls.append(url)
        if "translate.googleapis.com" in url:
            return httpx.Response(429, request=httpx.Request("GET", url))
        assert "clients5.google.com" in url
        return httpx.Response(
            200,
            json=[["Apa artinya ini?", "en"]],
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    cfg = AppConfig(translation_provider="google_free", translate_target_lang="id")
    res = Translator(cfg).translate("What does this mean?")

    assert res.ok
    assert res.translated_text == "Apa artinya ini?"
    assert res.source_language == "English"
    assert res.target_language == "Indonesian"
    assert len(calls) == 2


def test_translate_free_falls_back_on_429_to_mymemory(monkeypatch) -> None:
    calls: list[str] = []

    def fake_get(self, url, **kwargs):
        calls.append(url)
        if "translate.googleapis.com" in url or "clients5.google.com" in url:
            return httpx.Response(429, request=httpx.Request("GET", url))
        assert "api.mymemory.translated.net" in url
        assert kwargs["params"]["langpair"] == "en|id"
        return httpx.Response(
            200,
            json={
                "responseStatus": 200,
                "responseData": {"translatedText": "Apa maksudnya ini?"},
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    cfg = AppConfig(translation_provider="google_free", translate_target_lang="id")
    res = Translator(cfg).translate("What does this mean?")

    assert res.ok
    assert res.translated_text == "Apa maksudnya ini?"
    assert "MyMemory" in res.provider_name
    assert len(calls) == 3


def test_translate_auto_prefers_configured_ai(monkeypatch) -> None:
    def fake_post(self, url, **kwargs):
        assert "gemini-3.8-flash:generateContent" in url
        assert kwargs["headers"]["x-goog-api-key"] == "gem-key"
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "Selamat pagi dunia"}]}}
                ]
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    cfg = AppConfig(
        translation_provider="auto",
        ai_provider="gemini",
        gemini_api_key="gem-key",
        translate_target_lang="id",
    )
    res = Translator(cfg).translate("Good morning world")

    assert res.ok
    assert res.translated_text == "Selamat pagi dunia"
    assert res.target_language == "Indonesian"
    assert "Gemini" in res.provider_name


def test_translate_auto_falls_back_to_free_if_ai_fails(monkeypatch) -> None:
    def fake_post(self, url, **kwargs):
        return httpx.Response(
            500,
            json={"error": {"message": "Temporary outage"}},
            request=httpx.Request("POST", url),
        )

    def fake_get(self, url, **kwargs):
        return httpx.Response(
            200,
            json=[[["Bonjour le monde", "Hello world", None, None, 10]], None, "en"],
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    cfg = AppConfig(
        translation_provider="auto",
        ai_provider="gemini",
        gemini_api_key="gem-key",
    )
    res = Translator(cfg).translate("Hello world", target_lang="fr")

    assert res.ok
    assert res.translated_text == "Bonjour le monde"
    assert res.provider_name == "Free Translate"


def test_translate_empty_text_returns_error() -> None:
    res = Translator(AppConfig()).translate("   ")
    assert not res.ok
    assert res.error is not None


def test_translate_explicit_source_lang_google_free(monkeypatch) -> None:
    captured_params: dict[str, str] = {}

    def fake_get(self, url, **kwargs):
        captured_params.update(kwargs["params"])
        return httpx.Response(
            200,
            json=[[["Good morning", "Selamat pagi", None, None, 10]], None, "ms"],
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    cfg = AppConfig(
        translation_provider="google_free",
        translate_source_lang="id",
        translate_target_lang="en",
    )
    res = Translator(cfg).translate("Selamat pagi")

    assert res.ok
    assert captured_params["sl"] == "id"
    assert captured_params["tl"] == "en"
    assert res.source_language == "Indonesian"
    assert res.target_language == "English"


def test_translate_explicit_source_lang_mymemory_bypasses_autodetect(monkeypatch) -> None:
    def fail_detect(_text: str):
        raise AssertionError("detect_languages should not be called when source_lang is explicit")

    monkeypatch.setattr("ocr_snip.translate.detect_languages", fail_detect)

    def fake_get(self, url, **kwargs):
        if "translate.googleapis.com" in url or "clients5.google.com" in url:
            assert kwargs["params"]["sl"] == "ms"
            return httpx.Response(429, request=httpx.Request("GET", url))
        assert "api.mymemory.translated.net" in url
        assert kwargs["params"]["langpair"] == "ms|en"
        return httpx.Response(
            200,
            json={
                "responseStatus": 200,
                "responseData": {"translatedText": "Thank you"},
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.Client, "get", fake_get)
    cfg = AppConfig(translation_provider="google_free", translate_target_lang="en")
    res = Translator(cfg).translate("Terima kasih", source_lang="ms")

    assert res.ok
    assert res.translated_text == "Thank you"
    assert res.source_language == "Malay"


def test_translate_explicit_source_lang_ai_prompt(monkeypatch) -> None:
    captured_body: dict = {}

    def fake_post(self, url, **kwargs):
        captured_body.update(kwargs["json"])
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "Hello"}]}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    cfg = AppConfig(
        translation_provider="ai",
        ai_provider="gemini",
        gemini_api_key="gem-key",
        translate_source_lang="id",
        translate_target_lang="en",
    )
    res = Translator(cfg).translate("Halo")

    assert res.ok
    assert res.source_language == "Indonesian"
    assert res.target_language == "English"
    prompt_text = captured_body["systemInstruction"]["parts"][0]["text"]
    assert "from Indonesian into English" in prompt_text

