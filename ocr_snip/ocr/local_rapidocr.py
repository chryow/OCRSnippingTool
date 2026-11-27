"""Offline deep-learning OCR powered by RapidOCR (ONNX Runtime / PP-OCRv6 & PP-OCRv5).

Supports 100+ languages completely offline:
- Default `auto` / `universal` uses PP-OCRv6 multi-language ONNX model covering
  English, Latin languages, Simplified/Traditional Chinese, Japanese, and Greek
  in a single fast model.
- Specialized PP-OCRv5 ONNX recognition models cover Korean, Cyrillic (Russian,
  Ukrainian, etc.), Arabic (Arabic/Persian/Urdu), Devanagari (Hindi/Marathi/Nepali),
  Thai, Latin (high-accuracy European diacritics), Greek, Tamil, and Telugu.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image, ImageOps

from ocr_snip.config import get_models_dir
from ocr_snip.language import detect_languages
from ocr_snip.ocr.base import OCREngine, OCRLine, OCRResult


@dataclass(frozen=True)
class ScriptProfile:
    key: str
    label: str
    description: str
    ocr_version: str  # "PP-OCRv6" or "PP-OCRv5"
    lang_rec: str     # LangRec enum value, e.g. "ch", "latin", "korean"
    model_type: str   # "small" (for v6) or "mobile" (for v5)


SCRIPT_PROFILES: dict[str, ScriptProfile] = {
    "auto": ScriptProfile(
        key="auto",
        label="Auto (Universal Multi-Language)",
        description="PP-OCRv6 universal model (English, Latin, Chinese, Japanese, Greek)",
        ocr_version="PP-OCRv6",
        lang_rec="ch",
        model_type="small",
    ),
    "latin": ScriptProfile(
        key="latin",
        label="Latin / European (80+ langs)",
        description="English, French, Spanish, German, Portuguese, Vietnamese, Indonesian, etc.",
        ocr_version="PP-OCRv5",
        lang_rec="latin",
        model_type="mobile",
    ),
    "korean": ScriptProfile(
        key="korean",
        label="Korean (Hangul)",
        description="Korean + English",
        ocr_version="PP-OCRv5",
        lang_rec="korean",
        model_type="mobile",
    ),
    "eslav": ScriptProfile(
        key="eslav",
        label="Russian / Ukrainian / Belarusian",
        description="High-accuracy East Slavic Cyrillic model",
        ocr_version="PP-OCRv5",
        lang_rec="eslav",
        model_type="mobile",
    ),
    "cyrillic": ScriptProfile(
        key="cyrillic",
        label="Cyrillic (All Cyrillic langs)",
        description="Russian, Ukrainian, Bulgarian, Serbian, Belarusian, Kazakh",
        ocr_version="PP-OCRv5",
        lang_rec="cyrillic",
        model_type="mobile",
    ),
    "arabic": ScriptProfile(
        key="arabic",
        label="Arabic / Persian / Urdu",
        description="Arabic script languages",
        ocr_version="PP-OCRv5",
        lang_rec="arabic",
        model_type="mobile",
    ),
    "devanagari": ScriptProfile(
        key="devanagari",
        label="Devanagari (Hindi, Marathi, Nepali)",
        description="Hindi, Marathi, Nepali, Sanskrit",
        ocr_version="PP-OCRv5",
        lang_rec="devanagari",
        model_type="mobile",
    ),
    "thai": ScriptProfile(
        key="thai",
        label="Thai",
        description="Thai script",
        ocr_version="PP-OCRv5",
        lang_rec="th",
        model_type="mobile",
    ),
    "greek": ScriptProfile(
        key="greek",
        label="Greek",
        description="Greek alphabet",
        ocr_version="PP-OCRv5",
        lang_rec="el",
        model_type="mobile",
    ),
    "tamil": ScriptProfile(
        key="tamil",
        label="Tamil",
        description="Tamil script",
        ocr_version="PP-OCRv5",
        lang_rec="ta",
        model_type="mobile",
    ),
    "telugu": ScriptProfile(
        key="telugu",
        label="Telugu",
        description="Telugu script",
        ocr_version="PP-OCRv5",
        lang_rec="te",
        model_type="mobile",
    ),
}


def preprocess_snip_image(image: Image.Image) -> np.ndarray:
    """Prepare a tightly-cropped screen snip for accurate OCR detection.

    - Converts to RGB
    - Upscales small snips so text line height is clear for DBNet++
    - Adds subtle border padding around tightly-cropped regions
    """
    rgb = image.convert("RGB")
    w, h = rgb.size
    if w <= 0 or h <= 0:
        raise ValueError("Cannot run OCR on an empty image.")

    # Upscale very small crops (common when snipping a single label or line)
    min_dim = min(w, h)
    if min_dim < 64:
        scale = min(3.0, max(2.0, 96.0 / max(min_dim, 1)))
        rgb = rgb.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    elif max(w, h) < 200:
        rgb = rgb.resize((int(w * 1.5), int(h * 1.5)), Image.Resampling.LANCZOS)

    # Estimate background edge color for natural border padding so dark-mode snips stay clean
    arr = np.asarray(rgb)
    border_pixels = np.concatenate([arr[0, :], arr[-1, :], arr[:, 0], arr[:, -1]], axis=0)
    median_bg = tuple(int(v) for v in np.median(border_pixels, axis=0))
    padded = ImageOps.expand(rgb, border=16, fill=median_bg)
    return np.asarray(padded)


class LocalRapidOCREngine(OCREngine):
    """Offline ONNX OCR engine using RapidOCR with lazy model caching per script."""

    name = "Local ML (RapidOCR)"

    def __init__(self, default_script: str = "auto", preserve_line_breaks: bool = True) -> None:
        self.default_script = default_script if default_script in SCRIPT_PROFILES else "auto"
        self.preserve_line_breaks = preserve_line_breaks
        self._engines: dict[str, Any] = {}
        self._lock = threading.Lock()

    def _get_engine(self, script_key: str) -> Any:
        profile = SCRIPT_PROFILES.get(script_key, SCRIPT_PROFILES["auto"])
        with self._lock:
            if profile.key in self._engines:
                return self._engines[profile.key]

            from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR

            params: dict[str, Any] = {
                "Global.log_level": "warning",
                "Global.text_score": 0.45,
                "Global.model_root_dir": str(get_models_dir()),
            }
            if profile.ocr_version == "PP-OCRv5":
                params.update(
                    {
                        "Rec.ocr_version": OCRVersion.PPOCRV5,
                        "Rec.lang_type": LangRec(profile.lang_rec),
                        "Rec.model_type": ModelType(profile.model_type),
                    }
                )
            else:
                params.update(
                    {
                        "Det.ocr_version": OCRVersion.PPOCRV6,
                        "Det.model_type": ModelType.SMALL,
                        "Rec.ocr_version": OCRVersion.PPOCRV6,
                        "Rec.model_type": ModelType.SMALL,
                    }
                )

            engine = RapidOCR(params=params)
            self._engines[profile.key] = engine
            return engine

    def recognize(
        self,
        image: Image.Image,
        *,
        script: str | None = None,
        preserve_line_breaks: bool | None = None,
        **kwargs: Any,
    ) -> OCRResult:
        script_key = script or self.default_script
        if script_key not in SCRIPT_PROFILES:
            script_key = "auto"
        profile = SCRIPT_PROFILES[script_key]
        keep_breaks = (
            self.preserve_line_breaks if preserve_line_breaks is None else preserve_line_breaks
        )

        start = time.perf_counter()
        try:
            engine = self._get_engine(script_key)
            img_arr = preprocess_snip_image(image)
            raw = engine(img_arr)
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000.0
            return OCRResult(
                text="",
                engine_name=f"{self.name} [{profile.key}]",
                confidence=0.0,
                elapsed_ms=round(elapsed, 1),
                script_used=profile.key,
                error=f"Local OCR failed: {exc}",
            )

        elapsed = (time.perf_counter() - start) * 1000.0
        txts = list(raw.txts) if getattr(raw, "txts", None) else []
        scores = list(raw.scores) if getattr(raw, "scores", None) else []
        boxes = raw.boxes if getattr(raw, "boxes", None) is not None else []

        lines: list[OCRLine] = []
        for idx, txt in enumerate(txts):
            score = float(scores[idx]) if idx < len(scores) else 0.0
            bbox = boxes[idx].tolist() if idx < len(boxes) and hasattr(boxes[idx], "tolist") else []
            lines.append(OCRLine(text=str(txt), confidence=score, bbox=bbox))

        # Group boxes into visual rows (top-to-bottom, left-to-right within each row)
        rows = _group_reading_rows(lines)
        ordered_lines = [line for row in rows for line in row]
        full_text = _format_rows(rows, preserve_breaks=keep_breaks)
        avg_conf = (
            sum(line.confidence for line in ordered_lines) / len(ordered_lines)
            if ordered_lines
            else 0.0
        )
        langs = detect_languages(full_text) if full_text else []

        return OCRResult(
            text=full_text,
            engine_name=f"Local ML ({profile.ocr_version})",
            confidence=round(avg_conf, 3),
            lines=ordered_lines,
            languages=langs,
            elapsed_ms=round(elapsed, 1),
            script_used=profile.key,
        )


def _group_reading_rows(lines: list[OCRLine]) -> list[list[OCRLine]]:
    """Group OCR boxes into visual horizontal rows sorted top-to-bottom, left-to-right."""
    if not lines:
        return []
    if any(len(line.bbox) < 4 for line in lines):
        return [[line] for line in lines]

    def _metrics(line: OCRLine) -> tuple[float, float, float]:
        ys = [pt[1] for pt in line.bbox]
        xs = [pt[0] for pt in line.bbox]
        y_center = (min(ys) + max(ys)) / 2.0
        height = max(max(ys) - min(ys), 1.0)
        return y_center, min(xs), height

    decorated = [(line, *_metrics(line)) for line in lines]
    decorated.sort(key=lambda item: item[1])

    rows: list[list[tuple[OCRLine, float, float, float]]] = []
    for item in decorated:
        placed = False
        for row in rows:
            ref_y = row[0][1]
            ref_h = row[0][3]
            if abs(item[1] - ref_y) <= max(ref_h, item[3]) * 0.55:
                row.append(item)
                placed = True
                break
        if not placed:
            rows.append([item])

    grouped: list[list[OCRLine]] = []
    for row in rows:
        row.sort(key=lambda item: item[2])
        grouped.append([item[0] for item in row])
    return grouped


def _format_rows(rows: list[list[OCRLine]], preserve_breaks: bool = True) -> str:
    """Join boxes within the same row with spaces and rows with newlines."""
    row_texts: list[str] = []
    for row in rows:
        parts = [line.text.strip() for line in row if line.text and line.text.strip()]
        if parts:
            row_texts.append(" ".join(parts))
    sep = "\n" if preserve_breaks else " "
    return sep.join(row_texts)
