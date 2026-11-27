"""OCR and Vision AI engines for OCRSnippingTool."""

from ocr_snip.ocr.base import DetectedLanguage, OCREngine, OCRLine, OCRResult
from ocr_snip.ocr.local_rapidocr import SCRIPT_PROFILES, LocalRapidOCREngine
from ocr_snip.ocr.manager import OCRManager
from ocr_snip.ocr.vision_ai import VisionAIEngine

__all__ = [
    "DetectedLanguage",
    "LocalRapidOCREngine",
    "OCREngine",
    "OCRLine",
    "OCRManager",
    "OCRResult",
    "SCRIPT_PROFILES",
    "VisionAIEngine",
]
