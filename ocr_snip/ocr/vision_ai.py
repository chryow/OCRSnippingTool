"""Optional Vision AI OCR engines (Gemini, OpenAI / OpenAI-compatible, Ollama).

Provides universal multilingual OCR across all world languages, handwriting,
vertical text, mixed scripts, math/code, and low-contrast screenshots.
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

from ocr_snip.config import AppConfig
from ocr_snip.language import detect_languages, language_name
from ocr_snip.ocr.base import DetectedLanguage, OCREngine, OCRResult

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

    # Strip optional markdown code fences (```json ... ```)
    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    candidate = fence_match.group(1).strip() if fence_match else cleaned

    # Try parsing direct JSON or first JSON object inside the response
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
                            DetectedLanguage(
                                code="",
                                name=item.strip(),
                                confidence=0.95,
                            )
                        )
            if extracted and not langs:
                langs = detect_languages(extracted)
            return extracted, langs
    except json.JSONDecodeError:
        pass

    # Fallback: treat model output as raw extracted text
    extracted = candidate
    langs = detect_languages(extracted) if extracted else []
    return extracted, langs


class VisionAIEngine(OCREngine):
    """Vision LLM OCR engine supporting Gemini, OpenAI-compatible APIs, and local Ollama."""

    name = "Vision AI"

    def __init__(self, config: AppConfig, timeout: float = 45.0) -> None:
        self.config = config
        self.timeout = timeout

    def recognize(self, image: Image.Image, **kwargs: Any) -> OCRResult:
        provider = self.config.ai_provider.strip().lower()
        start = time.perf_counter()

        try:
            b64_png = _encode_image_png_base64(image)
            if provider == "gemini":
                raw_text, label = self._call_gemini(b64_png)
            elif provider == "openai":
                raw_text, label = self._call_openai(b64_png)
            elif provider == "ollama":
                raw_text, label = self._call_ollama(b64_png)
            else:
                raise ValueError(f"Unsupported Vision AI provider: {provider}")
        except httpx.HTTPStatusError as exc:
            elapsed = (time.perf_counter() - start) * 1000.0
            detail = _extract_http_error_detail(exc.response)
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
        return OCRResult(
            text=text,
            engine_name=label,
            confidence=0.98 if text else 0.0,
            languages=langs,
            elapsed_ms=round(elapsed, 1),
            script_used="all_languages",
        )

    def _call_gemini(self, b64_png: str) -> tuple[str, str]:
        api_key = self.config.effective_gemini_key()
        if not api_key:
            raise RuntimeError(
                "Gemini API key not set. Add it in Settings or set GEMINI_API_KEY."
            )
        model = self.config.gemini_model.strip() or "gemini-2.5-flash"
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        )
        headers = {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        }
        body = {
            "contents": [
                {
                    "parts": [
                        {"text": VISION_OCR_PROMPT},
                        {"inline_data": {"mime_type": "image/png", "data": b64_png}},
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.0,
                "responseMimeType": "application/json",
            },
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()

        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini returned no candidates.")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
        return text, f"Gemini ({model})"

    def _call_openai(self, b64_png: str) -> tuple[str, str]:
        api_key = self.config.effective_openai_key()
        if not api_key:
            raise RuntimeError(
                "OpenAI API key not set. Add it in Settings or set OPENAI_API_KEY."
            )
        base_url = (self.config.openai_base_url.strip() or "https://api.openai.com/v1").rstrip("/")
        model = self.config.openai_model.strip() or "gpt-4o-mini"
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        body = {
            "model": model,
            "temperature": 0.0,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISION_OCR_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64_png}"},
                        },
                    ],
                }
            ],
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            data = resp.json()

        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("OpenAI API returned no choices.")
        content = choices[0].get("message", {}).get("content", "")
        if isinstance(content, list):
            content = "".join(
                block.get("text", "") for block in content if isinstance(block, dict)
            )
        return str(content), f"OpenAI ({model})"

    def _call_ollama(self, b64_png: str) -> tuple[str, str]:
        base_url = (self.config.ollama_base_url.strip() or "http://localhost:11434").rstrip("/")
        model = self.config.ollama_model.strip() or "qwen2.5vl:7b"
        url = f"{base_url}/api/chat"
        body = {
            "model": model,
            "stream": False,
            "options": {"temperature": 0.0},
            "messages": [
                {
                    "role": "user",
                    "content": VISION_OCR_PROMPT,
                    "images": [b64_png],
                }
            ],
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, json=body)
            resp.raise_for_status()
            data = resp.json()

        message = data.get("message", {})
        content = str(message.get("content", ""))
        return content, f"Ollama ({model})"


def _extract_http_error_detail(response: httpx.Response) -> str:
    """Extract a concise, safe error message from a failed HTTP API response."""
    try:
        payload = response.json()
        if isinstance(payload, dict):
            err = payload.get("error")
            if isinstance(err, dict) and err.get("message"):
                return str(err["message"])
            if isinstance(err, str) and err:
                return err
    except Exception:
        pass
    return response.reason_phrase or "Request failed"

