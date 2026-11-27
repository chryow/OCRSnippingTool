"""Tests for diagnostic rotating logging and cross-platform single-instance guard."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from ocr_snip.logging_utils import setup_logging
from ocr_snip.single_instance import SingleInstanceGuard


def test_setup_logging_writes_to_file(tmp_path: Path) -> None:
    log_file = tmp_path / "logs" / "app.log"
    logger = setup_logging(log_file=log_file, level=logging.INFO)
    logger.info("diagnostic test entry")

    for handler in logger.handlers:
        handler.flush()

    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "diagnostic test entry" in content


def test_single_instance_guard_notifies_primary(qtbot) -> None:
    unique_name = f"OCRSnippingTool_Test_{uuid.uuid4().hex[:10]}"
    primary = SingleInstanceGuard(server_name=unique_name)
    secondary = SingleInstanceGuard(server_name=unique_name)

    assert primary.start_listening() is True
    try:
        with qtbot.waitSignal(primary.activate_requested, timeout=2000) as blocker:
            notified = secondary.try_notify_existing("SNIP")
        assert notified is True
        assert blocker.args == ["SNIP"]
    finally:
        primary.stop()


def test_single_instance_guard_returns_false_when_no_primary(qtbot) -> None:
    unique_name = f"OCRSnippingTool_NoServer_{uuid.uuid4().hex[:10]}"
    guard = SingleInstanceGuard(server_name=unique_name)
    assert guard.try_notify_existing("SNIP", timeout_ms=150) is False
