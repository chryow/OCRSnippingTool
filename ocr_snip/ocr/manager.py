"""Hybrid OCR orchestration manager combining offline RapidOCR and optional Vision AI."""

from __future__ import annotations

from PIL import Image

from ocr_snip.config import AppConfig
from ocr_snip.ocr.base import OCREngine, OCRResult
from ocr_snip.ocr.local_rapidocr import LocalRapidOCREngine
from ocr_snip.ocr.vision_ai import VisionAIEngine


class OCRManager:
    """Coordinates Local ML OCR and Vision AI according to user configuration."""

    def __init__(
        self,
        config: AppConfig,
        local_engine: OCREngine | None = None,
        vision_engine: OCREngine | None = None,
    ) -> None:
        self.config = config
        self._local = local_engine or LocalRapidOCREngine(
            default_script=config.local_script,
            preserve_line_breaks=config.preserve_line_breaks,
            auto_probe_installed_scripts=config.auto_probe_installed_scripts,
            offline_probe_threshold=config.offline_probe_threshold,
        )
        self._vision = vision_engine or VisionAIEngine(config)

    @property
    def local_engine(self) -> OCREngine:
        return self._local

    def update_config(self, config: AppConfig) -> None:
        self.config = config
        if isinstance(self._local, LocalRapidOCREngine):
            self._local.default_script = config.local_script
            self._local.preserve_line_breaks = config.preserve_line_breaks
            self._local.auto_probe_installed_scripts = config.auto_probe_installed_scripts
            self._local.offline_probe_threshold = config.offline_probe_threshold
        if isinstance(self._vision, VisionAIEngine):
            self._vision.config = config

    def recognize(
        self,
        image: Image.Image,
        *,
        force_engine: str | None = None,
        script_override: str | None = None,
        ai_output_format: str | None = None,
    ) -> OCRResult:
        """Run OCR using the configured mode (`hybrid`, `local`, or `vision_ai`)."""
        mode = (force_engine or self.config.engine_mode).strip().lower()
        fmt = ai_output_format or self.config.ai_output_format

        if script_override is not None and force_engine != "vision_ai":
            return self._local.recognize(
                image,
                script=script_override,
                preserve_line_breaks=self.config.preserve_line_breaks,
            )

        if mode == "vision_ai":
            return self._vision.recognize(image, output_format=fmt)

        if mode == "local":
            return self._local.recognize(
                image,
                script=self.config.local_script,
                preserve_line_breaks=self.config.preserve_line_breaks,
            )

        # Hybrid mode: fast offline ML first
        local_res = self._local.recognize(
            image,
            script=self.config.local_script,
            preserve_line_breaks=self.config.preserve_line_breaks,
        )

        needs_ai = (
            not local_res.ok
            or not local_res.text.strip()
            or local_res.confidence < self.config.hybrid_confidence_threshold
        )

        if needs_ai and self.config.is_vision_ai_configured():
            reason = (
                "local OCR failed"
                if not local_res.ok
                else "no text found locally"
                if not local_res.text.strip()
                else f"low local confidence ({local_res.confidence:.0%})"
            )
            ai_res = self._vision.recognize(image, output_format=fmt)
            if ai_res.ok and (ai_res.text.strip() or not local_res.text.strip()):
                ai_res.fallback_note = f"Auto-enhanced via Vision AI ({reason})"
                return ai_res
            if local_res.ok:
                local_res.fallback_note = f"Vision AI fallback failed: {ai_res.error}"
                return local_res
            return ai_res

        return local_res
