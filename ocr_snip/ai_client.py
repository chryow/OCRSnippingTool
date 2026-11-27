"""Shared AI provider HTTP client for Gemini, OpenAI-compatible APIs, and Ollama.

Security & performance features:
- Strict URL scheme validation and HTTPS enforcement for remote API-key endpoints
- Model name validation preventing URL path traversal / query injection
- Explicit `follow_redirects=False` so redirects cannot leak Authorization / API key headers
- Proper system-vs-user message separation to harden against prompt injection
- Secret redaction on all error strings
- Thread-safe connection-pooled `httpx.Client` reuse to avoid repeated TLS handshakes
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Any

import httpx

from ocr_snip.config import DEFAULT_GEMINI_MODEL, DEPRECATED_GEMINI_MODELS, AppConfig
from ocr_snip.security import redact_secrets, validate_base_url, validate_model_name

logger = logging.getLogger("ocr_snip.ai_client")

_CLIENT_LOCK = threading.Lock()
_SHARED_CLIENT: httpx.Client | None = None
_GEMINI_MODEL_HINT_RE = re.compile(r"\bmodels/(gemini-[A-Za-z0-9][A-Za-z0-9._-]{1,60})\b")
_GEMINI_VERSION_RE = re.compile(r"gemini-(\d+)(?:\.(\d+))?")


def get_http_client() -> httpx.Client:
    """Return a shared, keep-alive `httpx.Client` with redirects disabled."""
    global _SHARED_CLIENT
    with _CLIENT_LOCK:
        if _SHARED_CLIENT is None or _SHARED_CLIENT.is_closed:
            _SHARED_CLIENT = httpx.Client(
                follow_redirects=False,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return _SHARED_CLIENT


def close_http_client() -> None:
    """Close the shared HTTP connection pool cleanly on application shutdown."""
    global _SHARED_CLIENT
    with _CLIENT_LOCK:
        if _SHARED_CLIENT is not None and not _SHARED_CLIENT.is_closed:
            try:
                _SHARED_CLIENT.close()
            except Exception:
                pass
        _SHARED_CLIENT = None


def extract_http_error_detail(response: httpx.Response) -> str:
    """Extract a concise, secret-free error message from a failed HTTP response."""
    try:
        payload = response.json()
        if isinstance(payload, dict):
            err = payload.get("error")
            if isinstance(err, dict) and err.get("message"):
                return redact_secrets(str(err["message"]))
            if isinstance(err, str) and err:
                return redact_secrets(err)
    except Exception:
        pass
    return redact_secrets(response.reason_phrase or "Request failed")


def call_ai_provider(
    config: AppConfig,
    prompt: str,
    *,
    system_prompt: str | None = None,
    image_b64: str | None = None,
    temperature: float = 0.0,
    json_mode: bool = False,
    timeout: float = 45.0,
) -> tuple[str, str]:
    """Send a text or vision prompt to the active configured AI provider."""
    provider = config.ai_provider.strip().lower()
    if provider == "gemini":
        return _call_gemini(
            config,
            prompt,
            system_prompt=system_prompt,
            image_b64=image_b64,
            temperature=temperature,
            json_mode=json_mode,
            timeout=timeout,
        )
    if provider == "openai":
        return _call_openai(
            config,
            prompt,
            system_prompt=system_prompt,
            image_b64=image_b64,
            temperature=temperature,
            timeout=timeout,
        )
    if provider == "ollama":
        return _call_ollama(
            config,
            prompt,
            system_prompt=system_prompt,
            image_b64=image_b64,
            temperature=temperature,
            timeout=timeout,
        )
    raise ValueError(f"Unsupported AI provider: {provider}")


def _gemini_model_sort_key(model_name: str) -> tuple[int, int, int, int, str]:
    """Rank Gemini models: prefer stable non-preview Flash models with highest version."""
    lower = model_name.lower()
    is_flash = 1 if "flash" in lower else 0
    is_stable = 0 if any(tag in lower for tag in ("exp", "preview", "thinking", "audio", "tts", "image")) else 1
    is_non_lite = 0 if "lite" in lower else 1
    ver_match = _GEMINI_VERSION_RE.search(lower)
    major = int(ver_match.group(1)) if ver_match else 0
    minor = int(ver_match.group(2)) if ver_match and ver_match.group(2) else 0
    return (is_flash, is_stable, major, minor, f"{is_non_lite}:{lower}")


def _discover_gemini_fallback_model(
    client: httpx.Client,
    api_key: str,
    *,
    failed_model: str,
    error_detail: str,
    timeout: float,
) -> str | None:
    """Resolve an available replacement Gemini model when a configured model returns HTTP 404."""
    failed_lower = failed_model.lower()

    # 1. Check if Google's 404 message explicitly recommends a replacement model
    for candidate in _GEMINI_MODEL_HINT_RE.findall(error_detail):
        cand_lower = candidate.lower()
        if cand_lower != failed_lower and cand_lower not in DEPRECATED_GEMINI_MODELS:
            try:
                return validate_model_name(candidate)
            except ValueError:
                continue

    # 2. Query the Gemini models catalog to find the newest available Flash model
    try:
        list_resp = client.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            headers={"x-goog-api-key": api_key},
            timeout=min(timeout, 10.0),
        )
        if list_resp.status_code != 200:
            return None
        payload = list_resp.json()
        models = payload.get("models", []) if isinstance(payload, dict) else []
        candidates: list[str] = []
        for entry in models:
            if not isinstance(entry, dict):
                continue
            methods = entry.get("supportedGenerationMethods", [])
            if not isinstance(methods, list) or "generateContent" not in methods:
                continue
            raw_name = str(entry.get("name", ""))
            if not raw_name.startswith("models/gemini-"):
                continue
            short_name = raw_name[len("models/") :]
            if short_name.lower() == failed_lower or short_name.lower() in DEPRECATED_GEMINI_MODELS:
                continue
            try:
                candidates.append(validate_model_name(short_name))
            except ValueError:
                continue
        if candidates:
            candidates.sort(key=_gemini_model_sort_key, reverse=True)
            return candidates[0]
    except Exception:
        return None
    return None


def _call_gemini(
    config: AppConfig,
    prompt: str,
    *,
    system_prompt: str | None,
    image_b64: str | None,
    temperature: float,
    json_mode: bool,
    timeout: float,
) -> tuple[str, str]:
    api_key = config.effective_gemini_key()
    if not api_key:
        raise RuntimeError(
            "Gemini API key not set. Add it in Settings or set GEMINI_API_KEY."
        )
    model = validate_model_name(config.gemini_model.strip() or DEFAULT_GEMINI_MODEL)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }

    parts: list[dict[str, Any]] = [{"text": prompt}]
    if image_b64 is not None:
        parts.append({"inline_data": {"mime_type": "image/png", "data": image_b64}})

    gen_cfg: dict[str, Any] = {"temperature": temperature}
    if json_mode:
        gen_cfg["responseMimeType"] = "application/json"

    body: dict[str, Any] = {"contents": [{"parts": parts}], "generationConfig": gen_cfg}
    if system_prompt:
        body["systemInstruction"] = {"parts": [{"text": system_prompt}]}

    client = get_http_client()
    resp = client.post(url, headers=headers, json=body, timeout=timeout)

    if resp.status_code == 404:
        detail = extract_http_error_detail(resp)
        fallback_model = _discover_gemini_fallback_model(
            client,
            api_key,
            failed_model=model,
            error_detail=detail,
            timeout=timeout,
        )
        if fallback_model:
            logger.info(
                "Gemini model '%s' returned 404; retrying automatically with '%s'",
                model,
                fallback_model,
            )
            fallback_url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{fallback_model}:generateContent"
            )
            retry_resp = client.post(fallback_url, headers=headers, json=body, timeout=timeout)
            if retry_resp.status_code == 200:
                resp = retry_resp
                model = fallback_model
                config.gemini_model = fallback_model

    resp.raise_for_status()
    data = resp.json()

    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini returned no candidates.")
    resp_parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in resp_parts if isinstance(part, dict))
    return text.strip(), f"Gemini ({model})"


def _call_openai(
    config: AppConfig,
    prompt: str,
    *,
    system_prompt: str | None,
    image_b64: str | None,
    temperature: float,
    timeout: float,
) -> tuple[str, str]:
    api_key = config.effective_openai_key()
    if not api_key:
        raise RuntimeError(
            "OpenAI API key not set. Add it in Settings or set OPENAI_API_KEY."
        )
    base_url = validate_base_url(
        config.openai_base_url.strip() or "https://api.openai.com/v1",
        require_https_remote=True,
    )
    model = validate_model_name(config.openai_model.strip() or "gpt-4o-mini")
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    messages: list[dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    if image_b64 is not None:
        user_content: str | list[dict[str, Any]] = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
        ]
    else:
        user_content = prompt
    messages.append({"role": "user", "content": user_content})

    body = {"model": model, "temperature": temperature, "messages": messages}
    client = get_http_client()
    resp = client.post(url, headers=headers, json=body, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError("OpenAI API returned no choices.")
    msg_content = choices[0].get("message", {}).get("content", "")
    if isinstance(msg_content, list):
        msg_content = "".join(
            block.get("text", "") for block in msg_content if isinstance(block, dict)
        )
    return str(msg_content).strip(), f"OpenAI ({model})"


def _call_ollama(
    config: AppConfig,
    prompt: str,
    *,
    system_prompt: str | None,
    image_b64: str | None,
    temperature: float,
    timeout: float,
) -> tuple[str, str]:
    base_url = validate_base_url(
        config.ollama_base_url.strip() or "http://localhost:11434",
        require_https_remote=False,
    )
    model = validate_model_name(config.ollama_model.strip() or "qwen2.5vl:7b")
    url = f"{base_url}/api/chat"

    messages: list[dict[str, Any]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    user_msg: dict[str, Any] = {"role": "user", "content": prompt}
    if image_b64 is not None:
        user_msg["images"] = [image_b64]
    messages.append(user_msg)

    body = {
        "model": model,
        "stream": False,
        "options": {"temperature": temperature},
        "messages": messages,
    }
    client = get_http_client()
    resp = client.post(url, json=body, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    text = str(data.get("message", {}).get("content", "")).strip()
    return text, f"Ollama ({model})"
