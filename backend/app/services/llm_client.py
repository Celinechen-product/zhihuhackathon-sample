from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx

from app.config import settings


class LLMClientError(RuntimeError):
    """Base exception for controlled LLM failures."""


class LLMConfigurationError(LLMClientError):
    """Raised when required LLM environment variables are missing."""


class LLMResponseError(LLMClientError):
    """Raised when the LLM relay returns an unusable response."""


class LLMJSONDecodeError(LLMResponseError):
    """Raised when the model response is not a JSON object."""


_CODE_BLOCK_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.IGNORECASE | re.DOTALL)
_semaphore: asyncio.Semaphore | None = None
_semaphore_limit: int | None = None


async def call_llm_json(
    messages: list[dict],
    temperature: float = 0.2,
    timeout: int | None = None,
) -> dict:
    """Call an OpenAI-compatible Chat Completions API and parse a JSON object."""
    _validate_config()
    _validate_messages(messages)

    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    request_timeout = float(timeout if timeout is not None else settings.llm_timeout_seconds)
    if request_timeout <= 0:
        raise LLMClientError("LLM timeout must be greater than 0")

    async with _get_semaphore():
        async with httpx.AsyncClient(timeout=httpx.Timeout(request_timeout)) as client:
            try:
                response = await client.post(
                    _chat_completions_url(),
                    headers=headers,
                    json=payload,
                )
            except httpx.TimeoutException as exc:
                raise LLMClientError("LLM request timed out") from exc
            except httpx.HTTPError as exc:
                raise LLMClientError(f"LLM request failed: {_redact(str(exc))}") from exc

    if response.status_code < 200 or response.status_code >= 300:
        raise LLMClientError(
            "LLM HTTP request failed: "
            f"status={response.status_code}, body={_safe_excerpt(response.text)}"
        )

    try:
        response_payload = response.json()
    except ValueError as exc:
        raise LLMResponseError(
            "LLM relay returned non-JSON HTTP response: "
            f"status={response.status_code}, body={_safe_excerpt(response.text)}"
        ) from exc

    content = _extract_message_content(response_payload)
    return _parse_json_object(content)


def _validate_config() -> None:
    if not settings.has_llm_config:
        raise LLMConfigurationError(
            "LLM is not configured. Set LLM_API_KEY, LLM_BASE_URL, and LLM_MODEL."
        )


def _validate_messages(messages: list[dict]) -> None:
    if not isinstance(messages, list) or not messages:
        raise LLMClientError("LLM messages must be a non-empty list")
    if not all(isinstance(message, dict) for message in messages):
        raise LLMClientError("Each LLM message must be a dict")


def _chat_completions_url() -> str:
    return f"{settings.llm_base_url.rstrip('/')}/chat/completions"


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore, _semaphore_limit

    limit = max(1, int(settings.llm_max_concurrency or 1))
    if _semaphore is None or _semaphore_limit != limit:
        _semaphore = asyncio.Semaphore(limit)
        _semaphore_limit = limit
    return _semaphore


def _extract_message_content(payload: dict[str, Any]) -> str:
    try:
        message = payload["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMResponseError("LLM response did not include choices[0].message") from exc
    if not isinstance(message, dict):
        raise LLMResponseError("LLM response message is not an object")

    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = [
            str(part.get("text", ""))
            for part in content
            if isinstance(part, dict) and part.get("type") in {None, "text"}
        ]
        content_text = "".join(text_parts)
        if content_text:
            return content_text
    raise LLMResponseError("LLM response message content is empty or unsupported")


def _parse_json_object(content: str) -> dict:
    clean_content = _strip_markdown_json_block(content)
    try:
        parsed = json.loads(clean_content)
    except json.JSONDecodeError as exc:
        raise LLMJSONDecodeError(
            f"LLM response was not strict JSON: body={_safe_excerpt(clean_content)}"
        ) from exc
    if not isinstance(parsed, dict):
        raise LLMJSONDecodeError("LLM response JSON must be an object")
    return parsed


def _strip_markdown_json_block(content: str) -> str:
    text = content.strip()
    match = _CODE_BLOCK_RE.fullmatch(text)
    if match:
        return match.group(1).strip()
    return text


def _safe_excerpt(value: Any, limit: int = 500) -> str:
    text = _redact(str(value)).replace("\n", "\\n")
    return text if len(text) <= limit else f"{text[:limit]}..."


def _redact(value: str) -> str:
    api_key = settings.llm_api_key
    if api_key:
        return value.replace(api_key, "[redacted]")
    return value
