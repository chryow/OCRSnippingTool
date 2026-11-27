"""Built-in 1-click translation for extracted OCR text.

Supports:
- Configured AI providers (Google Gemini, OpenAI / Compatible, local Ollama)
- Zero-config free web translation fallback (`translate.googleapis.com`) so
  1-click translation works immediately without any API keys.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from ocr_snip.ai_client import call_ai_provider, extract_http_error_detail
from ocr_snip.config import AppConfig
from ocr_snip.language import language_name

# Curated list of popular target languages shown in the floating popup & settings
TARGET_LANGUAGES: list[tuple[str, str]] = [
    ("en", "English"),
    ("id", "Indonesian"),
    ("es", "Spanish"),
    ("fr", "French"),
    ("de", "German"),
    ("ja", "Japanese"),
    ("zh-CN", "Chinese (Simplified)"),
    ("zh-TW", "Chinese (Traditional)"),
    ("ko", "Korean"),
    ("ru", "Russian"),
    ("ar", "Arabic"),
    ("hi", "Hindi"),
    ("pt", "Portuguese"),
    ("it", "Italian"),
    ("nl", "Dutch"),
    ("tr", "Turkish"),
    ("vi", "Vietnamese"),
    ("th", "Thai"),
    ("pl", "Polish"),
    ("uk", "Ukrainian"),
    ("el", "Greek"),
    ("he", "Hebrew"),
    ("sv", "Swedish"),
    ("ms", "Malay"),
    ("tl", "Tagalog / Filipino"),
]


@dataclass
class TranslationResult:
    """Unified output from the translation engine."""

    translated_text: str
    target_language: str
    source_language: str = ""
    provider_name: str = ""
    elapsed_ms: float = 0.0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


class Translator:
    """Translates extracted text using AI (if configured) or free web translation."""

    def __init__(self, config: AppConfig, timeout: float = 30.0) -> None:
        self.config = config
        self.timeout = timeout

    def update_config(self, config: AppConfig) -> None:
        self.config = config

    def translate(
        self,
        text: str,
        target_lang: str | None = None,
        *,
        provider_override: str | None = None,
    ) -> TranslationResult:
        """Translate `text` into `target_lang` (ISO/BCP-47 code like 'en', 'id', 'ja')."""
        cleaned = text.strip()
        target = (target_lang or self.config.translate_target_lang or "en").strip()
        target_label = language_name(target)

        if not cleaned:
            return TranslationResult(
                translated_text="",
                target_language=target_label,
                error="No text to translate.",
            )

        mode = (provider_override or self.config.translation_provider or "auto").strip().lower()
        start = time.perf_counter()

        try:
            if mode == "ai" or (mode == "auto" and self.config.is_vision_ai_configured()):
                try:
                    prompt = (
                        f"Translate the following text accurately into {target_label}. "
                        "Preserve line breaks, formatting, and meaning. "
                        "Return ONLY the translated text without quotes, notes, or explanations.\n\n"
                        f"{cleaned}"
                    )
                    translated, provider_label = call_ai_provider(
                        self.config,
                        prompt,
                        temperature=0.1,
                        timeout=self.timeout,
                    )
                    elapsed = (time.perf_counter() - start) * 1000.0
                    return TranslationResult(
                        translated_text=translated,
                        target_language=target_label,
                        provider_name=provider_label,
                        elapsed_ms=round(elapsed, 1),
                    )
                except Exception:
                    if mode == "ai":
                        raise

            translated, detected_src = self._translate_google_free(cleaned, target)
            elapsed = (time.perf_counter() - start) * 1000.0
            return TranslationResult(
                translated_text=translated,
                target_language=target_label,
                source_language=language_name(detected_src) if detected_src else "",
                provider_name="Free Translate",
                elapsed_ms=round(elapsed, 1),
            )
        except httpx.HTTPStatusError as exc:
            elapsed = (time.perf_counter() - start) * 1000.0
            detail = extract_http_error_detail(exc.response)
            return TranslationResult(
                translated_text="",
                target_language=target_label,
                elapsed_ms=round(elapsed, 1),
                error=f"Translation HTTP {exc.response.status_code}: {detail}",
            )
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000.0
            return TranslationResult(
                translated_text="",
                target_language=target_label,
                elapsed_ms=round(elapsed, 1),
                error=f"Translation failed: {exc}",
            )

    def _translate_google_free(self, text: str, target_code: str) -> tuple[str, str]:
        """Translate via Google's lightweight public GTX endpoint (no API key needed)."""
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "auto",
            "tl": target_code,
            "dt": "t",
            "q": text,
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()

        if not isinstance(data, list) or not data or not isinstance(data[0], list):
            raise RuntimeError("Unexpected translation response format.")

        segments = [
            str(seg[0]) for seg in data[0] if isinstance(seg, list) and seg and seg[0] is not None
        ]
        translated = "".join(segments).strip()
        detected_src = str(data[2]) if len(data) > 2 and isinstance(data[2], str) else ""
        return translated, detected_src
