"""Tests for persistent AppConfig."""

from __future__ import annotations

from pathlib import Path

from ocr_snip.config import AppConfig


def test_config_roundtrip(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.json"
    original = AppConfig(
        hotkey="<ctrl>+<alt>+s",
        engine_mode="local",
        local_script="korean",
        hybrid_confidence_threshold=0.72,
        ai_provider="ollama",
        ollama_model="llava:latest",
        auto_copy=False,
        popup_auto_close_seconds=10,
    )
    original.save(cfg_file)
    loaded = AppConfig.load(cfg_file)

    assert loaded.hotkey == "<ctrl>+<alt>+s"
    assert loaded.engine_mode == "local"
    assert loaded.local_script == "korean"
    assert loaded.hybrid_confidence_threshold == 0.72
    assert loaded.ai_provider == "ollama"
    assert loaded.ollama_model == "llava:latest"
    assert loaded.auto_copy is False
    assert loaded.popup_auto_close_seconds == 10


def test_config_ignores_unknown_fields(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text('{"hotkey": "<alt>+<shift>+o", "future_flag": true}', encoding="utf-8")
    loaded = AppConfig.load(cfg_file)
    assert loaded.hotkey == "<alt>+<shift>+o"


def test_vision_ai_configured_env_fallback(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    cfg = AppConfig(ai_provider="gemini", gemini_api_key="")
    assert cfg.is_vision_ai_configured() is False

    monkeypatch.setenv("GEMINI_API_KEY", "test-secret-key")
    assert cfg.is_vision_ai_configured() is True

    cfg_ollama = AppConfig(ai_provider="ollama", ollama_base_url="http://localhost:11434")
    assert cfg_ollama.is_vision_ai_configured() is True
