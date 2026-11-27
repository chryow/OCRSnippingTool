"""Tests for Hybrid OCRManager orchestration logic."""

from __future__ import annotations

from PIL import Image

from ocr_snip.config import AppConfig
from ocr_snip.ocr.base import DetectedLanguage, OCREngine, OCRResult
from ocr_snip.ocr.manager import OCRManager


class StubEngine(OCREngine):
    def __init__(self, result: OCRResult) -> None:
        self._result = result
        self.calls: int = 0
        self.last_kwargs: dict = {}

    def recognize(self, image: Image.Image, **kwargs) -> OCRResult:
        self.calls += 1
        self.last_kwargs = kwargs
        return self._result


def test_hybrid_keeps_high_confidence_local() -> None:
    local = StubEngine(
        OCRResult(
            text="Fast local result",
            engine_name="Local ML",
            confidence=0.95,
            languages=[DetectedLanguage("en", "English")],
        )
    )
    vision = StubEngine(OCRResult(text="AI result", engine_name="Gemini", confidence=0.99))
    cfg = AppConfig(engine_mode="hybrid", ai_provider="gemini", gemini_api_key="key")
    mgr = OCRManager(cfg, local_engine=local, vision_engine=vision)

    res = mgr.recognize(Image.new("RGB", (40, 20), "white"))
    assert res.text == "Fast local result"
    assert local.calls == 1
    assert vision.calls == 0


def test_hybrid_falls_back_to_vision_on_low_confidence() -> None:
    local = StubEngine(OCRResult(text="garbled", engine_name="Local ML", confidence=0.35))
    vision = StubEngine(
        OCRResult(
            text="안녕하세요",
            engine_name="Gemini",
            confidence=0.98,
            languages=[DetectedLanguage("ko", "Korean")],
        )
    )
    cfg = AppConfig(
        engine_mode="hybrid",
        hybrid_confidence_threshold=0.65,
        ai_provider="gemini",
        gemini_api_key="key",
    )
    mgr = OCRManager(cfg, local_engine=local, vision_engine=vision)

    res = mgr.recognize(Image.new("RGB", (40, 20), "white"))
    assert res.text == "안녕하세요"
    assert "Auto-enhanced via Vision AI" in res.fallback_note
    assert local.calls == 1
    assert vision.calls == 1


def test_hybrid_gracefully_returns_local_when_vision_errors() -> None:
    local = StubEngine(OCRResult(text="partial text", engine_name="Local ML", confidence=0.40))
    vision = StubEngine(OCRResult(text="", engine_name="Gemini", error="Network offline"))
    cfg = AppConfig(engine_mode="hybrid", ai_provider="gemini", gemini_api_key="key")
    mgr = OCRManager(cfg, local_engine=local, vision_engine=vision)

    res = mgr.recognize(Image.new("RGB", (40, 20), "white"))
    assert res.ok
    assert res.text == "partial text"
    assert "Network offline" in res.fallback_note


def test_script_override_forces_local_with_script() -> None:
    local = StubEngine(OCRResult(text="Привет", engine_name="Local ML", confidence=0.92))
    vision = StubEngine(OCRResult(text="AI", engine_name="Gemini", confidence=0.99))
    cfg = AppConfig(engine_mode="vision_ai", ai_provider="gemini", gemini_api_key="key")
    mgr = OCRManager(cfg, local_engine=local, vision_engine=vision)

    res = mgr.recognize(Image.new("RGB", (40, 20), "white"), script_override="cyrillic")
    assert res.text == "Привет"
    assert local.last_kwargs["script"] == "cyrillic"
    assert vision.calls == 0
