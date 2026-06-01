from __future__ import annotations

import json
import re
from typing import Any

from app.services.llm_client import (
    LLMClientError,
    LLMConfigurationError,
    LLMJSONDecodeError,
    call_llm_json,
)
from app.services.llm_prompts import CLUSTER_PATHS_PROMPT


PATH_GENERATION_MODE = "rule_based_with_llm_cluster_debug"
VALID_CLUSTER_AXES = {
    "action_strategy",
    "access_mechanism",
    "choice_direction",
    "current_stage",
    "constraint_context",
    "outcome_direction",
}
VALID_CONFIDENCE = {"high", "medium", "low"}
FORBIDDEN_PATH_NAME_MARKERS = (
    "理性规划型",
    "勇敢尝试型",
    "自我成长型",
    "稳定回归型",
    "寻找意义型",
    "突破自我型",
    "积极面对型",
    "阶段性探索型",
    "最优选择路径",
    "其他相关经历",
    "其他路径",
    "相近经历",
)
AI_DESC_MARKERS = (
    "提供参考",
    "帮助理解",
    "具有启发",
    "值得借鉴",
    "适合你看",
)
EXTERNAL_EVENT_PATH_NAME_MARKERS = (
    "疫情",
    "封控",
    "意外",
    "家里出事",
    "家里出了事",
    "家中出事",
    "offer 被取消",
    "offer被取消",
    "Offer 被取消",
    "Offer被取消",
    "生病",
)
ACTIVE_CHOICE_PATH_NAME_MARKERS = (
    "裸辞",
    "离职",
    "待业",
    "找工作",
    "求职",
    "面试",
    "休整",
    "重新开始",
    "换城市",
    "搬家",
    "定居",
    "回老家",
    "回家",
    "调整",
    "转行",
    "考公",
    "考编",
    "自由职业",
    "副业",
    "创业",
    "降低预期",
    "就业",
    "工作",
    "生活",
    "协商",
    "支持",
    "边界",
    "沟通",
    "分开",
    "修复",
    "考研",
    "跨专业",
    "选专业",
)


async def cluster_paths_with_llm_debug(
    *,
    query: str,
    clarification: str | None,
    query_context: dict[str, Any] | None,
    people: list[dict[str, Any]] | None,
    rule_fallback_used: bool,
    enabled: bool = True,
) -> dict[str, Any]:
    valid_people = [person for person in people or [] if _person_id(person)]
    debug = _empty_debug(
        people_count=len(valid_people),
        rule_fallback_used=rule_fallback_used,
    )
    debug["llmClusterDebugEnabled"] = enabled
    if not enabled:
        debug["llmClusterValidationDebug"].append(
            {"level": "info", "message": "skipped: disabled for request"}
        )
        return debug
    if not valid_people:
        debug["llmClusterValidationDebug"].append(
            {"level": "info", "message": "skipped: no valid people for path clustering"}
        )
        return debug

    payload = _build_payload(
        query=query,
        clarification=clarification,
        query_context=query_context or {},
        people=valid_people,
    )
    try:
        raw = await call_llm_json(
            messages=[
                {"role": "system", "content": CLUSTER_PATHS_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False),
                },
            ],
            temperature=0.2,
        )
    except LLMConfigurationError as exc:
        debug["llmClusterValidationDebug"].append(
            {"level": "error", "message": f"LLM path clustering skipped: {_text(exc)}"}
        )
        return debug
    except LLMJSONDecodeError as exc:
        debug["llmClusterValidationDebug"].append(
            {"level": "error", "message": f"LLM path clustering JSON parse failed: {_text(exc)}"}
        )
        return debug
    except LLMClientError as exc:
        debug["llmClusterValidationDebug"].append(
            {"level": "error", "message": f"LLM path clustering failed: {_text(exc)}"}
        )
        return debug
    except Exception as exc:
        debug["llmClusterValidationDebug"].append(
            {"level": "error", "message": f"Unexpected LLM path clustering error: {_text(exc)}"}
        )
        return debug

    validation_debug, dropped_paths = validate_llm_cluster_result(raw, valid_people)
    debug["llmClusterPathsRaw"] = raw
    debug["llmClusterValidationDebug"] = validation_debug
    debug["droppedClusterPaths"] = dropped_paths
    return debug


