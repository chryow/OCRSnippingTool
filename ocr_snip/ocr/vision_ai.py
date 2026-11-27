"""Optional Vision AI OCR engines (Gemini, OpenAI / OpenAI-compatible, Ollama).

Provides universal multilingual OCR across all world languages, handwriting,
vertical text, mixed scripts, Markdown tables, math/LaTeX, and low-contrast captures.
"""

from __future__ import annotations

import base64
import io
import json
import re
import time
from typing import Any

import httpx
from PIL import Image

from ocr_snip.ai_client import call_ai_provider, extract_http_error_detail
from ocr_snip.config import AppConfig
from ocr_snip.language import detect_languages, language_name
from ocr_snip.ocr.base import DetectedLanguage, OCREngine, OCRResult

AI_OUTPUT_FORMATS: list[tuple[str, str]] = [
    ("text", "Plain Text"),
    ("markdown", "Markdown / Tables"),
    ("latex", "Math / LaTeX"),
]

VISION_OCR_PROMPT = """You are a precision multilingual OCR engine.
Extract ALL visible text from this image accurately and verbatim.
Rules:
1. Preserve the original language(s), script(s), spelling, accents, diacritics, and line breaks.
2. Do NOT translate, summarize, explain, or add commentary.
3. Support any writing system (Latin, CJK, Japanese, Korean, Arabic, Cyrillic, Devanagari, Thai, Hebrew, Greek, Indic, Southeast Asian, handwriting, math, code, etc.).
4. Return ONLY valid JSON with this exact schema:
{"text": "<extracted text>", "languages": [{"code": "<iso-639-1 code>", "name": "<English language name>"}]}
If there is no readable text in the image, return:
{"text": "", "languages": []}"""


def build_vision_prompt(output_format: str = "text") -> str:
    """Build the Vision AI OCR prompt tailored to the requested output format."""
    fmt = (output_format or "text").strip().lower()
    if fmt == "markdown":
        return (
            VISION_OCR_PROMPT
            + "\n5. Format structured layouts cleanly in GitHub-Flavored Markdown: "
            "convert any tables into Markdown tables (`| col |`), preserve headings (`#`), "
            "bullet/numbered lists, and wrap code blocks in fenced ``` blocks."
        )
    if fmt == "latex":
        return (
            VISION_OCR_PROMPT
            + "\n5. Convert all mathematical formulas, fractions, integrals, matrices, "
            "subscripts, superscripts, and Greek symbols into clean LaTeX (`$...$` inline "
            "or `$$...$$` for display equations), preserving surrounding prose verbatim."
        )
    return VISION_OCR_PROMPT


def _encode_image_png_base64(image: Image.Image, max_side: int = 2048) -> str:
    """Resize oversized captures gently and encode to PNG base64."""
    rgb = image.convert("RGB")
    w, h = rgb.size
    if max(w, h) > max_side:
        scale = max_side / max(w, h)
        rgb = rgb.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    rgb.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def parse_vision_ai_response(raw_text: str) -> tuple[str, list[DetectedLanguage]]:
    """Parse structured JSON from a Vision LLM, with graceful fallback to plain text."""
    cleaned = raw_text.strip()
    if not cleaned:
        return "", []

    fence_match = re.search(
        r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE
    )
    candidate = fence_match.group(1).strip() if fence_match else cleaned

    json_str = candidate
    if not json_str.startswith("{"):
        brace_start = json_str.find("{")
        brace_end = json_str.rfind("}")
        if brace_start != -1 and brace_end > brace_start:
            json_str = json_str[brace_start : brace_end + 1]

    try:
        payload = json.loads(json_str)
        if isinstance(payload, dict) and "text" in payload:
            extracted = str(payload.get("text", "")).strip()
            langs: list[DetectedLanguage] = []
            raw_langs = payload.get("languages", [])
            if isinstance(raw_langs, list):
                for item in raw_langs:
                    if isinstance(item, dict):
                        code = str(item.get("code", "")).strip().lower()
                        name = str(item.get("name", "")).strip() or language_name(code)
                        if name and name.lower() != "unknown":
                            langs.append(
                                DetectedLanguage(code=code, name=name, confidence=0.98)
                            )
                    elif isinstance(item, str) and item.strip():
                        langs.append(
                            DetectedLanguage(code="", name=item.strip(), confidence=0.95)
                        )
            if extracted and not langs:
                langs = detect_languages(extracted)
            return extracted, langs
    except json.JSONDecodeError:
        pass

    extracted = candidate
    langs = detect_languages(extracted) if extracted else []
    return extracted, langs


class VisionAIEngine(OCREngine):
    """Vision LLM OCR engine supporting Gemini, OpenAI-compatible APIs, and local Ollama."""

    name = "Vision AI"

    def __init__(self, config: AppConfig, timeout: float = 45.0) -> None:
        self.config = config
        self.timeout = timeout

    def recognize(
        self, image: Image.Image, *, output_format: str | None = None, **kwargs: Any
    ) -> OCRResult:
        provider = self.config.ai_provider.strip().lower()
        fmt = (output_format or self.config.ai_output_format or "text").strip().lower()
        prompt = build_vision_prompt(fmt)
        start = time.perf_counter()

        try:
            b64_png = _encode_image_png_base64(image)
            raw_text, label = call_ai_provider(
                self.config,
                prompt,
                image_b64=b64_png,
                temperature=0.0,
                json_mode=True,
                timeout=self.timeout,
            )
        except httpx.HTTPStatusError as exc:
            elapsed = (time.perf_counter() - start) * 1000.0
            detail = extract_http_error_detail(exc.response)
            return OCRResult(
                text="",
                engine_name=f"Vision AI ({provider})",
                confidence=0.0,
                elapsed_ms=round(elapsed, 1),
                error=f"{provider.title()} API HTTP {exc.response.status_code}: {detail}",
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000.0
            return OCRResult(
                text="",
                engine_name=f"Vision AI ({provider})",
                confidence=0.0,
                elapsed_ms=round(elapsed, 1),
                error=str(exc),
            )

        elapsed = (time.perf_counter() - start) * 1000.0
        text, langs = parse_vision_ai_response(raw_text)
        fmt_suffix = f" [{fmt}]" if fmt != "text" else ""
        return OCRResult(
            text=text,
            engine_name=f"{label}{fmt_suffix}",
            confidence=0.98 if text else 0.0,
            languages=langs,
            elapsed_ms=round(elapsed, 1),
            script_used="all_languages",
        )
