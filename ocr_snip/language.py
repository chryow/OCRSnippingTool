"""Multilingual script and language detection for extracted OCR text.

Combines Unicode script inspection (reliable even for very short text and mixed
scripts) with statistical n-gram language detection (`langdetect`) to accurately
identify languages across writing systems worldwide.
"""

from __future__ import annotations

import unicodedata
from collections import Counter
from dataclasses import dataclass


@dataclass
class DetectedLanguage:
    """Represents a detected language in the extracted text."""

    code: str          # ISO 639-1 / BCP-47 code, e.g. "en", "ja", "zh-cn", "ar"
    name: str          # Human-readable name, e.g. "English", "Japanese"
    script: str = ""   # Unicode script family, e.g. "Latin", "Han", "Hiragana/Katakana"
    confidence: float = 1.0

    @property
    def label(self) -> str:
        if self.code:
            return f"{self.name} ({self.code})"
        return self.name

# Comprehensive ISO-639-1 / BCP-47 -> human-readable language name mapping
LANGUAGE_NAMES: dict[str, str] = {
    "af": "Afrikaans",
    "am": "Amharic",
    "ar": "Arabic",
    "az": "Azerbaijani",
    "be": "Belarusian",
    "bg": "Bulgarian",
    "bn": "Bengali",
    "bo": "Tibetan",
    "bs": "Bosnian",
    "ca": "Catalan",
    "cs": "Czech",
    "cy": "Welsh",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "en": "English",
    "eo": "Esperanto",
    "es": "Spanish",
    "et": "Estonian",
    "eu": "Basque",
    "fa": "Persian",
    "fi": "Finnish",
    "fr": "French",
    "ga": "Irish",
    "gl": "Galician",
    "gu": "Gujarati",
    "he": "Hebrew",
    "hi": "Hindi",
    "hr": "Croatian",
    "hu": "Hungarian",
    "hy": "Armenian",
    "id": "Indonesian",
    "is": "Icelandic",
    "it": "Italian",
    "ja": "Japanese",
    "ka": "Georgian",
    "kk": "Kazakh",
    "km": "Khmer",
    "kn": "Kannada",
    "ko": "Korean",
    "lo": "Lao",
    "lt": "Lithuanian",
    "lv": "Latvian",
    "mk": "Macedonian",
    "ml": "Malayalam",
    "mn": "Mongolian",
    "mr": "Marathi",
    "ms": "Malay",
    "mt": "Maltese",
    "my": "Burmese",
    "ne": "Nepali",
    "nl": "Dutch",
    "no": "Norwegian",
    "pa": "Punjabi",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "si": "Sinhala",
    "sk": "Slovak",
    "sl": "Slovenian",
    "so": "Somali",
    "sq": "Albanian",
    "sr": "Serbian",
    "sv": "Swedish",
    "sw": "Swahili",
    "ta": "Tamil",
    "te": "Telugu",
    "th": "Thai",
    "tl": "Tagalog",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "ur": "Urdu",
    "vi": "Vietnamese",
    "zh": "Chinese",
    "zh-cn": "Chinese (Simplified)",
    "zh-tw": "Chinese (Traditional)",
}

# Script -> default fallback language code when text is too short for n-gram detection
SCRIPT_DEFAULT_LANG: dict[str, tuple[str, str]] = {
    "Japanese": ("ja", "Japanese"),
    "Hangul": ("ko", "Korean"),
    "Han": ("zh-cn", "Chinese"),
    "Thai": ("th", "Thai"),
    "Greek": ("el", "Greek"),
    "Hebrew": ("he", "Hebrew"),
    "Devanagari": ("hi", "Hindi"),
    "Bengali": ("bn", "Bengali"),
    "Tamil": ("ta", "Tamil"),
    "Telugu": ("te", "Telugu"),
    "Gujarati": ("gu", "Gujarati"),
    "Gurmukhi": ("pa", "Punjabi"),
    "Kannada": ("kn", "Kannada"),
    "Malayalam": ("ml", "Malayalam"),
    "Sinhala": ("si", "Sinhala"),
    "Myanmar": ("my", "Burmese"),
    "Khmer": ("km", "Khmer"),
    "Lao": ("lo", "Lao"),
    "Georgian": ("ka", "Georgian"),
    "Armenian": ("hy", "Armenian"),
    "Ethiopic": ("am", "Amharic"),
    "Tibetan": ("bo", "Tibetan"),
    "Arabic": ("ar", "Arabic"),
    "Cyrillic": ("ru", "Russian"),
    "Latin": ("en", "English"),
}

