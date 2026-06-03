from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.services.llm_router import (
    LLMResolvedConfig,
    default_temperature_for_task,
    resolve_fallback_config,
    resolve_primary_config,
    resolve_provider_config,
    task_requires_json,
)


class LLMClientError(RuntimeError):
    """Base exception for controlled LLM failures."""


class LLMConfigurationError(LLMClientError):
    """Raised when required LLM environment variables are missing."""


class LLMResponseError(LLMClientError):
    """Raised when the LLM relay returns an unusable response."""


class LLMJSONDecodeError(LLMResponseError):
    """Raised when the model response is not a JSON object."""


class _AttemptFailure(RuntimeError):
    def __init__(
        self,
        reason: str,
        error: LLMClientError,
        metadata: dict[str, Any] | None = None,
    ):
        super().__init__(str(error))
        self.reason = reason
        self.error = error
        self.metadata = metadata or {}


_CODE_BLOCK_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.IGNORECASE | re.DOTALL)
_semaphore: asyncio.Semaphore | None = None
_semaphore_limit: int | None = None


async def call_llm_task(
    *,
    task: str,
    messages: list[dict],
    response_format: str = "json",
    temperature: float | None = None,
    timeout: int | float | None = None,
    debug: list[dict[str, Any]] | None = None,
    allow_fallback: bool | None = None,
    provider_override: str | None = None,
) -> dict[str, Any] | str:
    """Call the routed OpenAI-compatible provider for one logical LLM task."""
    _validate_messages(messages)
    clean_task = str(task or "").strip()
    if not clean_task:
        _record_missing_task(debug)
        raise LLMConfigurationError("LLM task is required for routed calls")

    primary_config = (
        resolve_provider_config(clean_task, provider_override, is_fallback=False)
        if provider_override
        else resolve_primary_config(clean_task)
    )
    requested_provider = primary_config.provider
    requested_model = primary_config.model
    requested_model_env = primary_config.model_env
    actual_temperature = (
        float(temperature)
        if temperature is not None
        else default_temperature_for_task(clean_task)
    )
    wants_json = response_format == "json" or task_requires_json(clean_task)
    started_at = time.perf_counter()
    debug_entry: dict[str, Any] = {
        "task": clean_task,
        "requested_provider": requested_provider,
        "requested_model": requested_model,
        "requested_model_env": requested_model_env,
        "requested_temperature": actual_temperature,
        "actual_temperature": None,
        "actual_provider": "",
        "actual_model": "",
        "actual_model_env": "",
        "provider": "",
        "base_url_host": "",
        "model": "",
        "http_status": None,
        "provider_error_message": "",
        "provider_error_type": "",
        "latency_ms": 0,
        "fallback_used": False,
        "fallback_reason": "",
        "json_parse_ok": not wants_json,
        "error": "",
    }

    try:
        try:
            result = await _attempt_call(
                config=primary_config,
                messages=messages,
                wants_json=wants_json,
                temperature=actual_temperature,
                timeout=timeout,
            )
            _record_actual(debug_entry, primary_config)
            debug_entry["json_parse_ok"] = True
            return result
        except _AttemptFailure as primary_failure:
            debug_entry["fallback_reason"] = primary_failure.reason
            _apply_failure_metadata(debug_entry, primary_failure)
            fallback_enabled = settings.llm_enable_fallback if allow_fallback is None else allow_fallback
            if not fallback_enabled:
                _record_actual(debug_entry, primary_config)
                debug_entry["json_parse_ok"] = False
                debug_entry["error"] = _safe_excerpt(primary_failure.error)
                raise primary_failure.error

            fallback_config = resolve_fallback_config(clean_task)
            if fallback_config.missing:
                _record_actual(debug_entry, primary_config)
                debug_entry["error"] = _safe_excerpt(
                    f"{primary_failure.error}; fallback missing: {', '.join(fallback_config.missing)}"
                )
                raise primary_failure.error

            try:
                result = await _attempt_call(
                    config=fallback_config,
                    messages=messages,
                    wants_json=wants_json,
                    temperature=actual_temperature,
                    timeout=timeout,
                )
                _record_actual(debug_entry, fallback_config)
                debug_entry["fallback_used"] = True
                debug_entry["json_parse_ok"] = True
                return result
            except _AttemptFailure as fallback_failure:
                _record_actual(debug_entry, fallback_config)
                debug_entry["fallback_used"] = True
                debug_entry["json_parse_ok"] = False
                debug_entry["error"] = _safe_excerpt(fallback_failure.error)
                _apply_failure_metadata(debug_entry, fallback_failure)
                raise fallback_failure.error
    except asyncio.CancelledError:
        debug_entry["fallback_used"] = False
        debug_entry["fallback_reason"] = "task_cancelled"
        debug_entry["json_parse_ok"] = False
        debug_entry["error"] = "LLM task was cancelled before completion"
        raise
    finally:
        debug_entry["latency_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
        if debug is not None:
            debug.append(debug_entry)
        _log_llm_debug(debug_entry)


async def call_llm_json(
    messages: list[dict],
    temperature: float = 0.2,
    timeout: int | None = None,
    *,
    task: str,
    debug: list[dict[str, Any]] | None = None,
    allow_fallback: bool | None = None,
    provider_override: str | None = None,
) -> dict[str, Any]:
    """JSON helper. Callers must pass an explicit logical task."""
    result = await call_llm_task(
        task=task,
        messages=messages,
        response_format="json",
        temperature=temperature,
        timeout=timeout,
        debug=debug,
        allow_fallback=allow_fallback,
        provider_override=provider_override,
    )
    if not isinstance(result, dict):
        raise LLMJSONDecodeError("LLM response JSON must be an object")
    return result


async def _attempt_call(
    *,
    config: LLMResolvedConfig,
    messages: list[dict],
    wants_json: bool,
    temperature: float,
    timeout: int | float | None,
) -> dict[str, Any] | str:
    provider_temperature = _normalize_provider_temperature(
        config.provider,
        config.model,
        temperature,
    )
    metadata = _provider_metadata(
        config,
        requested_temperature=temperature,
        actual_temperature=provider_temperature,
    )
    if config.missing:
        raise _AttemptFailure(
            config.fallback_reason or "missing_config",
            LLMConfigurationError(
                f"LLM task '{config.task}' provider '{config.provider}' is not configured. "
                f"Missing: {', '.join(config.missing)}."
            ),
            metadata,
        )

    payload = {
        "model": config.model,
        "messages": messages,
        "temperature": provider_temperature,
    }
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    request_timeout = float(
        timeout if timeout is not None else settings.llm_request_timeout_seconds
    )
    if request_timeout <= 0:
        raise _AttemptFailure(
            "provider_client_error",
            LLMClientError("LLM timeout must be greater than 0"),
            metadata,
        )

    async with _get_semaphore():
        async with httpx.AsyncClient(timeout=httpx.Timeout(request_timeout)) as client:
            try:
                response = await client.post(
                    config.chat_completions_url,
                    headers=headers,
                    json=payload,
                )
            except httpx.TimeoutException as exc:
                raise _AttemptFailure(
                    "timeout",
                    LLMClientError("LLM request timed out"),
                    metadata,
                ) from exc
            except httpx.HTTPError as exc:
                raise _AttemptFailure(
                    "provider_client_error",
                    LLMClientError(f"LLM request failed: {_safe_excerpt(exc)}"),
                    metadata,
                ) from exc

    if response.status_code < 200 or response.status_code >= 300:
        error_message, error_type = _provider_error_from_response(response)
        raise _AttemptFailure(
            "http_error",
            LLMClientError(
                "LLM HTTP request failed: "
                f"provider={config.provider}, status={response.status_code}, "
                f"body={_safe_excerpt(response.text)}"
            ),
            _provider_metadata(
                config,
                requested_temperature=temperature,
                actual_temperature=provider_temperature,
                http_status=response.status_code,
                provider_error_message=error_message,
                provider_error_type=error_type,
            ),
        )

    try:
        response_payload = response.json()
    except ValueError as exc:
        raise _AttemptFailure(
            "provider_client_error",
            LLMResponseError(
                "LLM relay returned non-JSON HTTP response: "
                f"status={response.status_code}, body={_safe_excerpt(response.text)}"
            ),
            _provider_metadata(
                config,
                requested_temperature=temperature,
                actual_temperature=provider_temperature,
                http_status=response.status_code,
            ),
        ) from exc

    try:
        content = _extract_message_content(response_payload)
    except LLMResponseError as exc:
        raise _AttemptFailure("provider_client_error", exc, metadata) from exc

    if not wants_json:
        return content

    try:
        return _parse_json_object(content)
    except LLMJSONDecodeError as exc:
        raise _AttemptFailure("json_parse_failed", exc, metadata) from exc


def _record_actual(debug_entry: dict[str, Any], config: LLMResolvedConfig) -> None:
    debug_entry["actual_provider"] = config.provider
    debug_entry["actual_model"] = config.model
    debug_entry["actual_model_env"] = config.model_env
    requested_temperature = debug_entry.get("requested_temperature")
    if isinstance(requested_temperature, (int, float)):
        debug_entry["actual_temperature"] = _normalize_provider_temperature(
            config.provider,
            config.model,
            float(requested_temperature),
        )
    if not debug_entry.get("http_status") and not debug_entry.get("provider_error_message"):
        debug_entry["provider"] = config.provider
        debug_entry["base_url_host"] = _base_url_host(config.base_url)
        debug_entry["model"] = config.model


def _apply_failure_metadata(debug_entry: dict[str, Any], failure: _AttemptFailure) -> None:
    for key, value in failure.metadata.items():
        if value not in (None, ""):
            debug_entry[key] = value


def _record_missing_task(debug: list[dict[str, Any]] | None) -> None:
    entry: dict[str, Any] = {
        "task": "",
        "requested_provider": "",
        "requested_model": "",
        "requested_model_env": "",
        "actual_provider": "",
        "actual_model": "",
        "actual_model_env": "",
        "provider": "",
        "base_url_host": "",
        "model": "",
        "http_status": None,
        "provider_error_message": "",
        "provider_error_type": "",
        "latency_ms": 0,
        "fallback_used": False,
        "fallback_reason": "missing_task",
        "json_parse_ok": False,
        "error": "LLM task is required for routed calls",
    }
    if debug is not None:
        debug.append(entry)
    _log_llm_debug(entry)


def _validate_messages(messages: list[dict]) -> None:
    if not isinstance(messages, list) or not messages:
        raise LLMClientError("LLM messages must be a non-empty list")
    if not all(isinstance(message, dict) for message in messages):
        raise LLMClientError("Each LLM message must be a dict")


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


def _provider_metadata(
    config: LLMResolvedConfig,
    *,
    requested_temperature: float | None = None,
    actual_temperature: float | None = None,
    http_status: int | None = None,
    provider_error_message: str = "",
    provider_error_type: str = "",
) -> dict[str, Any]:
    return {
        "provider": config.provider,
        "base_url_host": _base_url_host(config.base_url),
        "model": config.model,
        "requested_temperature": requested_temperature,
        "actual_temperature": actual_temperature,
        "http_status": http_status,
        "provider_error_message": _safe_excerpt(provider_error_message, limit=500)
        if provider_error_message
        else "",
        "provider_error_type": _safe_excerpt(provider_error_type, limit=120)
        if provider_error_type
        else "",
    }


def _provider_error_from_response(response: httpx.Response) -> tuple[str, str]:
    text = response.text
    try:
        payload = response.json()
    except ValueError:
        return _safe_excerpt(text), ""
    message = ""
    error_type = ""
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = _text(error.get("message") or error.get("msg") or error.get("code"))
            error_type = _text(error.get("type") or error.get("code") or error.get("param"))
        else:
            message = _text(payload.get("message") or payload.get("msg") or payload.get("detail"))
            error_type = _text(payload.get("type") or payload.get("code"))
    return _safe_excerpt(message or text), _safe_excerpt(error_type, limit=120)


def _base_url_host(base_url: str) -> str:
    clean = _text(base_url)
    if not clean:
        return ""
    parsed = urlparse(clean)
    if not parsed.netloc and parsed.path:
        parsed = urlparse(f"https://{clean}")
    return parsed.netloc or parsed.path.split("/")[0]


def _normalize_provider_temperature(
    provider: str,
    model: str,
    temperature: float,
) -> float:
    if provider.strip().lower() == "kimi" and model.strip() == "kimi-k2.6":
        return 1.0
    return temperature


def _parse_json_object(content: str) -> dict[str, Any]:
    clean_content = _strip_markdown_json_block(content)
    parsed = _load_json_object(clean_content)
    if parsed is None:
        parsed = _safe_parse_first_json_object(clean_content)
    if parsed is None:
        raise LLMJSONDecodeError(
            f"LLM response was not strict JSON: body={_safe_excerpt(clean_content)}"
        )
    if not isinstance(parsed, dict):
        raise LLMJSONDecodeError("LLM response JSON must be an object")
    return parsed


def _load_json_object(content: str) -> Any | None:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None


def _safe_parse_first_json_object(content: str) -> dict[str, Any] | None:
    decoder = json.JSONDecoder()
    start = content.find("{")
    while start >= 0:
        try:
            parsed, _ = decoder.raw_decode(content[start:])
        except json.JSONDecodeError:
            start = content.find("{", start + 1)
            continue
        return parsed if isinstance(parsed, dict) else None
    return None


def _strip_markdown_json_block(content: str) -> str:
    text = content.strip()
    match = _CODE_BLOCK_RE.fullmatch(text)
    if match:
        return match.group(1).strip()
    return text


def _safe_excerpt(value: Any, limit: int = 500) -> str:
    text = _redact(str(value)).replace("\n", "\\n")
    return text if len(text) <= limit else f"{text[:limit]}..."


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _redact(value: str) -> str:
    redacted = value
    for api_key in (
        settings.deepseek_api_key,
        settings.kimi_api_key,
        settings.qwen_api_key,
        settings.openai_api_key,
        settings.llm_api_key,
    ):
        if api_key:
            redacted = redacted.replace(api_key, "[redacted]")
    return redacted


def _log_llm_debug(entry: dict[str, Any]) -> None:
    parts = [
        f"task={entry.get('task', '')}",
        f"requested_provider={entry.get('requested_provider', '')}",
        f"requested_model={entry.get('requested_model', '')}",
        f"actual_provider={entry.get('actual_provider', '')}",
        f"actual_model={entry.get('actual_model', '')}",
        f"requested_temperature={entry.get('requested_temperature', '')}",
        f"actual_temperature={entry.get('actual_temperature', '')}",
        f"provider={entry.get('provider', '')}",
        f"base_url_host={entry.get('base_url_host', '')}",
        f"model={entry.get('model', '')}",
        f"fallback_used={str(entry.get('fallback_used', False)).lower()}",
        f"fallback_reason={entry.get('fallback_reason', '')}",
        f"http_status={entry.get('http_status', '')}",
        f"provider_error_type={entry.get('provider_error_type', '')}",
        f"json_parse_ok={str(entry.get('json_parse_ok', False)).lower()}",
        f"latency_ms={entry.get('latency_ms', 0)}",
    ]
    if entry.get("provider_error_message"):
        parts.append(
            f"provider_error_message={_safe_excerpt(entry['provider_error_message'], limit=160)}"
        )
    if entry.get("error"):
        parts.append(f"error={_safe_excerpt(entry['error'], limit=160)}")
    print("[llm.router] " + " ".join(parts))
