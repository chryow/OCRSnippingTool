"""Security regression tests for secret redaction, URL/model validation, permissions, and IPC."""

from __future__ import annotations

import logging
import os
import stat
import uuid
from pathlib import Path

import pytest
from PIL import Image
from PyQt6.QtNetwork import QLocalSocket

from ocr_snip.config import AppConfig
from ocr_snip.logging_utils import setup_logging
from ocr_snip.ocr.local_rapidocr import preprocess_snip_image
from ocr_snip.security import (
    atomic_write_text,
    redact_secrets,
    validate_base_url,
    validate_model_name,
)
from ocr_snip.single_instance import SingleInstanceGuard
from ocr_snip.translate import MAX_TRANSLATE_CHARS, Translator


def test_redact_secrets_scrubs_keys_and_tokens() -> None:
    sample = (
        "Failed with AIzaSyAbCdEfGhIjKlMnOpQrStUvWxYz12345 "
        "and sk-proj-1234567890abcdef123456 "
        "and Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload "
        "and ?key=my-secret-param"
    )
    redacted = redact_secrets(sample)
    assert "AIzaSy" not in redacted
    assert "sk-proj-" not in redacted
    assert "eyJhbGci" not in redacted
    assert "my-secret-param" not in redacted
    assert "[REDACTED" in redacted


def test_log_filter_redacts_secrets_on_disk(tmp_path: Path) -> None:
    log_file = tmp_path / "logs" / "app.log"
    logger = setup_logging(log_file=log_file, level=logging.INFO)
    logger.error("Auth failed: Bearer super_secret_token_999 and AIzaSyDummySecretKeyValue123456789")

    for h in logger.handlers:
        h.flush()

    content = log_file.read_text(encoding="utf-8")
    assert "super_secret_token_999" not in content
    assert "AIzaSyDummySecretKeyValue123456789" not in content
    assert "[REDACTED" in content


def test_atomic_write_enforces_owner_only_permissions(tmp_path: Path) -> None:
    secret_file = tmp_path / "private" / "config.json"
    atomic_write_text(secret_file, '{"api_key": "test"}', private=True)
    assert secret_file.exists()

    if os.name == "posix":
        file_mode = stat.S_IMODE(secret_file.stat().st_mode)
        dir_mode = stat.S_IMODE(secret_file.parent.stat().st_mode)
        assert file_mode == 0o600
        assert dir_mode == 0o700


def test_validate_base_url_hardening() -> None:
    assert validate_base_url("https://api.openai.com/v1/", require_https_remote=True) == "https://api.openai.com/v1"
    assert validate_base_url("http://localhost:11434/", require_https_remote=True) == "http://localhost:11434"
    assert validate_base_url("http://127.0.0.1:8080/v1", require_https_remote=True) == "http://127.0.0.1:8080/v1"

    with pytest.raises(ValueError):
        validate_base_url("file:///etc/passwd")
    with pytest.raises(ValueError):
        validate_base_url("https://user:pass@api.openai.com/v1")
    with pytest.raises(ValueError):
        validate_base_url("http://api.example.com/v1", require_https_remote=True)


def test_validate_model_name_blocks_traversal_and_query_injection() -> None:
    assert validate_model_name("gemini-2.5-flash") == "gemini-2.5-flash"
    assert validate_model_name("qwen2.5vl:7b") == "qwen2.5vl:7b"
    assert validate_model_name("openai/gpt-4o-mini") == "openai/gpt-4o-mini"

    for bad in ("", "../../etc/passwd", "gemini?key=leak", "model#frag", "model name with spaces"):
        with pytest.raises(ValueError):
            validate_model_name(bad)


def test_translate_blocks_oversized_input() -> None:
    huge = "a" * (MAX_TRANSLATE_CHARS + 10)
    res = Translator(AppConfig()).translate(huge)
    assert not res.ok
    assert "too long" in (res.error or "").lower()


def test_preprocess_downscales_oversized_4k_image() -> None:
    giant = Image.new("RGB", (4000, 3000), "white")
    arr = preprocess_snip_image(giant, max_side=2400)
    # 2400px + 32px border padding
    assert max(arr.shape[0], arr.shape[1]) <= 2432


def test_single_instance_ignores_untrusted_ipc_payload(qtbot) -> None:
    unique_name = f"OCRSnippingTool_Sec_{uuid.uuid4().hex[:10]}"
    primary = SingleInstanceGuard(server_name=unique_name)
    received: list[str] = []
    primary.activate_requested.connect(received.append)

    assert primary.start_listening() is True
    try:
        sock = QLocalSocket()
        sock.connectToServer(unique_name)
        assert sock.waitForConnected(500)
        sock.write(b"UNTRUSTED_COMMAND_INJECTION")
        sock.flush()
        sock.waitForBytesWritten(500)
        sock.disconnectFromServer()

        qtbot.wait(150)
        assert received == []
    finally:
        primary.stop()
