"""Tests for Offline Language Pack Manager helpers and smart multi-script auto-probe."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from ocr_snip.ocr.base import DetectedLanguage, OCRResult
from ocr_snip.ocr.local_rapidocr import (
    SCRIPT_PROFILES,
    LocalRapidOCREngine,
    is_script_installed,
    list_installed_scripts,
)


def test_language_pack_detection_and_removal(tmp_path: Path) -> None:
    korean_file = tmp_path / SCRIPT_PROFILES["korean"].model_filename
    korean_file.write_bytes(b"fake-onnx")

    assert is_script_installed("korean", models_dir=tmp_path) is True
    assert is_script_installed("arabic", models_dir=tmp_path) is False
    assert list_installed_scripts(models_dir=tmp_path, exclude_auto=True) == ["korean"]

    engine = LocalRapidOCREngine(models_dir=tmp_path)
    assert engine.remove_script_pack("korean") is True
    assert is_script_installed("korean", models_dir=tmp_path) is False
    assert engine.remove_script_pack("auto") is False  # universal base pack cannot be removed


def test_smart_offline_auto_probe_picks_installed_script(tmp_path: Path, monkeypatch) -> None:
    # Pretend Korean & Arabic packs are installed locally
    (tmp_path / SCRIPT_PROFILES["korean"].model_filename).write_bytes(b"fake")
    (tmp_path / SCRIPT_PROFILES["arabic"].model_filename).write_bytes(b"fake")

    engine = LocalRapidOCREngine(
        default_script="auto",
        auto_probe_installed_scripts=True,
        offline_probe_threshold=0.72,
        models_dir=tmp_path,
    )

    def fake_run(img_arr, script_key: str, keep_breaks: bool) -> OCRResult:
        if script_key == "auto":
            return OCRResult(text="???", engine_name="Local ML (PP-OCRv6)", confidence=0.41, script_used="auto")
        if script_key == "korean":
            return OCRResult(
                text="안녕하세요",
                engine_name="Local ML (PP-OCRv5)",
                confidence=0.98,
                languages=[DetectedLanguage("ko", "Korean", "Hangul", 0.99)],
                script_used="korean",
            )
        return OCRResult(text="", engine_name="Local ML (PP-OCRv5)", confidence=0.10, script_used=script_key)

    monkeypatch.setattr(engine, "_run_single_script", fake_run)

    res = engine.recognize(Image.new("RGB", (120, 40), "white"))
    assert res.ok
    assert res.text == "안녕하세요"
    assert res.script_used == "korean"
    assert "Auto-detected offline language pack" in res.fallback_note
