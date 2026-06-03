from __future__ import annotations

import argparse
import asyncio
import contextlib
import io
import json
import os
import sys
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = BACKEND_DIR / "tmp" / "llm_cluster_debug_latest.json"
VENV_PYTHON = BACKEND_DIR / ".venv" / "bin" / "python"

if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.search_pipeline import search_life_samples  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run backend search pipeline and print LLM path clustering debug only.",
    )
    parser.add_argument("query", help="User query to debug.")
    parser.add_argument(
        "--clarification",
        default="",
        help="Optional clarification answer used by the search pipeline.",
    )
    parser.add_argument(
        "--count",
        default=20,
        type=int,
        help="Search result count passed to the backend pipeline.",
    )
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    pipeline_stdout = io.StringIO()
    with contextlib.redirect_stdout(pipeline_stdout):
        response = await search_life_samples(
            query=args.query,
            clarification=args.clarification,
            count=args.count,
            llm_path_cluster_debug=True,
        )
    debug = response.get("debug") if isinstance(response, dict) else {}
    if not isinstance(debug, dict):
        debug = {}
    cluster_debug = extract_cluster_debug(debug)
    save_debug_json(
        {
            "query": args.query,
            "clarification": args.clarification,
            "validPeopleCount": valid_people_count(response, cluster_debug),
            "llmPathClusterDebug": cluster_debug,
            "pipelineDebug": debug,
            "pipelineStdout": pipeline_stdout.getvalue(),
        }
    )
    print_summary(
        query=args.query,
        response=response,
        cluster_debug=cluster_debug,
        pipeline_debug=debug,
        output_path=OUTPUT_PATH,
    )
    return 0


def extract_cluster_debug(debug: dict[str, Any]) -> dict[str, Any]:
    nested = debug.get("understanding")
    if isinstance(nested, dict) and isinstance(nested.get("llmPathClusterDebug"), dict):
        return nested["llmPathClusterDebug"]

    keys = {
        "pathGenerationMode",
        "llmClusterInputPeopleCount",
        "llmClusterPathsRaw",
        "llmClusterValidationDebug",
        "droppedClusterPaths",
        "ruleFallbackUsed",
    }
    return {key: debug.get(key) for key in keys if key in debug}


def valid_people_count(response: dict[str, Any], cluster_debug: dict[str, Any]) -> int:
    value = cluster_debug.get("llmClusterInputPeopleCount")
    if isinstance(value, int):
        return value
    people = response.get("people") if isinstance(response, dict) else []
    return len(people) if isinstance(people, list) else 0


def save_debug_json(payload: dict[str, Any]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def print_summary(
    *,
    query: str,
    response: dict[str, Any],
    cluster_debug: dict[str, Any],
    pipeline_debug: dict[str, Any],
    output_path: Path,
) -> None:
    raw = cluster_debug.get("llmClusterPathsRaw")
    raw = raw if isinstance(raw, dict) else {}
    validation = cluster_debug.get("llmClusterValidationDebug")
    validation = validation if isinstance(validation, list) else []
    dropped_paths = cluster_debug.get("droppedClusterPaths")
    dropped_paths = dropped_paths if isinstance(dropped_paths, list) else []

    print(f"query: {query}")
    print(f"validPeopleCount: {valid_people_count(response, cluster_debug)}")
    print(f"pathGenerationMode: {cluster_debug.get('pathGenerationMode', '')}")
    print(f"llmClusterInputPeopleCount: {cluster_debug.get('llmClusterInputPeopleCount', 0)}")
    print(f"cluster_axis: {raw.get('cluster_axis', '')}")
    print(f"llm path names: {json.dumps(path_names(raw), ensure_ascii=False)}")
    print(f"droppedClusterPaths: {json.dumps(dropped_paths, ensure_ascii=False)}")
    print(
        "warnings/errors: "
        f"{json.dumps(warnings_and_errors(validation), ensure_ascii=False)}"
    )
    print("llmDebug:")
    llm_debug = pipeline_debug.get("llmDebug")
    for item in llm_debug if isinstance(llm_debug, list) else []:
        if not isinstance(item, dict):
            continue
        print(
            "  "
            f"task={item.get('task', '')} "
            f"requested={provider_model(item.get('requested_provider'), item.get('requested_model'))} "
            f"actual={provider_model(item.get('actual_provider'), item.get('actual_model'))} "
            f"temperature={item.get('requested_temperature', '')}->{item.get('actual_temperature', '')} "
            f"fallback={item.get('fallback_used', False)} "
            f"reason={item.get('fallback_reason', '')} "
            f"latencyMs={item.get('latency_ms', 0)}"
        )
    print(f"raw debug JSON 保存路径: {output_path}")


def path_names(raw: dict[str, Any]) -> list[str]:
    paths = raw.get("paths")
    if not isinstance(paths, list):
        return []
    names: list[str] = []
    for path in paths:
        if isinstance(path, dict) and str(path.get("name", "")).strip():
            names.append(str(path["name"]).strip())
    return names


def warnings_and_errors(validation: list[Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in validation:
        if not isinstance(item, dict):
            continue
        if item.get("level") in {"warning", "error"}:
            items.append(item)
    return items


def provider_model(provider: Any, model: Any) -> str:
    clean_provider = str(provider or "").strip()
    clean_model = str(model or "").strip()
    if not clean_provider and not clean_model:
        return "(none)"
    if not clean_model:
        return clean_provider
    if not clean_provider:
        return clean_model
    return f"{clean_provider}/{clean_model}"


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
