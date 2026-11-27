"""Rotating diagnostic file logging and friendly unhandled-crash reporting."""

from __future__ import annotations

import logging
import sys
import threading
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ocr_snip.config import get_config_dir

LOGGER_NAME = "ocr_snip"


def get_logs_dir() -> Path:
    """Return the user-writable logs directory."""
    logs_dir = get_config_dir() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def get_log_file_path() -> Path:
    """Return the path to the rotating application log file."""
    return get_logs_dir() / "app.log"


def setup_logging(log_file: Path | None = None, level: int = logging.INFO) -> logging.Logger:
    """Configure a UTF-8 rotating file logger for diagnostics and crash reports."""
    target = log_file or get_log_file_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)

    # Avoid duplicating handlers if called multiple times
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
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger


def install_crash_handler(gui: bool = True) -> None:
    """Log uncaught main-thread and background-thread exceptions to the log file."""
    logger = logging.getLogger(LOGGER_NAME)

    def _sys_excepthook(exc_type, exc_value, exc_tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return

        tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.critical("Unhandled exception:\n%s", tb_text)

        if gui:
            try:
                from PyQt6.QtWidgets import QApplication, QMessageBox

                if QApplication.instance() is not None:
                    log_path = get_log_file_path()
                    QMessageBox.critical(
                        None,
                        "OCRSnippingTool — Unexpected Error",
                        f"An unexpected error occurred:\n\n{exc_value}\n\n"
                        f"Diagnostic details have been saved to:\n{log_path}",
                    )
            except Exception:
                pass

        sys.__excepthook__(exc_type, exc_value, exc_tb)

    def _thread_excepthook(args: threading.ExceptHookArgs) -> None:
        tb_text = "".join(
            traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
        )
        logger.critical("Unhandled thread exception (%s):\n%s", args.thread, tb_text)

    sys.excepthook = _sys_excepthook
    threading.excepthook = _thread_excepthook
