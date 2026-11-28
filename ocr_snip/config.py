"""Persistent application configuration stored in the user's config directory."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def get_config_dir() -> Path:
    """Return the platform-appropriate configuration directory."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "OCRSnippingTool"


def get_config_path() -> Path:
    """Return the path to the persistent JSON configuration file."""
    return get_config_dir() / "config.json"


def get_models_dir() -> Path:
    """Return a user-writable directory for caching downloaded ONNX OCR models.

    Essential for frozen PyInstaller executables (.exe / .app) where the bundled
    package directory is read-only or temporary.
    """
    models_dir = get_config_dir() / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir


DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"

RECOMMENDED_GEMINI_MODELS: tuple[str, ...] = (
    "gemini-3.8-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.1-flash-lite",
)

DEPRECATED_GEMINI_MODELS: frozenset[str] = frozenset(
    {
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-flash-exp",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
    }
)


@dataclass
class AppConfig:
    """User-configurable settings for OCRSnippingTool."""

    # Global snip hotkey (pynput format, e.g. "<ctrl>+<shift>+x" or "<cmd>+<shift>+o")
    hotkey: str = "<ctrl>+<shift>+x"

    # Engine mode: "hybrid" | "local" | "vision_ai"
    # - local: Offline RapidOCR (ONNX deep-learning OCR) only
    # - vision_ai: Cloud/Local Vision LLM (Gemini / OpenAI / Ollama) only
    # - hybrid: Fast offline RapidOCR first; automatically falls back to Vision AI
    #           when confidence is low, text is empty, or user clicks "Enhance with AI"
    engine_mode: str = "hybrid"

    # Local OCR script profile:
    # "auto" (runs universal multi-script + auto-probes installed offline packs when low confidence),
    # or explicit script key: "latin", "korean", "eslav", "cyrillic",
    # "arabic", "devanagari", "thai", "greek", "tamil", "telugu"
    local_script: str = "auto"
    auto_probe_installed_scripts: bool = True
    offline_probe_threshold: float = 0.72

    # Hybrid fallback confidence threshold (0.0 - 1.0): if local OCR average confidence
    # is below this and Vision AI is configured, automatically refine with Vision AI
    hybrid_confidence_threshold: float = 0.65

    # Vision AI provider: "gemini" | "openai" | "ollama"
    ai_provider: str = "gemini"
    # Vision AI output format: "text" | "markdown" | "latex"
    ai_output_format: str = "text"

    # API keys / endpoints (also reads GEMINI_API_KEY / OPENAI_API_KEY env vars as fallback)
    gemini_api_key: str = ""
    gemini_model: str = DEFAULT_GEMINI_MODEL

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5vl:7b"

    # Workflow preferences
    auto_copy: bool = True
    show_popup: bool = True
    popup_auto_close_seconds: int = 0  # 0 = stay open until dismissed
    popup_width: int = 720
    popup_height: int = 490
    preserve_line_breaks: bool = True
    history_max_entries: int = 100

    # Built-in 1-click translation preferences
    translate_source_lang: str = "auto"  # "auto" (auto-detect) or explicit ISO/BCP-47 code
    translate_target_lang: str = "en"
    translation_provider: str = "auto"  # "auto" | "google_free" | "ai"
    auto_translate: bool = False

    # Extra provider-specific or future options
    extra: dict[str, Any] = field(default_factory=dict)

    def effective_gemini_key(self) -> str:
        return self.gemini_api_key.strip() or os.environ.get("GEMINI_API_KEY", "").strip()

    def effective_openai_key(self) -> str:
        return self.openai_api_key.strip() or os.environ.get("OPENAI_API_KEY", "").strip()

    def is_vision_ai_configured(self) -> bool:
        """Return True if the selected Vision AI provider has credentials/endpoint ready."""
        if self.ai_provider == "gemini":
            return bool(self.effective_gemini_key())
        if self.ai_provider == "openai":
            return bool(self.effective_openai_key())
        if self.ai_provider == "ollama":
            return bool(self.ollama_base_url.strip() and self.ollama_model.strip())
        return False

    def save(self, path: Path | None = None) -> Path:
        from ocr_snip.security import atomic_write_text

        target = path or get_config_path()
        content = json.dumps(asdict(self), indent=2, ensure_ascii=False)
        return atomic_write_text(target, content, private=True)

    @classmethod
    def load(cls, path: Path | None = None) -> "AppConfig":
        target = path or get_config_path()
        if not target.exists():
            return cls()
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        valid_fields = set(cls.__dataclass_fields__.keys())
        filtered = {k: v for k, v in raw.items() if k in valid_fields}
        gemini_model = str(filtered.get("gemini_model", "")).strip().lower()
        if gemini_model in DEPRECATED_GEMINI_MODELS:
            filtered["gemini_model"] = DEFAULT_GEMINI_MODEL
        return cls(**filtered)
