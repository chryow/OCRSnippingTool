"""Offline deep-learning OCR powered by RapidOCR (ONNX Runtime / PP-OCRv6 & PP-OCRv5).

Supports 100+ languages completely offline:
- Default `auto` uses the PP-OCRv6 universal ONNX model (English, Latin languages,
  Simplified/Traditional Chinese, Japanese, and Greek).
- Specialized PP-OCRv5 ONNX recognition packs cover Latin (80+ European langs),
  Korean, East Slavic (Russian/Ukrainian/Belarusian), Cyrillic, Arabic/Persian/Urdu,
  Devanagari (Hindi/Marathi/Nepali), Thai, Greek, Tamil, and Telugu.
- When `auto_probe_installed_scripts` is enabled, low-confidence `auto` snips
  automatically probe any locally installed specialized language packs and pick
  the highest-confidence recognition with zero manual switching.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
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
    ocr_version: str      # "PP-OCRv6" or "PP-OCRv5"
    lang_rec: str         # LangRec enum value, e.g. "ch", "latin", "korean"
    model_type: str       # "small" (for v6) or "mobile" (for v5)
    model_filename: str   # Expected ONNX filename inside models_dir


SCRIPT_PROFILES: dict[str, ScriptProfile] = {
    "auto": ScriptProfile(
        key="auto",
        label="Auto (Universal Multi-Language)",
        description="PP-OCRv6 universal model (English, Latin, Chinese, Japanese, Greek)",
        ocr_version="PP-OCRv6",
        lang_rec="ch",
        model_type="small",
        model_filename="PP-OCRv6_rec_small.onnx",
    ),
    "latin": ScriptProfile(
        key="latin",
        label="Latin / European (80+ langs)",
        description="English, French, Spanish, German, Portuguese, Vietnamese, Indonesian, etc.",
        ocr_version="PP-OCRv5",
        lang_rec="latin",
        model_type="mobile",
        model_filename="latin_PP-OCRv5_rec_mobile.onnx",
    ),
    "korean": ScriptProfile(
        key="korean",
        label="Korean (Hangul)",
        description="Korean + English",
        ocr_version="PP-OCRv5",
        lang_rec="korean",
        model_type="mobile",
        model_filename="korean_PP-OCRv5_rec_mobile.onnx",
    ),
    "eslav": ScriptProfile(
        key="eslav",
        label="Russian / Ukrainian / Belarusian",
        description="High-accuracy East Slavic Cyrillic model",
        ocr_version="PP-OCRv5",
        lang_rec="eslav",
        model_type="mobile",
        model_filename="eslav_PP-OCRv5_rec_mobile.onnx",
    ),
    "cyrillic": ScriptProfile(
        key="cyrillic",
        label="Cyrillic (All Cyrillic langs)",
        description="Russian, Ukrainian, Bulgarian, Serbian, Belarusian, Kazakh",
        ocr_version="PP-OCRv5",
        lang_rec="cyrillic",
        model_type="mobile",
        model_filename="cyrillic_PP-OCRv5_rec_mobile.onnx",
    ),
    "arabic": ScriptProfile(
        key="arabic",
        label="Arabic / Persian / Urdu",
        description="Arabic script languages",
        ocr_version="PP-OCRv5",
        lang_rec="arabic",
        model_type="mobile",
        model_filename="arabic_PP-OCRv5_rec_mobile.onnx",
    ),
    "devanagari": ScriptProfile(
        key="devanagari",
        label="Devanagari (Hindi, Marathi, Nepali)",
        description="Hindi, Marathi, Nepali, Sanskrit",
        ocr_version="PP-OCRv5",
        lang_rec="devanagari",
        model_type="mobile",
        model_filename="devanagari_PP-OCRv5_rec_mobile.onnx",
    ),
    "thai": ScriptProfile(
        key="thai",
        label="Thai",
        description="Thai script",
        ocr_version="PP-OCRv5",
        lang_rec="th",
        model_type="mobile",
        model_filename="th_PP-OCRv5_rec_mobile.onnx",
    ),
    "greek": ScriptProfile(
        key="greek",
        label="Greek",
        description="Greek alphabet",
        ocr_version="PP-OCRv5",
        lang_rec="el",
        model_type="mobile",
        model_filename="el_PP-OCRv5_rec_mobile.onnx",
    ),
    "tamil": ScriptProfile(
        key="tamil",
        label="Tamil",
        description="Tamil script",
        ocr_version="PP-OCRv5",
        lang_rec="ta",
        model_type="mobile",
        model_filename="ta_PP-OCRv5_rec_mobile.onnx",
    ),
    "telugu": ScriptProfile(
        key="telugu",
        label="Telugu",
        description="Telugu script",
        ocr_version="PP-OCRv5",
        lang_rec="te",
        model_type="mobile",
        model_filename="te_PP-OCRv5_rec_mobile.onnx",
    ),
}


def is_script_installed(script_key: str, models_dir: Path | None = None) -> bool:
    """Return True if the ONNX recognition model for `script_key` is already cached locally."""
    profile = SCRIPT_PROFILES.get(script_key)
    if profile is None:
        return False
    root = models_dir or get_models_dir()
    if not root.exists():
        return False
    if (root / profile.model_filename).exists():
        return True
    return any(root.rglob(profile.model_filename))


def list_installed_scripts(
    models_dir: Path | None = None, *, exclude_auto: bool = False
) -> list[str]:
    """Return script keys whose ONNX packs are present in `models_dir`."""
    installed: list[str] = []
    for key in SCRIPT_PROFILES:
        if exclude_auto and key == "auto":
            continue
        if is_script_installed(key, models_dir=models_dir):
            installed.append(key)
    return installed


def preprocess_snip_image(image: Image.Image, max_side: int = 2400) -> np.ndarray:
    """Prepare a screen snip for accurate, fast OCR detection.

    - Converts to RGB
    - Downscales giant 4K/8K captures cleanly to cap memory & cut CPU latency
    - Upscales tiny snips so text line height is clear for DBNet++
    - Adds subtle background-matched border padding around tightly-cropped regions
    """
    rgb = image.convert("RGB")
    w, h = rgb.size
    if w <= 0 or h <= 0:
        raise ValueError("Cannot run OCR on an empty image.")

    max_dim = max(w, h)
    min_dim = min(w, h)
    if max_dim > max_side:
        scale = max_side / max_dim
        rgb = rgb.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.Resampling.LANCZOS)
    elif min_dim < 64:
        scale = min(3.0, max(2.0, 96.0 / max(min_dim, 1)))
        rgb = rgb.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    elif max_dim < 200:
        rgb = rgb.resize((int(w * 1.5), int(h * 1.5)), Image.Resampling.LANCZOS)

    arr = np.asarray(rgb)
    border_pixels = np.concatenate([arr[0, :], arr[-1, :], arr[:, 0], arr[:, -1]], axis=0)
    median_bg = tuple(int(v) for v in np.median(border_pixels, axis=0))
    padded = ImageOps.expand(rgb, border=16, fill=median_bg)
    return np.asarray(padded)


class LocalRapidOCREngine(OCREngine):
    """Offline ONNX OCR engine using RapidOCR with lazy model caching and smart auto-probe."""

    name = "Local ML (RapidOCR)"

    def __init__(
        self,
        default_script: str = "auto",
        preserve_line_breaks: bool = True,
        auto_probe_installed_scripts: bool = True,
        offline_probe_threshold: float = 0.72,
        models_dir: Path | None = None,
    ) -> None:
        self.default_script = default_script if default_script in SCRIPT_PROFILES else "auto"
        self.preserve_line_breaks = preserve_line_breaks
        self.auto_probe_installed_scripts = auto_probe_installed_scripts
        self.offline_probe_threshold = offline_probe_threshold
        self._models_dir = models_dir
        self._engines: dict[str, Any] = {}
        self._lock = threading.Lock()

    @property
    def models_dir(self) -> Path:
        if self._models_dir is not None:
            self._models_dir.mkdir(parents=True, exist_ok=True)
            return self._models_dir
        return get_models_dir()

    def _get_engine(self, script_key: str) -> Any:
        profile = SCRIPT_PROFILES.get(script_key, SCRIPT_PROFILES["auto"])
        with self._lock:
            if profile.key in self._engines:
                return self._engines[profile.key]

            from rapidocr import LangRec, ModelType, OCRVersion, RapidOCR

            params: dict[str, Any] = {
                "Global.log_level": "warning",
                "Global.text_score": 0.45,
                "Global.model_root_dir": str(self.models_dir),
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
            # Reuse already-loaded text detector & orientation classifier sessions
            # from the base 'auto' engine to cut RAM usage by ~25-35 MB per pack.
            base_engine = self._engines.get("auto")
            if profile.key != "auto" and base_engine is not None:
                if getattr(base_engine, "text_det", None) is not None:
                    engine.text_det = base_engine.text_det
                if getattr(base_engine, "text_cls", None) is not None:
                    engine.text_cls = base_engine.text_cls
            self._engines[profile.key] = engine
            return engine

    def download_script_pack(self, script_key: str) -> Path:
        """Download and cache the ONNX model pack for `script_key` into `models_dir`."""
        if script_key not in SCRIPT_PROFILES:
            raise ValueError(f"Unknown script pack: {script_key}")
        engine = self._get_engine(script_key)
        if script_key == "auto" and hasattr(engine, "_load_det_model"):
            engine._load_det_model()
        if hasattr(engine, "_load_rec_model"):
            engine._load_rec_model()
        return self.models_dir

    def remove_script_pack(self, script_key: str) -> bool:
        """Remove a cached ONNX language pack from `models_dir`."""
        profile = SCRIPT_PROFILES.get(script_key)
        if profile is None or script_key == "auto":
            return False

        with self._lock:
            self._engines.pop(script_key, None)

        removed = False
        stem = Path(profile.model_filename).stem
        for candidate in list(self.models_dir.rglob(f"*{stem}*")):
            if candidate.is_file():
                try:
                    candidate.unlink()
                    removed = True
                except OSError:
                    pass
        # Also remove matching dict file if present (e.g. ppocrv5_korean_dict.txt)
        dict_pattern = f"*{profile.lang_rec}*dict*.txt"
        for dict_file in list(self.models_dir.rglob(dict_pattern)):
            if dict_file.is_file():
                try:
                    dict_file.unlink()
                except OSError:
                    pass
        return removed

    def _run_single_script(
        self, img_arr: np.ndarray, script_key: str, keep_breaks: bool
    ) -> OCRResult:
        profile = SCRIPT_PROFILES[script_key]
        start = time.perf_counter()
        try:
            engine = self._get_engine(script_key)
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

    def recognize(
        self,
        image: Image.Image,
        *,
        script: str | None = None,
        preserve_line_breaks: bool | None = None,
        allow_auto_probe: bool = True,
        **kwargs: Any,
    ) -> OCRResult:
        script_key = script or self.default_script
        if script_key not in SCRIPT_PROFILES:
            script_key = "auto"
        keep_breaks = (
            self.preserve_line_breaks if preserve_line_breaks is None else preserve_line_breaks
        )

        total_start = time.perf_counter()
        try:
            img_arr = preprocess_snip_image(image)
        except Exception as exc:
            return OCRResult(
                text="",
                engine_name=self.name,
                confidence=0.0,
                script_used=script_key,
                error=f"Image preprocessing failed: {exc}",
            )

        best = self._run_single_script(img_arr, script_key, keep_breaks)

        # Smart Offline Multi-Script Auto-Probe:
        # When running "auto" (universal PP-OCRv6) and confidence is low or text is empty,
        # automatically test any installed specialized PP-OCRv5 language packs!
        should_probe = (
            script_key == "auto"
            and allow_auto_probe
            and self.auto_probe_installed_scripts
            and (
                not best.ok
                or not best.text.strip()
                or best.confidence < self.offline_probe_threshold
            )
        )
        if should_probe:
            installed_extras = list_installed_scripts(models_dir=self.models_dir, exclude_auto=True)
            best_score = _candidate_quality_score(best)
            best_probed_key: str | None = None

            for extra_key in installed_extras:
                candidate = self._run_single_script(img_arr, extra_key, keep_breaks)
                cand_score = _candidate_quality_score(candidate)
                if candidate.ok and candidate.text.strip() and cand_score > best_score + 0.04:
                    best = candidate
                    best_score = cand_score
                    best_probed_key = extra_key

            if best_probed_key is not None:
                profile = SCRIPT_PROFILES[best_probed_key]
                best.fallback_note = f"Auto-detected offline language pack: {profile.label}"
                best.elapsed_ms = round((time.perf_counter() - total_start) * 1000.0, 1)

        return best


def _candidate_quality_score(res: OCRResult) -> float:
    """Rank OCR candidates by confidence + non-empty meaningful character coverage."""
    if not res.ok or not res.text.strip():
        return 0.0
    non_space = len("".join(res.text.split()))
    length_bonus = min(0.05, non_space * 0.005)
    return res.confidence + length_bonus


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
