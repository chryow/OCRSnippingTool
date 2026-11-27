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

import threading
from typing import Any

import httpx

from ocr_snip.config import AppConfig
from ocr_snip.security import redact_secrets, validate_base_url, validate_model_name

_CLIENT_LOCK = threading.Lock()
_SHARED_CLIENT: httpx.Client | None = None


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
    model = validate_model_name(config.gemini_model.strip() or "gemini-2.5-flash")
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
