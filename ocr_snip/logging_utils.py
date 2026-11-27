"""Rotating diagnostic file logging with secret redaction and friendly crash reporting."""

from __future__ import annotations

import logging
import os
import sys
import threading
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ocr_snip.config import get_config_dir
from ocr_snip.security import ensure_private_dir, redact_secrets

LOGGER_NAME = "ocr_snip"


class SecretRedactingFilter(logging.Filter):
    """Scrubs API keys and bearer tokens before any log record is written to disk."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
            redacted = redact_secrets(rendered)
            if redacted != rendered:
                record.msg = redacted
                record.args = ()
        except Exception:
            pass
        return True


def get_logs_dir() -> Path:
    """Return the user-writable private logs directory (0o700 on POSIX)."""
    return ensure_private_dir(get_config_dir() / "logs")


def get_log_file_path() -> Path:
    """Return the path to the rotating application log file."""
    return get_logs_dir() / "app.log"


def setup_logging(log_file: Path | None = None, level: int = logging.INFO) -> logging.Logger:
    """Configure a UTF-8 rotating file logger with secret redaction and 0o600 permissions."""
    target = log_file or get_log_file_path()
    ensure_private_dir(target.parent)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)

    resolved_target = str(target.resolve())
    for handler in logger.handlers:
        if isinstance(handler, RotatingFileHandler) and handler.baseFilename == resolved_target:
            return logger

    file_handler = RotatingFileHandler(
        target,
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    if os.name == "posix" and target.exists():
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    file_handler.addFilter(SecretRedactingFilter())
    logger.addHandler(file_handler)
    return logger


def install_crash_handler(gui: bool = True) -> None:
    """Log uncaught main-thread and background-thread exceptions safely to the log file."""
    logger = logging.getLogger(LOGGER_NAME)

    def _sys_excepthook(exc_type, exc_value, exc_tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return

        tb_text = redact_secrets("".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
        logger.critical("Unhandled exception:\n%s", tb_text)

        if gui:
            try:
                from PyQt6.QtWidgets import QApplication, QMessageBox

                if QApplication.instance() is not None:
                    log_path = get_log_file_path()
                    safe_msg = redact_secrets(str(exc_value))
                    QMessageBox.critical(
                        None,
                        "OCRSnippingTool — Unexpected Error",
                        f"An unexpected error occurred:\n\n{safe_msg}\n\n"
                        f"Diagnostic details have been saved to:\n{log_path}",
                    )
            except Exception:
                pass

        sys.__excepthook__(exc_type, exc_value, exc_tb)

    def _thread_excepthook(args: threading.ExceptHookArgs) -> None:
        tb_text = redact_secrets(
            "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
        )
        logger.critical("Unhandled thread exception (%s):\n%s", args.thread, tb_text)

    sys.excepthook = _sys_excepthook
    threading.excepthook = _thread_excepthook
