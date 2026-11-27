"""Base types and interfaces for OCR engines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Sequence

from PIL import Image

from ocr_snip.language import DetectedLanguage


@dataclass
class OCRLine:
    """A single recognized line/region of text."""

    text: str
    confidence: float = 1.0
    bbox: list[list[float]] = field(default_factory=list)


@dataclass
class OCRResult:
    """Unified output from any OCR or Vision AI engine."""

    text: str
    engine_name: str
    confidence: float = 0.0
    lines: list[OCRLine] = field(default_factory=list)
    languages: list[DetectedLanguage] = field(default_factory=list)
    elapsed_ms: float = 0.0
    script_used: str = ""
    fallback_note: str = ""
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def primary_language(self) -> DetectedLanguage | None:
        return self.languages[0] if self.languages else None

    @property
    def language_summary(self) -> str:
        if not self.languages:
            return "Unknown"
        if len(self.languages) == 1:
            return self.languages[0].name
        return ", ".join(lang.name for lang in self.languages[:3])


class OCREngine(ABC):
    """Abstract base class for OCR / Vision AI backends."""

    name: str = "base"

    @abstractmethod
    def recognize(self, image: Image.Image, **kwargs) -> OCRResult:
        """Extract text and metadata from a PIL Image."""


def join_lines(lines: Sequence[OCRLine], preserve_breaks: bool = True) -> str:
    """Join OCR lines into clean output text."""
    cleaned = [line.text.strip() for line in lines if line.text and line.text.strip()]
    separator = "\n" if preserve_breaks else " "
    return separator.join(cleaned)
