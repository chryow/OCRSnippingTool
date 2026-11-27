"""Tests for VisionAIEngine response parsing and provider adapters."""

from __future__ import annotations

import httpx
from PIL import Image

from ocr_snip.config import AppConfig
from ocr_snip.ocr.vision_ai import VisionAIEngine, parse_vision_ai_response


def test_parse_clean_json() -> None:
    raw = '{"text": "Hello\\nWorld", "languages": [{"code": "en", "name": "English"}]}'
    text, langs = parse_vision_ai_response(raw)
    assert text == "Hello\nWorld"
    assert len(langs) == 1
    assert langs[0].code == "en"
    assert langs[0].name == "English"


def test_parse_markdown_fenced_json() -> None:
    raw = '```json\n{"text": "こんにちは", "languages": [{"code": "ja", "name": "Japanese"}]}\n```'
    text, langs = parse_vision_ai_response(raw)
    assert text == "こんにちは"
    assert langs[0].code == "ja"


def test_parse_plain_text_fallback() -> None:
    text, langs = parse_vision_ai_response("안녕하세요 반갑습니다")
    assert text == "안녕하세요 반갑습니다"
    assert langs and langs[0].code == "ko"


def test_gemini_provider_mocked(monkeypatch) -> None:
    def fake_post(self, url, **kwargs):
        assert "gemini-3.8-flash:generateContent" in url
        assert kwargs["headers"]["x-goog-api-key"] == "fake-key"
        assert "params" not in kwargs or "key" not in (kwargs.get("params") or {})
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": '{"text": "Café crème", "languages": [{"code": "fr", "name": "French"}]}'
                                }
                            ]
                        }
                    }
                ]
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    cfg = AppConfig(ai_provider="gemini", gemini_api_key="fake-key")
    engine = VisionAIEngine(cfg)
    res = engine.recognize(Image.new("RGB", (60, 30), "white"))

    assert res.ok
    assert res.text == "Café crème"
    assert res.languages[0].name == "French"
    assert "Gemini" in res.engine_name


def test_gemini_404_auto_recovers_from_error_hint(monkeypatch) -> None:
    attempted_urls: list[str] = []

    def fake_post(self, url, **kwargs):
        attempted_urls.append(url)
        if "gemini-2.5-flash:generateContent" in url:
            return httpx.Response(
                404,
                json={
                    "error": {
                        "message": (
                            "This model models/gemini-2.5-flash is no longer available to new users. "
                            "Please update your code to use models/gemini-3.8-flash for the latest features."
                        )
                    }
                },
                request=httpx.Request("POST", url),
            )
        assert "gemini-3.8-flash:generateContent" in url
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": '{"text": "Recovered text", "languages": [{"code": "en", "name": "English"}]}'
                                }
                            ]
                        }
                    }
                ]
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    cfg = AppConfig(ai_provider="gemini", gemini_api_key="fake-key", gemini_model="gemini-2.5-flash")
    res = VisionAIEngine(cfg).recognize(Image.new("RGB", (60, 30), "white"))

    assert res.ok
    assert res.text == "Recovered text"
    assert "gemini-3.8-flash" in res.engine_name
    assert cfg.gemini_model == "gemini-3.8-flash"
    assert len(attempted_urls) == 2


def test_gemini_404_auto_recovers_from_models_catalog(monkeypatch) -> None:
    def fake_post(self, url, **kwargs):
        if "gemini-old-custom:generateContent" in url:
            return httpx.Response(
                404,
                json={"error": {"message": "Model not found."}},
                request=httpx.Request("POST", url),
            )
        assert "gemini-3.8-flash:generateContent" in url
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": '{"text": "Catalog text", "languages": [{"code": "en", "name": "English"}]}'
                                }
                            ]
                        }
                    }
                ]
            },
            request=httpx.Request("POST", url),
        )

    def fake_get(self, url, **kwargs):
        assert url.endswith("/v1beta/models")
        assert kwargs["headers"]["x-goog-api-key"] == "fake-key"
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "models/gemini-3.5-flash-lite",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/gemini-3.8-flash",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                    {
                        "name": "models/gemini-4.0-flash-preview",
                        "supportedGenerationMethods": ["generateContent"],
                    },
                ]
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    monkeypatch.setattr(httpx.Client, "get", fake_get)
    cfg = AppConfig(ai_provider="gemini", gemini_api_key="fake-key", gemini_model="gemini-old-custom")
    res = VisionAIEngine(cfg).recognize(Image.new("RGB", (60, 30), "white"))

    assert res.ok
    assert res.text == "Catalog text"
    assert cfg.gemini_model == "gemini-3.8-flash"


