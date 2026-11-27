"""Shared AI provider HTTP client for Gemini, OpenAI-compatible APIs, and Ollama.

Used by both Vision AI OCR (`vision_ai.py`) and AI Translation (`translate.py`)
so credential handling, payload building, and safe error sanitization live in
one place with zero duplication.
"""

from __future__ import annotations

from typing import Any

import httpx

from ocr_snip.config import AppConfig


def extract_http_error_detail(response: httpx.Response) -> str:
    """Extract a concise, secret-free error message from a failed HTTP response."""
    try:
        payload = response.json()
        if isinstance(payload, dict):
            err = payload.get("error")
            if isinstance(err, dict) and err.get("message"):
                return str(err["message"])
            if isinstance(err, str) and err:
                return err
    except Exception:
        pass
    return response.reason_phrase or "Request failed"


def call_ai_provider(
    config: AppConfig,
    prompt: str,
    *,
    image_b64: str | None = None,
    temperature: float = 0.0,
    json_mode: bool = False,
    timeout: float = 45.0,
) -> tuple[str, str]:
    """Send a text or vision prompt to the active configured AI provider.

    Returns:
        `(response_text, provider_label)` where `provider_label` is e.g.
        `"Gemini (gemini-2.5-flash)"`.
    """
    provider = config.ai_provider.strip().lower()
    if provider == "gemini":
        return _call_gemini(
            config,
            prompt,
            image_b64=image_b64,
            temperature=temperature,
            json_mode=json_mode,
            timeout=timeout,
        )
    if provider == "openai":
        return _call_openai(
            config,
            prompt,
            image_b64=image_b64,
            temperature=temperature,
            timeout=timeout,
        )
    if provider == "ollama":
        return _call_ollama(
            config,
            prompt,
            image_b64=image_b64,
            temperature=temperature,
            timeout=timeout,
        )
    raise ValueError(f"Unsupported AI provider: {provider}")


def _call_gemini(
    config: AppConfig,
    prompt: str,
    *,
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
    model = config.gemini_model.strip() or "gemini-2.5-flash"
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

    body = {"contents": [{"parts": parts}], "generationConfig": gen_cfg}
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, headers=headers, json=body)
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
    image_b64: str | None,
    temperature: float,
    timeout: float,
) -> tuple[str, str]:
    api_key = config.effective_openai_key()
    if not api_key:
        raise RuntimeError(
            "OpenAI API key not set. Add it in Settings or set OPENAI_API_KEY."
        )
    base_url = (config.openai_base_url.strip() or "https://api.openai.com/v1").rstrip("/")
    model = config.openai_model.strip() or "gpt-4o-mini"
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    content: str | list[dict[str, Any]]
    if image_b64 is not None:
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
        ]
    else:
        content = prompt

    body = {
        "model": model,
        "temperature": temperature,
        "messages": [{"role": "user", "content": content}],
    }
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, headers=headers, json=body)
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
    image_b64: str | None,
    temperature: float,
    timeout: float,
) -> tuple[str, str]:
    base_url = (config.ollama_base_url.strip() or "http://localhost:11434").rstrip("/")
    model = config.ollama_model.strip() or "qwen2.5vl:7b"
    url = f"{base_url}/api/chat"

    message: dict[str, Any] = {"role": "user", "content": prompt}
    if image_b64 is not None:
        message["images"] = [image_b64]

    body = {
        "model": model,
        "stream": False,
        "options": {"temperature": temperature},
        "messages": [message],
    }
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(url, json=body)
        resp.raise_for_status()
        data = resp.json()

    text = str(data.get("message", {}).get("content", "")).strip()
    return text, f"Ollama ({model})"