def validate_llm_cluster_result(
    raw: dict[str, Any],
    valid_people: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    validation_debug: list[dict[str, Any]] = []
    dropped_paths: list[dict[str, Any]] = []
    valid_person_ids = {_person_id(person) for person in valid_people if _person_id(person)}

    cluster_axis = _text(raw.get("cluster_axis"))
    if cluster_axis and cluster_axis not in VALID_CLUSTER_AXES:
        validation_debug.append(
            {
                "level": "warning",
                "field": "cluster_axis",
                "message": f"unknown cluster_axis: {cluster_axis}",
            }
        )

    assigned_person_ids: set[str] = set()
    paths = raw.get("paths")
    if not isinstance(paths, list):
        validation_debug.append(
            {"level": "error", "field": "paths", "message": "paths must be an array"}
        )
        return validation_debug, dropped_paths

    for index, path in enumerate(paths):
        if not isinstance(path, dict):
            validation_debug.append(
                {"level": "error", "pathIndex": index, "message": "path must be an object"}
            )
            continue

        path_id = _path_id(path, index)
        person_ids = _string_list(path.get("personIds") or path.get("person_ids"))
        path_dropped = False

        if not person_ids:
            dropped_paths.append(
                _drop_path(path, "path has no personIds", path_index=index)
            )
            path_dropped = True

        invalid_person_ids = [person_id for person_id in person_ids if person_id not in valid_person_ids]
        if invalid_person_ids:
            dropped_paths.append(
                _drop_path(
                    path,
                    "path.personIds include unknown people",
                    path_index=index,
                    details={"invalidPersonIds": invalid_person_ids},
                )
            )
            path_dropped = True

        duplicate_person_ids = [person_id for person_id in person_ids if person_id in assigned_person_ids]
        if duplicate_person_ids:
            dropped_paths.append(
                _drop_path(
                    path,
                    "personId assigned to multiple paths",
                    path_index=index,
                    details={"duplicatePersonIds": duplicate_person_ids},
                )
            )
            path_dropped = True

        shared_evidence = path.get("shared_evidence")
        if shared_evidence is None:
            shared_evidence = path.get("sharedEvidence")
        _validate_shared_evidence(
            shared_evidence=shared_evidence,
            valid_person_ids=valid_person_ids,
            path_id=path_id,
            path_index=index,
            validation_debug=validation_debug,
        )

        name = _text(path.get("name"))
        forbidden_name_markers = [
            marker for marker in FORBIDDEN_PATH_NAME_MARKERS if marker in name
        ]
        if forbidden_name_markers:
            dropped_paths.append(
                _drop_path(
                    path,
                    "path.name contains forbidden marker",
                    path_index=index,
                    details={"markers": forbidden_name_markers},
                )
            )
            path_dropped = True

        external_event_markers = [
            marker for marker in EXTERNAL_EVENT_PATH_NAME_MARKERS if marker in name
        ]
        if external_event_markers:
            event_debug = {
                "pathId": path_id,
                "pathIndex": index,
                "field": "name",
                "code": "external_event_used_as_path_name",
                "message": "external_event_used_as_path_name",
                "markers": external_event_markers,
            }
            if _has_active_choice_expression(name):
                validation_debug.append(
                    {
                        "level": "warning",
                        **event_debug,
                    }
                )
            else:
                validation_debug.append(
                    {
                        "level": "error",
                        **event_debug,
                    }
                )
                dropped_paths.append(
                    _drop_path(
                        path,
                        "external_event_used_as_path_name",
                        path_index=index,
                        details={"markers": external_event_markers},
                    )
                )
                path_dropped = True

        desc = _text(path.get("desc"))
        ai_desc_markers = [marker for marker in AI_DESC_MARKERS if marker in desc]
        if ai_desc_markers:
            validation_debug.append(
                {
                    "level": "warning",
                    "pathId": path_id,
                    "pathIndex": index,
                    "field": "desc",
                    "message": "desc contains AI-ish wording",
                    "markers": ai_desc_markers,
                }
            )

        confidence = _text(path.get("confidence"))
        if confidence and confidence not in VALID_CONFIDENCE:
            validation_debug.append(
                {
                    "level": "warning",
                    "pathId": path_id,
                    "pathIndex": index,
                    "field": "confidence",
                    "message": f"unknown confidence: {confidence}",
                }
            )

        if not path_dropped:
            assigned_person_ids.update(person_ids)
            validation_debug.append(
                {
                    "level": "info",
                    "pathId": path_id,
                    "pathIndex": index,
                    "message": "path passed debug validation",
                    "personIds": person_ids,
                }
            )

    return validation_debug, dropped_paths


def _empty_debug(*, people_count: int, rule_fallback_used: bool) -> dict[str, Any]:
    return {
        "pathGenerationMode": PATH_GENERATION_MODE,
        "llmClusterInputPeopleCount": people_count,
        "llmClusterPathsRaw": {},
        "llmClusterValidationDebug": [],
        "droppedClusterPaths": [],
        "ruleFallbackUsed": rule_fallback_used,
    }


def _build_payload(
    *,
    query: str,
    clarification: str | None,
    query_context: dict[str, Any],
    people: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "task": "Cluster valid people into possible path groups for debug only.",
        "userQuery": _text(query),
        "clarification": _text(clarification),
        "queryContext": query_context,
        "people": [_llm_person_input(person) for person in people],
    }


def _llm_person_input(person: dict[str, Any]) -> dict[str, Any]:
    source = person.get("source") if isinstance(person.get("source"), dict) else {}
    internal = person.get("internal") if isinstance(person.get("internal"), dict) else {}
    return {
        "personId": _person_id(person),
        "name": _text(person.get("name")),
        "sampleType": _text(person.get("sampleType") or person.get("sample_type")),
        "situation": _text(person.get("situation")),
        "actionSummary": _text(person.get("actionSummary")),
        "realDetails": _string_list(person.get("realDetails")),
        "key_fragments": _string_list(person.get("key_fragments")),
        "currentStatus": _text(person.get("currentStatus")),
        "entrySituation": _text(person.get("entrySituation")),
        "entryStatus": _text(person.get("entryStatus")),
        "matchReasons": _string_list(person.get("matchReasons")),
        "source": {
            "title": _text(source.get("title")),
            "url": _text(source.get("url")),
            "content_type": _text(source.get("content_type") or source.get("type")),
        },
        "confidence": _text(internal.get("confidence")),
    }


def _validate_shared_evidence(
    *,
    shared_evidence: Any,
    valid_person_ids: set[str],
    path_id: str,
    path_index: int,
    validation_debug: list[dict[str, Any]],
) -> None:
    if not isinstance(shared_evidence, list):
        validation_debug.append(
            {
                "level": "warning",
                "pathId": path_id,
                "pathIndex": path_index,
                "field": "shared_evidence",
                "message": "shared_evidence must be an array",
            }
        )
        return
    if not shared_evidence:
        validation_debug.append(
            {
                "level": "warning",
                "pathId": path_id,
                "pathIndex": path_index,
                "field": "shared_evidence",
                "message": "shared_evidence is empty",
            }
        )
        return
    for evidence_index, item in enumerate(shared_evidence):
        if not isinstance(item, dict):
            validation_debug.append(
                {
                    "level": "warning",
                    "pathId": path_id,
                    "pathIndex": path_index,
                    "evidenceIndex": evidence_index,
                    "field": "shared_evidence",
                    "message": "shared_evidence item must be an object",
                }
            )
            continue
        person_id = _text(item.get("personId") or item.get("person_id"))
        if person_id not in valid_person_ids:
            validation_debug.append(
                {
                    "level": "warning",
                    "pathId": path_id,
                    "pathIndex": path_index,
                    "evidenceIndex": evidence_index,
                    "field": "shared_evidence.personId",
                    "message": "shared_evidence is not bound to a valid personId",
                    "personId": person_id,
                }
            )


def _drop_path(
    path: dict[str, Any],
    reason: str,
    *,
    path_index: int,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "pathId": _path_id(path, path_index),
        "name": _text(path.get("name")),
        "dropReason": reason,
        "pathIndex": path_index,
        **(details or {}),
    }


def _path_id(path: dict[str, Any], index: int) -> str:
    return _text(path.get("id")) or f"path_index_{index}"


def _person_id(person: dict[str, Any]) -> str:
    return _text(person.get("id") or person.get("personId") or person.get("person_id"))


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_text(item) for item in value if _text(item)]


def _has_active_choice_expression(name: str) -> bool:
    return any(marker in name for marker in ACTIVE_CHOICE_PATH_NAME_MARKERS)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()
