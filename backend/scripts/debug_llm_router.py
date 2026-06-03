from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
VENV_PYTHON = BACKEND_DIR / ".venv" / "bin" / "python"

if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.llm_client import LLMClientError, call_llm_task  # noqa: E402
from app.services.llm_router import router_dry_run  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect or smoke-test the LLM task router.")
    parser.add_argument(
        "--smoke",
        choices=["kimi", "qwen"],
        help="Run a provider smoke test. Does not print API keys or prompts.",
    )
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    if args.smoke == "kimi":
        return await smoke_kimi()
    if args.smoke == "qwen":
        return await smoke_qwen()
    return dry_run()


def dry_run() -> int:
    snapshot = router_dry_run()
    print("LLM task router dry run")
    print(
        "timeout: "
        f"{snapshot['timeout']['requestVariable']}="
        f"{snapshot['timeout']['seconds']}s "
        f"(fallback-compatible with {snapshot['timeout']['legacyCompatibleVariable']}, "
        f"default {snapshot['timeout']['defaultSeconds']}s)"
    )
    print(f"fallbackEnabled: {snapshot['fallbackEnabled']}")
    print()
    print("tasks:")
    for item in snapshot["tasks"]:
        print(
            "  "
            f"{item['task']}: defaultProvider={item['defaultProvider']} "
            f"overrideProvider={item['overrideProvider'] or '(none)'} "
            f"resolvedProvider={item['resolvedProvider']} "
            f"modelEnv={item['modelEnv']} "
            f"model={_display_model(item)} "
            f"requiresJson={item['requiresJson']} "
            f"missing={_json(item['missing'])}"
        )
    print()
    for provider, items in snapshot.get("providerChecks", {}).items():
        print(f"{provider} provider:")
        for item in items:
            print(
                "  "
                f"{item['task']}: provider={item['provider']} "
                f"modelEnv={item['modelEnv']} "
                f"model={_display_model(item)} "
                f"missing={_json(item['missing'])}"
            )
    print()
    fallback = snapshot["fallback"]
    print(
        "fallback: "
        f"provider={fallback['provider']} "
        f"modelEnv={fallback['modelEnv']} "
        f"model={_display_model(fallback)} "
        f"missing={_json(fallback['missing'])}"
    )
    return 0


async def smoke_kimi() -> int:
    return await smoke_provider(
        provider="kimi",
        task="experience_extraction",
        temperature=0,
    )


async def smoke_qwen() -> int:
    return await smoke_provider(
        provider="qwen",
        task="persona_chat",
        temperature=0,
    )


async def smoke_provider(provider: str, task: str, temperature: float) -> int:
    debug: list[dict[str, Any]] = []
    status = "success"
    error_excerpt = ""
    result: dict[str, Any] | str | None = None
    try:
        result = await call_llm_task(
            task=task,
            messages=[
                {
                    "role": "system",
                    "content": "Return one strict JSON object only. No markdown.",
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": "provider_smoke_test",
                            "provider": provider,
                            "expectedJson": {"ok": True},
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            response_format="json",
            temperature=temperature,
            timeout=20,
            debug=debug,
            allow_fallback=False,
            provider_override=provider,
        )
        if not isinstance(result, dict):
            status = "failed_non_json"
    except LLMClientError as exc:
        status = "failed"
        error_excerpt = _limit(str(exc), 500)

    entry = debug[-1] if debug else {}
    print(f"{provider} smoke test")
    print(f"status: {status}")
    print(f"task: {task}")
    print(f"provider: {entry.get('provider') or entry.get('requested_provider', '')}")
    print(f"model: {entry.get('model') or entry.get('requested_model', '')}")
    print(f"base_url_host: {entry.get('base_url_host', '')}")
    print(f"requested_temperature: {entry.get('requested_temperature', '')}")
    print(f"actual_temperature: {entry.get('actual_temperature', '')}")
    print(f"fallback_used: {entry.get('fallback_used', False)}")
    print(f"fallback_reason: {entry.get('fallback_reason', '')}")
    print(f"http_status: {entry.get('http_status', '')}")
    print(f"provider_error_type: {entry.get('provider_error_type', '')}")
    print(f"provider_error_message: {_limit(entry.get('provider_error_message', ''), 500)}")
    print(f"json_parse_ok: {entry.get('json_parse_ok', False)}")
    print(f"error excerpt: {_limit(error_excerpt or entry.get('error', ''), 500)}")
    if isinstance(result, dict):
        print(f"result_keys: {json.dumps(sorted(result.keys()), ensure_ascii=False)}")
    return 0


def _display_model(item: dict[str, Any]) -> str:
    return str(item.get("model") or "(missing)")


def _limit(value: Any, limit: int) -> str:
    text = str(value or "").replace("\n", "\\n")
    return text if len(text) <= limit else f"{text[:limit]}..."


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
