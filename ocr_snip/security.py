"""Security helpers: safe file permissions, URL/model validation, secret redaction & image guards."""

from __future__ import annotations

import ipaddress
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image

# Cap decoded images to 50 megapixels to defend against PNG/JPEG decompression bombs
MAX_IMAGE_PIXELS = 50_000_000

_MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")

_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"AIza[0-9A-Za-z_-]{20,}"), "[REDACTED_GEMINI_KEY]"),
    (re.compile(r"sk-[A-Za-z0-9_-]{16,}"), "[REDACTED_API_KEY]"),
    (re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9._~+/=-]{8,}"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(x-goog-api-key[\"']?\s*[:=]\s*[\"']?)[^\s\"',}]+"), r"\1[REDACTED]"),
    (re.compile(r"(?i)([?&]key=)[^&\s]+"), r"\1[REDACTED]"),
]


def redact_secrets(text: str) -> str:
    """Scrub API keys and bearer tokens from log messages or error text."""
    out = text
    for pattern, repl in _SECRET_PATTERNS:
        out = pattern.sub(repl, out)
    return out


def ensure_private_dir(path: Path) -> Path:
    """Create directory with owner-only permissions (0o700 on POSIX)."""
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        try:
            os.chmod(path, 0o700)
        except OSError:
            pass
    return path


def atomic_write_text(path: Path, content: str, *, private: bool = True) -> Path:
    """Atomically write UTF-8 text to `path`, enforcing 0o600 permissions when `private=True`."""
    if private:
        ensure_private_dir(path.parent)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    tmp_path = Path(tmp_name)
    try:
        if private and os.name == "posix":
            try:
                os.fchmod(fd, 0o600)
            except OSError:
                pass
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
        if private and os.name == "posix":
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return path


def _is_loopback_host(hostname: str) -> bool:
    host = hostname.strip().lower().rstrip(".")
    if host in ("localhost", "localhost.localdomain") or host.endswith(".local"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def validate_base_url(url: str, *, require_https_remote: bool = False) -> str:
    """Validate an API base URL against scheme injection and plaintext remote credential leaks."""
    cleaned = url.strip().rstrip("/")
    parsed = urlparse(cleaned)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme '{parsed.scheme}': only http/https allowed.")
    if not parsed.hostname:
        raise ValueError("URL must include a valid hostname.")
    if parsed.username or parsed.password:
        raise ValueError("Embedded credentials in URL are not allowed.")
    if require_https_remote and parsed.scheme != "https" and not _is_loopback_host(parsed.hostname):
        raise ValueError(
            "HTTPS is required for remote API endpoints to protect your API key "
            "(HTTP is only allowed for localhost)."
        )
    return cleaned


def validate_model_name(model: str) -> str:
    """Ensure a model identifier cannot inject URL path traversal or query parameters."""
    cleaned = model.strip()
    if not cleaned or ".." in cleaned or not _MODEL_NAME_RE.match(cleaned):
        raise ValueError(f"Invalid model name: {model!r}")
    return cleaned


def safe_open_image(path: Path | str) -> Image.Image:
    """Open an image file with decompression-bomb protection."""
    prev_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
    try:
        with Image.open(path) as img:
            return img.convert("RGB")
    finally:
        Image.MAX_IMAGE_PIXELS = prev_limit