# Expected script family for each langdetect ISO code (helps prevent impossible mismatches)
LANG_EXPECTED_SCRIPT: dict[str, str] = {
    "ar": "Arabic",
    "fa": "Arabic",
    "ur": "Arabic",
    "bg": "Cyrillic",
    "mk": "Cyrillic",
    "ru": "Cyrillic",
    "uk": "Cyrillic",
    "be": "Cyrillic",
    "kk": "Cyrillic",
    "sr": "Cyrillic",
    "el": "Greek",
    "he": "Hebrew",
    "hi": "Devanagari",
    "mr": "Devanagari",
    "ne": "Devanagari",
    "bn": "Bengali",
    "gu": "Gujarati",
    "kn": "Kannada",
    "ml": "Malayalam",
    "pa": "Gurmukhi",
    "ta": "Tamil",
    "te": "Telugu",
    "th": "Thai",
    "ko": "Hangul",
    "ja": "Japanese",
    "zh-cn": "Han",
    "zh-tw": "Han",
    "zh": "Han",
}


def _classify_char_script(ch: str) -> str | None:
    """Map a single Unicode letter to its script family."""
    cp = ord(ch)
    # Fast range checks for most common scripts
    if 0x3040 <= cp <= 0x30FF or 0x31F0 <= cp <= 0x31FF or 0xFF65 <= cp <= 0xFF9F:
        return "Japanese"  # Hiragana / Katakana
    if 0xAC00 <= cp <= 0xD7AF or 0x1100 <= cp <= 0x11FF or 0x3130 <= cp <= 0x318F:
        return "Hangul"
    if (
        0x4E00 <= cp <= 0x9FFF
        or 0x3400 <= cp <= 0x4DBF
        or 0x20000 <= cp <= 0x2A6DF
        or 0xF900 <= cp <= 0xFAFF
    ):
        return "Han"
    if 0x0400 <= cp <= 0x052F:
        return "Cyrillic"
    if 0x0600 <= cp <= 0x06FF or 0x0750 <= cp <= 0x077F or 0x08A0 <= cp <= 0x08FF:
        return "Arabic"
    if 0x0900 <= cp <= 0x097F:
        return "Devanagari"
    if 0x0E00 <= cp <= 0x0E7F:
        return "Thai"
    if 0x0370 <= cp <= 0x03FF or 0x1F00 <= cp <= 0x1FFF:
        return "Greek"
    if 0x0590 <= cp <= 0x05FF:
        return "Hebrew"
    if 0x0980 <= cp <= 0x09FF:
        return "Bengali"
    if 0x0B80 <= cp <= 0x0BFF:
        return "Tamil"
    if 0x0C00 <= cp <= 0x0C7F:
        return "Telugu"
    if 0x0A80 <= cp <= 0x0AFF:
        return "Gujarati"
    if 0x0A00 <= cp <= 0x0A7F:
        return "Gurmukhi"
    if 0x0C80 <= cp <= 0x0CFF:
        return "Kannada"
    if 0x0D00 <= cp <= 0x0D7F:
        return "Malayalam"
    if 0x0D80 <= cp <= 0x0DFF:
        return "Sinhala"
    if 0x1000 <= cp <= 0x109F:
        return "Myanmar"
    if 0x1780 <= cp <= 0x17FF:
        return "Khmer"
    if 0x0E80 <= cp <= 0x0EFF:
        return "Lao"
    if 0x10A0 <= cp <= 0x10FF:
        return "Georgian"
    if 0x0530 <= cp <= 0x058F:
        return "Armenian"
    if 0x1200 <= cp <= 0x137F:
        return "Ethiopic"
    if 0x0F00 <= cp <= 0x0FFF:
        return "Tibetan"
    if (0x0041 <= cp <= 0x024F) or (0x1E00 <= cp <= 0x1EFF):
        return "Latin"

    # Fallback to Unicode character name for extended blocks
    cat = unicodedata.category(ch)
    if not cat.startswith("L"):
        return None
    name = unicodedata.name(ch, "")
    if "LATIN" in name:
        return "Latin"
    if "CYRILLIC" in name:
        return "Cyrillic"
    if "ARABIC" in name:
        return "Arabic"
    if "GREEK" in name:
        return "Greek"
    if "CJK" in name:
        return "Han"
    return None


