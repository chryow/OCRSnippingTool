"""CLI and Desktop entry point for OCRSnippingTool."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ocr_snip import __app_name__, __version__
from ocr_snip.config import AppConfig


def _run_cli_image(args: argparse.Namespace) -> int:
    from ocr_snip.ai_client import close_http_client
    from ocr_snip.ocr.manager import OCRManager
    from ocr_snip.security import safe_open_image

    img_path = Path(args.image)
    if not img_path.exists():
        print(f"Error: file not found: {img_path}", file=sys.stderr)
        return 1

    config = AppConfig.load()
    if args.mode:
        config.engine_mode = args.mode
    if args.script:
        config.local_script = args.script

    manager = OCRManager(config)
    try:
        image = safe_open_image(img_path)
    except Exception as exc:
        print(f"Error: could not open image: {exc}", file=sys.stderr)
        return 1
    result = manager.recognize(
        image,
        force_engine=args.mode,
        script_override=args.script,
        ai_output_format=args.ai_format,
    )

    if args.unwrap and result.ok and result.text.strip():
        from ocr_snip.formatting import unwrap_paragraphs

        result.text = unwrap_paragraphs(result.text)

    translation = None
    if args.translate and result.ok and result.text.strip():
        from ocr_snip.translate import Translator

        translation = Translator(config).translate(result.text, target_lang=args.translate)

    if args.json:
        payload = {
            "ok": result.ok,
            "text": result.text,
            "engine": result.engine_name,
            "confidence": result.confidence,
            "elapsed_ms": result.elapsed_ms,
            "languages": [
                {
                    "code": lang.code,
                    "name": lang.name,
                    "script": lang.script,
                    "confidence": lang.confidence,
                }
                for lang in result.languages
            ],
            "fallback_note": result.fallback_note,
            "error": result.error,
        }
        if translation is not None:
            payload["translation"] = {
                "ok": translation.ok,
                "text": translation.translated_text,
                "target_language": translation.target_language,
                "provider": translation.provider_name,
                "error": translation.error,
            }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        if not result.ok:
            print(f"Error: {result.error}", file=sys.stderr)
            return 1
        print(
            f"[Language: {result.language_summary} | Engine: {result.engine_name} | "
            f"Confidence: {result.confidence:.0%} | {result.elapsed_ms:.0f} ms]"
        )
        if result.fallback_note:
            print(f"[Note: {result.fallback_note}]")
        print(result.text)
        if translation is not None:
            if translation.ok:
                print(
                    f"\n[Translation → {translation.target_language} | "
                    f"{translation.provider_name}]"
                )
                print(translation.translated_text)
            else:
                print(f"\n[Translation error: {translation.error}]", file=sys.stderr)

    close_http_client()
    return 0 if result.ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ocr-snip",
        description="OCRSnippingTool — Snipping Tool that extracts multilingual text using AI/ML OCR.",
    )
    parser.add_argument("--version", action="version", version=f"{__app_name__} {__version__}")
    parser.add_argument(
        "--snip",
        action="store_true",
        help="Immediately open the snipping overlay on launch.",
    )
    parser.add_argument(
        "--image",
        type=str,
        default=None,
        help="Run headless OCR on an image file and print extracted text.",
    )
    parser.add_argument(
        "--mode",
        choices=["hybrid", "local", "vision_ai"],
        default=None,
        help="Override OCR engine mode (used with --image).",
    )
    parser.add_argument(
        "--script",
        type=str,
        default=None,
        help="Override local OCR script profile (e.g. auto, latin, korean, eslav, cyrillic, arabic, devanagari, thai).",
    )
    parser.add_argument(
        "--ai-format",
        choices=["text", "markdown", "latex"],
        default=None,
        help="Vision AI output format (text, markdown tables/code, or math latex).",
    )
    parser.add_argument(
        "--unwrap",
        action="store_true",
        help="Unwrap hard line breaks into flowing paragraphs (ideal for PDFs/articles).",
    )
    parser.add_argument(
        "--translate",
        type=str,
        default=None,
        help="Translate extracted text to target language code (e.g. en, id, es, ja).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON result (used with --image).",
    )

    args = parser.parse_args(argv)

    if args.image:
        return _run_cli_image(args)

    from ocr_snip.ui.app import run_gui

    return run_gui(start_with_snip=args.snip)


if __name__ == "__main__":
    raise SystemExit(main())
