from __future__ import annotations

import copy
from collections import Counter
from typing import Any


CLUSTER_META = {
    "return_to_work": {
        "id": "path_return_to_work",
        "name": "裸辞后重新找工作",
    },
    "freelance_trials": {
        "id": "path_freelance_trials",
        "name": "裸辞后自由职业试错",
    },
    "public_exam": {
        "id": "path_public_exam",
        "name": "裸辞后考公/考编",
    },
    "rest_then_restart": {
        "id": "path_rest_then_restart",
        "name": "裸辞后先休整再重启",
    },
    "low_pressure_life": {
        "id": "path_low_pressure_life",
        "name": "裸辞后换低压生活方式",
    },
    "hometown_low_cost": {
        "id": "path_hometown_low_cost",
        "name": "裸辞后回老家/低成本生活",
    },
    "other_related_experience": {
        "id": "path_other_related_experience",
        "name": "其他相近真实经历",
    },
}


def cluster_people_drafts(
    people_draft: list[dict[str, Any]],
    query: str,
    understanding: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    people_draft_with_path: list[dict[str, Any]] = []

    for person in people_draft:
        cluster_key = _resolve_cluster_key(person)
        meta = CLUSTER_META[cluster_key]
        person_with_path = copy.deepcopy(person)
        person_with_path["pathId"] = meta["id"]
        people_draft_with_path.append(person_with_path)
        groups.setdefault(cluster_key, []).append(person_with_path)

    paths_draft = [
        _build_path(cluster_key, samples, query=query, understanding=understanding)
        for cluster_key, samples in groups.items()
    ]
    paths_draft.sort(key=_path_sort_key)
    for path in paths_draft:
        path.pop("_sort_full_story_count", None)
        path.pop("_sort_high_confidence_count", None)
    path_order = {path["id"]: index for index, path in enumerate(paths_draft)}
    people_draft_with_path.sort(
        key=lambda item: (
            path_order.get(str(item.get("pathId")), 999),
            _confidence_rank(str(item.get("confidence", ""))),
            -_sample_type_rank(str(item.get("sample_type", ""))),
            str(item.get("id", "")),
        )
    )
    return paths_draft, people_draft_with_path


def _resolve_cluster_key(person: dict[str, Any]) -> str:
    suggested_cluster = _text(person.get("suggested_cluster"))
    cluster_key = _cluster_key_from_text(suggested_cluster)
    if cluster_key:
        return cluster_key

    choice_action = _text(person.get("choice_action"))
    outcome = _text(person.get("outcome"))
    constraints = " ".join(str(item) for item in person.get("constraints") or [])
    fallback_text = f"{choice_action} {outcome} {constraints}"
    cluster_key = _cluster_key_from_text(fallback_text)
    return cluster_key or "other_related_experience"


def _cluster_key_from_text(value: str) -> str:
    if not value:
        return ""
    if any(marker in value for marker in ("重新找工作", "找工作", "投简历", "面试", "重回职场", "回职场")):
        return "return_to_work"
    if any(marker in value for marker in ("自由职业", "副业", "接单", "收入不稳定")):
        return "freelance_trials"
    if any(marker in value for marker in ("考公", "考编", "上岸")):
        return "public_exam"
    if any(marker in value for marker in ("回老家", "低成本")):
        return "hometown_low_cost"
    if any(marker in value for marker in ("低压", "生活方式")):
        return "low_pressure_life"
    if any(marker in value for marker in ("休整", "重启", "内耗", "健康", "迷茫")):
        return "rest_then_restart"
    return ""


def _build_path(
    cluster_key: str,
    samples: list[dict[str, Any]],
    query: str,
    understanding: dict[str, Any],
) -> dict[str, Any]:
    meta = CLUSTER_META[cluster_key]
    sample_ids = [_text(sample.get("id")) for sample in samples if _text(sample.get("id"))]
    return {
        "id": meta["id"],
        "name": meta["name"],
        "desc": _build_desc(cluster_key, samples),
        "count": len(samples),
        "evidence_count": len(sample_ids),
        "cluster_key": cluster_key,
        "sample_ids": sample_ids,
        "_sort_full_story_count": _full_story_count(samples),
        "_sort_high_confidence_count": _high_confidence_count(samples),
    }


def _build_desc(cluster_key: str, samples: list[dict[str, Any]]) -> str:
    return {
        "return_to_work": "他们裸辞后主要回到求职轨道，在投简历、面试和降预期中重新找位置。",
        "freelance_trials": "他们把裸辞后的空档用来试副业、接单或自由职业，也承担收入波动。",
        "public_exam": "他们把考公考编作为阶段性方向，但结果不一定稳定或成功。",
        "rest_then_restart": "他们没有马上求职，而是先停下来恢复状态，再慢慢判断下一步。",
        "low_pressure_life": "他们转向更低压的生活方式，但仍要重新安排收入和日常。",
        "hometown_low_cost": "他们选择回老家或降低生活成本，用更低压力重新观察职业方向。",
        "other_related_experience": "这些样本选择不完全相同，但都记录了裸辞后的真实处境。",
    }.get(cluster_key, "这些样本选择不完全相同，但都记录了裸辞后的真实处境。")


def _build_outcome_sentence(outcomes: list[str]) -> str:
    if not outcomes:
        return "原文不一定完整交代最终结果。"
    return f"其中一部分样本提到{_join_values(outcomes[:2])}等阶段性结果。"


def _top_values(values: Any) -> list[str]:
    counter: Counter[str] = Counter()
    for value in values:
        text = _text(value)
        if text:
            counter[text] += 1
    return [value for value, _ in counter.most_common()]


def _join_values(values: list[str]) -> str:
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    return "、".join(values)


def _path_sort_key(path: dict[str, Any]) -> tuple[int, int, int, int, str]:
    return (
        -int(path.get("count") or 0),
        -int(path.get("evidence_count") or 0),
        -int(path.get("_sort_full_story_count") or 0),
        -int(path.get("_sort_high_confidence_count") or 0),
        str(path.get("id", "")),
    )


def _full_story_count(samples: list[dict[str, Any]]) -> int:
    return sum(1 for sample in samples if sample.get("sample_type") == "full_story")


def _high_confidence_count(samples: list[dict[str, Any]]) -> int:
    return sum(1 for sample in samples if sample.get("confidence") == "high")


def _sample_type_rank(sample_type: str) -> int:
    return {"full_story": 3, "partial_experience": 2, "opinion_with_experience": 1}.get(
        sample_type,
        0,
    )


def _confidence_rank(confidence: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(confidence, 3)


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