def detect_scripts(text: str) -> Counter[str]:
    """Count occurrences of each Unicode script across letters in `text`."""
    counts: Counter[str] = Counter()
    for ch in text:
        script = _classify_char_script(ch)
        if script:
            counts[script] += 1
    return counts


def language_name(code: str) -> str:
    """Return a clean human-readable name for a language code."""
    normalized = code.strip().lower().replace("_", "-")
    if normalized in LANGUAGE_NAMES:
        return LANGUAGE_NAMES[normalized]
    base = normalized.split("-")[0]
    if base in LANGUAGE_NAMES:
        return LANGUAGE_NAMES[base]
    return code.upper() if code else "Unknown"


_LANGDETECT_FN = None


def _detect_with_langdetect(text: str) -> list[tuple[str, float]]:
    """Run statistical language detection safely; returns [(lang_code, prob), ...]."""
    global _LANGDETECT_FN
    try:
        if _LANGDETECT_FN is None:
            from langdetect import DetectorFactory, detect_langs

            DetectorFactory.seed = 0
            _LANGDETECT_FN = detect_langs
        preds = _LANGDETECT_FN(text)
        return [(p.lang.lower(), float(p.prob)) for p in preds]
    except Exception:
        return []


def detect_languages(text: str, max_results: int = 3) -> list[DetectedLanguage]:
    """Detect one or more languages present in `text`.

    Handles:
    - Single-language text in any Unicode script
    - Very short snippets (1-5 chars) using script heuristics
    - Mixed-script text (e.g., Japanese + English, Chinese + English, Arabic + Latin)
    """
    stripped = text.strip()
    if not stripped:
        return []

    scripts = detect_scripts(stripped)
    if not scripts:
        return []

    total_letters = sum(scripts.values())
    detected: list[DetectedLanguage] = []
    seen_codes: set[str] = set()

    # Special rule: if Hiragana/Katakana appears alongside Han, treat combined CJK as Japanese
    has_kana = scripts.get("Japanese", 0) > 0
    if has_kana and scripts.get("Han", 0) > 0:
        scripts["Japanese"] += scripts.pop("Han")

    # Sort scripts by character count descending
    ranked_scripts = scripts.most_common()

    for script, count in ranked_scripts:
        share = count / total_letters
        # Ignore tiny stray noise characters in multi-script text (e.g. a single trademark letter)
        if len(ranked_scripts) > 1 and share < 0.08 and count < 4:
            continue

        # Extract only characters from this script + spaces for focused statistical detection
        if script in ("Latin", "Cyrillic", "Arabic", "Devanagari", "Han"):
            segment = _extract_script_segment(stripped, script)
            lang_preds = _detect_with_langdetect(segment) if len(segment) >= 6 else []

            matched = None
            for code, prob in lang_preds:
                expected = LANG_EXPECTED_SCRIPT.get(code, "Latin")
                if expected == script:
                    matched = (code, prob)
                    break

            if matched:
                code, prob = matched
                if code not in seen_codes:
                    seen_codes.add(code)
                    detected.append(
                        DetectedLanguage(
                            code=code,
                            name=language_name(code),
                            script=script,
                            confidence=round(min(1.0, prob * (0.5 + 0.5 * share)), 3),
                        )
                    )
                continue

        # Unambiguous script (Hangul, Japanese, Thai, Greek, Hebrew, Tamil, etc.)
        # or short snippet fallback
        code, name = SCRIPT_DEFAULT_LANG.get(script, ("und", script))
        if code not in seen_codes:
            seen_codes.add(code)
            detected.append(
                DetectedLanguage(
                    code=code,
                    name=name,
                    script=script,
                    confidence=round(min(1.0, 0.75 + 0.25 * share), 3),
                )
            )

        if len(detected) >= max_results:
            break

    return detected[:max_results]


def _extract_script_segment(text: str, target_script: str) -> str:
    """Keep characters matching `target_script` along with whitespace and basic punctuation."""
    chars: list[str] = []
    for ch in text:
        if ch.isspace() or ch in ".,!?;:'\"-()":
            chars.append(ch)
        else:
            sc = _classify_char_script(ch)
            if sc == target_script:
                chars.append(ch)
    return "".join(chars).strip()