def test_config_migrates_deprecated_gemini_model(tmp_path) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text('{"gemini_model": "gemini-2.5-flash"}', encoding="utf-8")
    loaded = AppConfig.load(cfg_path)
    assert loaded.gemini_model == "gemini-3.8-flash"

    # Custom non-deprecated model is preserved untouched
    cfg_path.write_text('{"gemini_model": "gemini-3.6-flash"}', encoding="utf-8")
    loaded_custom = AppConfig.load(cfg_path)
    assert loaded_custom.gemini_model == "gemini-3.6-flash"


def test_gemini_http_error_sanitized(monkeypatch) -> None:
    def fake_post(self, url, **kwargs):
        return httpx.Response(
            403,
            json={"error": {"message": "API key not valid."}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    cfg = AppConfig(ai_provider="gemini", gemini_api_key="super-secret-token")
    engine = VisionAIEngine(cfg)
    res = engine.recognize(Image.new("RGB", (60, 30), "white"))

    assert not res.ok
    assert res.error is not None
    assert "403" in res.error
    assert "API key not valid." in res.error
    assert "super-secret-token" not in res.error


def test_ollama_provider_mocked(monkeypatch) -> None:
    def fake_post(self, url, **kwargs):
        assert url.endswith("/api/chat")
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": '{"text": "Привет", "languages": [{"code": "ru", "name": "Russian"}]}'
                }
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    cfg = AppConfig(ai_provider="ollama", ollama_model="qwen2.5vl:7b")
    engine = VisionAIEngine(cfg)
    res = engine.recognize(Image.new("RGB", (60, 30), "white"))

    assert res.ok
    assert res.text == "Привет"
    assert res.languages[0].code == "ru"
    assert "Ollama" in res.engine_name


def test_openai_provider_mocked(monkeypatch) -> None:
    def fake_post(self, url, **kwargs):
        assert url.endswith("/chat/completions")
        assert kwargs["headers"]["Authorization"] == "Bearer sk-test"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"text": "Hola mundo", "languages": [{"code": "es", "name": "Spanish"}]}'
                        }
                    }
                ]
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    cfg = AppConfig(ai_provider="openai", openai_api_key="sk-test", openai_model="gpt-4o-mini")
    engine = VisionAIEngine(cfg)
    res = engine.recognize(Image.new("RGB", (60, 30), "white"))

    assert res.ok
    assert res.text == "Hola mundo"
    assert res.languages[0].code == "es"
    assert "OpenAI" in res.engine_name


def test_vision_ai_markdown_and_latex_prompts(monkeypatch) -> None:
    from ocr_snip.ocr.vision_ai import build_vision_prompt

    assert "Markdown tables" in build_vision_prompt("markdown")
    assert "LaTeX" in build_vision_prompt("latex")

    captured_prompts: list[str] = []

    def fake_post(self, url, **kwargs):
        sys_inst = kwargs["json"]["systemInstruction"]["parts"][0]["text"]
        captured_prompts.append(sys_inst)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": '{"text": "| A | B |\\n|---|---|\\n| 1 | 2 |", "languages": [{"code": "en", "name": "English"}]}'
                                }
                            ]
                        }
                    }
                ]
            },
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    cfg = AppConfig(ai_provider="gemini", gemini_api_key="key")
    res = VisionAIEngine(cfg).recognize(
        Image.new("RGB", (60, 30), "white"), output_format="markdown"
    )
    assert res.ok
    assert "| A | B |" in res.text
    assert "[markdown]" in res.engine_name
    assert captured_prompts and "Markdown tables" in captured_prompts[0]


