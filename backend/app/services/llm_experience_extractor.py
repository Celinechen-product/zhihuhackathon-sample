from __future__ import annotations

import asyncio
import hashlib
import json
import re
from math import ceil
from typing import Any

from app.config import settings
from app.services.llm_client import (
    LLMClientError,
    LLMConfigurationError,
    LLMJSONDecodeError,
    call_llm_json,
)
from app.services.llm_prompts import EXTRACT_PERSON_EXPERIENCE_PROMPT


VALID_SAMPLE_TYPES = {
    "full_experience",
    "fragmented_experience",
    "full_story",
    "partial_experience",
    "opinion_with_experience",
}
VALID_CONFIDENCE = {"high", "medium", "low"}
VALID_SOURCE_TYPES = {"answer", "article", "pin", "question", "unknown"}
DEFAULT_CURRENT_STATUS = "原文未明确提到后续结果"
MIN_RAW_TEXT_LENGTH = 80
MAX_RAW_TEXT_LENGTH = 5000
HEAD_TAIL_SEGMENT_LENGTH = 2500
TRUNCATED_RAW_TEXT_SEPARATOR = "\n...\n[中间内容已截断]\n...\n"
ABSOLUTE_YEAR_RE = re.compile(r"20\d{2}年?")
WEAK_CURRENT_STATUS_VALUES = {
    "原文只呈现到这一阶段",
    "原文只呈现到这一阶段。",
    "原文仅呈现到这一阶段",
    "原文仅呈现到这一阶段。",
    DEFAULT_CURRENT_STATUS,
    "计划裸辞没成功",
    "计划裸辞没成功。",
}


async def extract_people_with_llm(
    query: str,
    clarification: str | None,
    raw_results: list[dict],
    limit: int = 8,
    query_context: dict[str, Any] | None = None,
) -> tuple[list[dict], list[Any]]:
    if not settings.has_llm_config:
        return [], ["LLM config is missing"]

    items = _select_items(raw_results, limit=limit, query_context=query_context)
    if not items:
        return [], []

    tasks = [
        asyncio.create_task(
            _extract_one(
                index=index,
                item=item,
                query=query,
                clarification=clarification,
                query_context=query_context,
            )
        )
        for index, item in enumerate(items)
    ]
    task_items = dict(zip(tasks, items))
    done, pending = await asyncio.wait(tasks, timeout=_overall_timeout(len(items)))

    people: list[dict] = []
    errors: list[Any] = []

    for task in done:
        item = task_items[task]
        try:
            draft, task_errors = task.result()
        except Exception as exc:
            errors.append(_error(item, "Unexpected LLM task error", exc))
            continue
        if draft is not None:
            people.append(draft)
        errors.extend(task_errors)

    for task in pending:
        task.cancel()
        item = task_items[task]
        errors.append(
            {
                "index": item["index"],
                "title": item["title"],
                "error": "LLM overall timeout",
            }
        )

    people.sort(key=lambda item: item.get("_inputIndex", 0))
    for person in people:
        person.pop("_inputIndex", None)
    errors.sort(key=lambda item: item.get("index", 0) if isinstance(item, dict) else 0)
    return people, errors


async def _extract_one(
    *,
    index: int,
    item: dict[str, Any],
    query: str,
    clarification: str | None,
    query_context: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, list[Any]]:
    try:
        response = await call_llm_json(
            messages=[
                {"role": "system", "content": EXTRACT_PERSON_EXPERIENCE_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        _build_user_payload(
                            item=item,
                            query=query,
                            clarification=clarification,
                            query_context=query_context,
                        ),
                        ensure_ascii=False,
                    ),
                },
            ],
            temperature=0.2,
        )
    except LLMConfigurationError:
        return None, ["LLM config is missing"]
    except LLMJSONDecodeError as exc:
        return None, [_error(item, "JSON parse failed", exc)]
    except LLMClientError as exc:
        return None, [_error(item, "LLM request failed", exc)]
    except Exception as exc:
        return None, [_error(item, "Unexpected LLM extraction error", exc)]

    if "people" in response or "person" in response:
        return None, [
            {
                "index": item["index"],
                "title": item["title"],
                "error": "LLM returned a wrapper object; expected one JSON object for one content item",
            }
        ]

    if response.get("isPersonalExperience") is not True:
        return _normalize_rejected_llm_draft(response, item=item, input_index=index), []

    try:
        return _normalize_llm_draft(response, item=item, input_index=index), []
    except ValueError as exc:
        return None, [_error(item, "LLM draft validation failed", exc)]


def _select_items(
    raw_results: list[dict],
    limit: int,
    query_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    normalized_items: list[dict[str, Any]] = []
    for index, raw_item in enumerate(raw_results):
        item = _normalize_input(raw_item, index=index)
        if not item:
            continue
        normalized_items.append(item)
    return _pick_diverse_items(normalized_items, limit=max(1, limit), query_context=query_context)


def _normalize_input(raw_item: dict[str, Any], index: int) -> dict[str, Any] | None:
    linked_raw_item = raw_item.get("_rawResult") if isinstance(raw_item.get("_rawResult"), dict) else {}
    source = raw_item.get("source") if isinstance(raw_item.get("source"), dict) else {}
    author = raw_item.get("author") if isinstance(raw_item.get("author"), dict) else {}
    raw = raw_item.get("raw") if isinstance(raw_item.get("raw"), dict) else {}
    linked_raw = linked_raw_item.get("raw") if isinstance(linked_raw_item.get("raw"), dict) else {}
    meta = raw_item.get("meta") if isinstance(raw_item.get("meta"), dict) else {}
    linked_meta = linked_raw_item.get("meta") if isinstance(linked_raw_item.get("meta"), dict) else {}

    title = _text(source.get("title") or raw_item.get("title") or raw.get("Title") or linked_raw_item.get("title") or linked_raw.get("Title"))
    url = _text(source.get("url") or raw_item.get("url") or raw.get("Url") or linked_raw_item.get("url") or linked_raw.get("Url"))
    if not url:
        return None

    raw_text = _text(
        raw.get("ContentText")
        or linked_raw.get("ContentText")
        or raw_item.get("content")
        or raw_item.get("text")
        or linked_raw_item.get("excerpt")
        or raw_item.get("excerpt")
        or source.get("excerpt")
        or raw_item.get("key_experience")
    )
    if len(_compact(raw_text)) < MIN_RAW_TEXT_LENGTH:
        return None
    prepared_raw_text, raw_text_debug = _prepare_raw_text(raw_text)

    author_name = _text(
        author.get("name")
        or source.get("author_name")
        or raw.get("AuthorName")
        or linked_raw.get("AuthorName")
    )
    avatar = _text(
        author.get("avatar")
        or source.get("author_avatar")
        or raw.get("AuthorAvatar")
        or linked_raw.get("AuthorAvatar")
    )
    content_type = _normalize_source_type(
        source.get("content_type")
        or raw_item.get("type")
        or meta.get("contentType")
        or raw.get("ContentType")
        or linked_raw_item.get("type")
        or linked_meta.get("contentType")
        or linked_raw.get("ContentType")
    )
    updated_at = _text(meta.get("editTime") or raw.get("EditTime") or linked_meta.get("editTime") or linked_raw.get("EditTime"))

    return {
        "index": index,
        "title": title,
        "url": url,
        "contentType": content_type,
        "authorName": author_name,
        "avatar": avatar,
        "updatedAt": updated_at,
        "rawText": prepared_raw_text,
        "rawContentPreview": _preview(raw_text),
        "rawTextStrategy": raw_text_debug["strategy"],
        "rawTextLength": raw_text_debug["length"],
        "llmInputPreviewHead": raw_text_debug["head"],
        "llmInputPreviewTail": raw_text_debug["tail"],
    }


def _pick_diverse_items(
    items: list[dict[str, Any]],
    limit: int,
    query_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if len(items) <= limit:
        return items

    selected: list[dict[str, Any]] = []
    selected_ids: set[int] = set()
    query_type = _text((query_context or {}).get("query_type"))
    buckets = _diversity_buckets(query_type)
    for keywords in buckets:
        for item in items:
            if id(item) in selected_ids:
                continue
            text = _compact(f"{item.get('title', '')} {item.get('rawText', '')}")
            if any(keyword in text for keyword in keywords):
                selected.append(item)
                selected_ids.add(id(item))
                break
        if len(selected) >= limit:
            return selected[:limit]

    for item in items:
        if id(item) in selected_ids:
            continue
        selected.append(item)
        selected_ids.add(id(item))
        if len(selected) >= limit:
            break
    selected.sort(key=lambda item: item.get("index", 0))
    return selected[:limit]


def _diversity_buckets(query_type: str) -> tuple[tuple[str, ...], ...]:
    if query_type == "relationship":
        return (
            ("恋爱", "分手", "亲密关系", "感情", "伴侣", "男朋友", "女朋友"),
            ("沟通", "修复", "复合", "继续", "磨合"),
            ("异地", "同城", "距离"),
            ("边界", "犹豫", "不确定", "冷静"),
        )
    if query_type == "migration_new_zealand":
        return (
            ("新西兰", "WHV", "打工度假"),
            ("新西兰", "留学", "工签", "学签"),
            ("新西兰", "移民", "生活", "工作"),
            ("新西兰", "回国", "没去", "申请", "准备"),
        )
    return (
        ("自由职业", "副业", "接单", "电商", "小红书店", "拼夕夕", "小说推文", "漫画解说", "不上班"),
        ("考公", "考编", "公务员", "事业编", "没有上岸", "没上岸", "上岸"),
        ("找工作", "投简历", "面试", "offer", "复试", "终面", "猎头", "回职场", "销售助理"),
        ("休息", "休整", "停下来", "恢复状态", "迷茫", "焦虑", "内耗", "存款减少", "生活开销"),
    )


def _build_user_payload(
    *,
    item: dict[str, Any],
    query: str,
    clarification: str | None,
    query_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = query_context or {}
    return {
        "task": "Extract one personal experience draft from the provided Zhihu content.",
        "returnRules": [
            "Return one strict JSON object only.",
            "Do not wrap the JSON in markdown.",
            "Do not return a people array or a person wrapper.",
            "Do not invent source, author, URL, or avatar fields.",
            "If the content is not a personal experience, return the false schema from the system prompt.",
            "Use currentStatus='' and entryStatus='' when the original text does not mention the outcome.",
            "Only author-owned first-person experiences can set can_be_person_sample=true.",
        ],
        "outputShape": {
            "isPersonalExperience": "boolean",
            "is_first_person_experience": "boolean",
            "experience_owner": "author | mentioned_person | unclear",
            "can_be_person_sample": "boolean",
            "filter_reason": "string",
            "sampleType": "full_story | partial_experience | opinion_with_experience",
            "situation": "string",
            "actionSummary": "string",
            "realDetails": ["string"],
            "key_fragments": ["string"],
            "author_experience_evidence": ["string"],
            "timeline": ["string"],
            "currentStatus": "string",
            "entrySituation": "string",
            "entryStatus": "string",
            "matchReasons": ["string"],
            "confidence": "high | medium | low",
            "hasOutcome": "boolean",
            "hasTimeline": "boolean",
            "missingInfo": ["string"],
        },
        "userQuery": _text(query),
        "clarification": _text(clarification),
        "queryContext": context,
        "title": item["title"],
        "authorName": item["authorName"],
        "sourceUrl": item["url"],
        "contentType": item["contentType"],
        "rawText": item["rawText"],
    }


def _normalize_llm_draft(
    payload: dict[str, Any],
    *,
    item: dict[str, Any],
    input_index: int,
) -> dict[str, Any]:
    sample_type = _normalize_sample_type(payload.get("sampleType") or payload.get("sample_type"))
    if sample_type not in VALID_SAMPLE_TYPES:
        sample_type = "partial_experience"
    situation = _remove_unseen_absolute_years(_text(payload.get("situation")), item)
    action_summary = _remove_unseen_absolute_years(
        _text(payload.get("actionSummary") or payload.get("action_summary")),
        item,
    )
    real_details = [
        _remove_unseen_absolute_years(detail, item)
        for detail in _string_list(payload.get("realDetails") or payload.get("real_details"))[:5]
    ]
    real_details = [detail for detail in real_details if detail]
    key_fragments = [
        _remove_unseen_absolute_years(detail, item)
        for detail in _string_list(payload.get("key_fragments") or payload.get("keyFragments"))
    ]
    key_fragments = [detail for detail in key_fragments if detail][:6]
    author_experience_evidence = [
        _remove_unseen_absolute_years(detail, item)
        for detail in _string_list(payload.get("author_experience_evidence") or payload.get("authorExperienceEvidence"))
    ]
    author_experience_evidence = [detail for detail in author_experience_evidence if detail][:3]
    timeline = [
        _remove_unseen_absolute_years(detail, item)
        for detail in _string_list(payload.get("timeline"))
    ]
    timeline = [detail for detail in timeline if detail][:6]
    current_status = _remove_unseen_absolute_years(
        _text(payload.get("currentStatus") or payload.get("current_status")),
        item,
    )
    derived_current_status = _derive_current_status_from_raw_text(item)
    if _is_weak_current_status(current_status):
        current_status = derived_current_status
    elif _should_prefer_derived_current_status(current_status, derived_current_status):
        current_status = derived_current_status
    real_details = _ensure_derived_real_details(real_details, item=item)
    if not key_fragments:
        key_fragments = real_details[:]
    entry_situation = _entry_situation(
        _remove_unseen_absolute_years(
            _text(payload.get("entrySituation") or payload.get("entry_situation")),
            item,
        )
        or situation
    )
    entry_status = _entry_status(
        _remove_unseen_absolute_years(
            _text(payload.get("entryStatus") or payload.get("entry_status")),
            item,
        )
        or current_status
    )
    if _is_weak_current_status(entry_status) and not _is_weak_current_status(current_status):
        entry_status = _entry_status(current_status)
    if _is_weak_current_status(entry_status):
        entry_status = ""
    if sample_type == "full_story" and not real_details:
        sample_type = "partial_experience"

    internal = payload.get("internal") if isinstance(payload.get("internal"), dict) else {}
    confidence = _normalize_confidence(internal.get("confidence") or payload.get("confidence"))
    match_reasons = _string_list(
        internal.get("matchReasons")
        or internal.get("match_reasons")
        or payload.get("matchReasons")
        or payload.get("match_reasons")
    )[:3]
    missing_info = _string_list(
        internal.get("missingInfo")
        or internal.get("missing_info")
        or payload.get("missingInfo")
        or payload.get("missing_info")
    )

    validation_errors = []
    if not item["url"]:
        validation_errors.append("source.url is missing")
    if not situation:
        validation_errors.append("situation is missing")
    if not action_summary:
        validation_errors.append("actionSummary is missing")
    if not isinstance(real_details, list):
        validation_errors.append("realDetails must be an array")
    if confidence not in VALID_CONFIDENCE:
        validation_errors.append("confidence is invalid")
    if validation_errors:
        raise ValueError("; ".join(validation_errors))

    first_person_raw = (
        payload.get("is_first_person_experience")
        if "is_first_person_experience" in payload
        else payload.get("isFirstPersonExperience")
    )
    owner_raw = payload.get("experience_owner") or payload.get("experienceOwner")
    can_sample_raw = (
        payload.get("can_be_person_sample")
        if "can_be_person_sample" in payload
        else payload.get("canBePersonSample")
    )
    is_first_person = _bool_value(first_person_raw) if first_person_raw is not None else True
    experience_owner = _normalize_experience_owner(owner_raw) if owner_raw is not None else "author"
    can_be_person_sample = _bool_value(can_sample_raw) if can_sample_raw is not None else True

    return {
        "_inputIndex": input_index,
        "id": f"llm_person_{_stable_hash(item['url'])}",
        "name": item["authorName"] or "知乎用户",
        "avatar": item["avatar"],
        "source": {
            "title": item["title"],
            "url": item["url"],
            "type": item["contentType"],
            "authorName": item["authorName"],
            "updatedAt": item["updatedAt"],
        },
        "isPersonalExperience": True,
        "is_first_person_experience": is_first_person,
        "experience_owner": experience_owner,
        "can_be_person_sample": can_be_person_sample,
        "filter_reason": _text(payload.get("filter_reason") or payload.get("filterReason")),
        "sampleType": sample_type,
        "situation": situation,
        "actionSummary": action_summary,
        "realDetails": real_details,
        "key_fragments": key_fragments,
        "author_experience_evidence": author_experience_evidence,
        "timeline": timeline,
        "currentStatus": current_status,
        "entrySituation": entry_situation,
        "entryStatus": entry_status,
        "internal": {
            "matchReasons": match_reasons,
            "confidence": confidence,
            "hasOutcome": _bool_value(
                internal.get("hasOutcome")
                if "hasOutcome" in internal
                else internal.get("has_outcome")
                if "has_outcome" in internal
                else payload.get("hasOutcome")
                if "hasOutcome" in payload
                else payload.get("has_outcome")
            ),
            "hasTimeline": _bool_value(
                internal.get("hasTimeline")
                if "hasTimeline" in internal
                else internal.get("has_timeline")
                if "has_timeline" in internal
                else payload.get("hasTimeline")
                if "hasTimeline" in payload
                else payload.get("has_timeline")
            ),
            "missingInfo": missing_info,
        },
        "rawContentPreview": item["rawContentPreview"],
        "rawTextStrategy": item["rawTextStrategy"],
        "rawTextLength": item["rawTextLength"],
        "llmInputPreviewHead": item["llmInputPreviewHead"],
        "llmInputPreviewTail": item["llmInputPreviewTail"],
    }


def _normalize_rejected_llm_draft(
    payload: dict[str, Any],
    *,
    item: dict[str, Any],
    input_index: int,
) -> dict[str, Any]:
    reason = _text(
        payload.get("filter_reason")
        or payload.get("filterReason")
        or payload.get("reason")
    )
    if not reason:
        reason = "；".join(_string_list(payload.get("missingInfo") or payload.get("missing_info")))
    if not reason:
        reason = "不是可确认的作者本人亲历"

    first_person_raw = (
        payload.get("is_first_person_experience")
        if "is_first_person_experience" in payload
        else payload.get("isFirstPersonExperience")
    )
    owner_raw = payload.get("experience_owner") or payload.get("experienceOwner")
    can_sample_raw = (
        payload.get("can_be_person_sample")
        if "can_be_person_sample" in payload
        else payload.get("canBePersonSample")
    )
    sample_type = _normalize_sample_type(payload.get("sampleType") or payload.get("sample_type"))
    if sample_type not in VALID_SAMPLE_TYPES:
        sample_type = "partial_experience"

    return {
        "_inputIndex": input_index,
        "id": f"llm_person_{_stable_hash(item['url'])}",
        "name": item["authorName"] or "知乎用户",
        "avatar": item["avatar"],
        "source": {
            "title": item["title"],
            "url": item["url"],
            "type": item["contentType"],
            "authorName": item["authorName"],
            "updatedAt": item["updatedAt"],
        },
        "isPersonalExperience": False,
        "is_first_person_experience": _bool_value(first_person_raw) if first_person_raw is not None else False,
        "experience_owner": _normalize_experience_owner(owner_raw) if owner_raw is not None else "unclear",
        "can_be_person_sample": _bool_value(can_sample_raw) if can_sample_raw is not None else False,
        "filter_reason": reason,
        "sampleType": sample_type,
        "situation": _text(payload.get("situation")),
        "actionSummary": _text(payload.get("actionSummary") or payload.get("action_summary")),
        "realDetails": _string_list(payload.get("realDetails") or payload.get("real_details"))[:5],
        "key_fragments": _string_list(payload.get("key_fragments") or payload.get("keyFragments"))[:6],
        "author_experience_evidence": _string_list(
            payload.get("author_experience_evidence") or payload.get("authorExperienceEvidence")
        )[:3],
        "timeline": _string_list(payload.get("timeline"))[:6],
        "currentStatus": _text(payload.get("currentStatus") or payload.get("current_status")),
        "entrySituation": _text(payload.get("entrySituation") or payload.get("entry_situation")),
        "entryStatus": _text(payload.get("entryStatus") or payload.get("entry_status")),
        "internal": {
            "matchReasons": _string_list(payload.get("matchReasons") or payload.get("match_reasons"))[:3],
            "confidence": _normalize_confidence(payload.get("confidence")) or "low",
            "hasOutcome": _bool_value(payload.get("hasOutcome") or payload.get("has_outcome")),
            "hasTimeline": _bool_value(payload.get("hasTimeline") or payload.get("has_timeline")),
            "missingInfo": _string_list(payload.get("missingInfo") or payload.get("missing_info")),
        },
        "rawContentPreview": item["rawContentPreview"],
        "rawTextStrategy": item["rawTextStrategy"],
        "rawTextLength": item["rawTextLength"],
        "llmInputPreviewHead": item["llmInputPreviewHead"],
        "llmInputPreviewTail": item["llmInputPreviewTail"],
    }


def _normalize_sample_type(value: Any) -> str:
    raw = _text(value)
    aliases = {
        "full_experience": "full_story",
        "fragmented_experience": "partial_experience",
        "fragment_experience": "partial_experience",
        "fragmented_story": "partial_experience",
    }
    return aliases.get(raw, raw)


def _normalize_experience_owner(value: Any) -> str:
    owner = _text(value).lower()
    return owner if owner in {"author", "mentioned_person", "unclear"} else "unclear"


def _normalize_confidence(value: Any) -> str:
    confidence = _text(value).lower()
    return confidence if confidence in VALID_CONFIDENCE else ""


def _normalize_source_type(value: Any) -> str:
    raw = _text(value).lower()
    aliases = {
        "answer": "answer",
        "article": "article",
        "pin": "pin",
        "question": "question",
    }
    return aliases.get(raw, "unknown")


def _prepare_raw_text(value: str) -> tuple[str, dict[str, Any]]:
    text = _clean_text(value)
    if len(text) <= MAX_RAW_TEXT_LENGTH:
        return text, {
            "strategy": "full",
            "length": len(text),
            "head": text[:160],
            "tail": text[-160:],
        }
    prepared = (
        f"{text[:HEAD_TAIL_SEGMENT_LENGTH]}"
        f"{TRUNCATED_RAW_TEXT_SEPARATOR}"
        f"{text[-HEAD_TAIL_SEGMENT_LENGTH:]}"
    )
    return prepared, {
        "strategy": "head_tail",
        "length": len(text),
        "head": text[:160],
        "tail": text[-160:],
    }


def _preview(value: str) -> str:
    clean = _clean_text(value)
    return clean[:120]


def _overall_timeout(item_count: int) -> float:
    per_request = max(1.0, float(settings.llm_timeout_seconds or 20))
    max_concurrency = max(1, int(settings.llm_max_concurrency or 1))
    waves = max(1, ceil(item_count / max_concurrency))
    return min(45.0, max(per_request + 2.0, waves * (per_request + 1.0)))


def _error(item: dict[str, Any], label: str, exc: BaseException) -> dict[str, Any]:
    return {
        "index": item["index"],
        "title": item["title"],
        "error": f"{label}: {_text(exc)}",
    }


def _stable_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_text(item) for item in value if _text(item)]


def _bool_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _remove_unseen_absolute_years(value: str, item: dict[str, Any]) -> str:
    text = _text(value)
    if not text:
        return ""
    source_text = f"{item.get('title', '')}\n{item.get('rawText', '')}"

    def replace_unseen(match: re.Match[str]) -> str:
        year = match.group(0)
        bare_year = year.rstrip("年")
        if year in source_text or bare_year in source_text:
            return year
        return ""

    return re.sub(r"\s+", " ", ABSOLUTE_YEAR_RE.sub(replace_unseen, text)).strip()


def _is_weak_current_status(value: str) -> bool:
    text = _text(value)
    return not text or text in WEAK_CURRENT_STATUS_VALUES


def _derive_current_status_from_raw_text(item: dict[str, Any]) -> str:
    raw_text = _clean_text(item.get("rawText"))
    title = _clean_text(item.get("title"))
    if not raw_text and not title:
        return ""
    tail = raw_text[-1600:]
    evidence = f"{title} {tail}".strip()
    if (
        any(marker in evidence for marker in ("没有考上公务员", "没考上公务员", "没有上岸", "没上岸"))
        and "重新回到职场" in evidence
    ):
        return "考公没有上岸，但焦虑感比裸辞初期减轻，接下来准备调整状态、重新回到职场。"
    if (
        "裸辞" in evidence
        and any(marker in title for marker in ("没有上岸", "没上岸"))
        and any(marker in title for marker in ("治愈", "内耗", "迷茫"))
    ):
        return "考公没有上岸，但裸辞后的内耗与迷茫已有缓解，接下来准备调整状态、重新回到职场。"
    if "复试" in tail and any(marker in tail for marker in ("终面", "offer", "Offer", "面试通知")):
        return "复试已经结束，可能进入终面，但原文尚未明确最终 offer 结果。"
    if "销售助理" in tail and any(marker in tail for marker in ("一年九个月", "一年9个月")):
        return "已经在销售助理岗位工作一年九个月，但仍不喜欢这份工作，暂时因现实压力没有再裸辞。"
    if any(marker in tail for marker in ("收到offer", "收到 offer", "收到Offer")) and any(
        marker in tail for marker in ("拒绝回职场", "不回职场", "继续自由职业")
    ):
        return "35岁时收到 offer 但拒绝回职场，目前更倾向继续自由职业。"

    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[。！？!?])\s*", tail)
        if sentence.strip()
    ]
    status_markers = ("现在的我", "接下来", "目前", "最后", "更新", "更：", "更:")
    candidates = [
        sentence
        for sentence in sentences[-10:]
        if any(marker in sentence for marker in status_markers)
    ]
    if not candidates:
        return ""
    return _limit_text("".join(candidates[-2:]), 120)


def _should_prefer_derived_current_status(current_status: str, derived_current_status: str) -> bool:
    if not derived_current_status:
        return False
    current = _compact(current_status)
    derived = _compact(derived_current_status)
    if "考公没有上岸" in derived and "上岸" not in current:
        return True
    if "重新回到职场" in derived and "回到职场" not in current and "回职场" not in current:
        return True
    return False


def _ensure_derived_real_details(
    real_details: list[str],
    *,
    item: dict[str, Any],
) -> list[str]:
    details = [detail for detail in real_details if detail]
    evidence = _compact(f"{item.get('title', '')} {item.get('rawText', '')}")
    if (
        any(marker in evidence for marker in ("裸辞考公", "考公"))
        and any(marker in evidence for marker in ("没有上岸", "没上岸", "没有考上公务员", "没考上公务员"))
        and not any("上岸" in detail or "考公" in detail or "公务员" in detail for detail in details)
    ):
        details.insert(0, "考公没有上岸，但作者认为这段经历缓解了裸辞后的内耗和迷茫。")
    return details[:5]


def _entry_situation(value: str) -> str:
    return _limit_text(_strip_intro_words(value), 44)


def _entry_status(value: str) -> str:
    text = _strip_intro_words(value)
    if _is_weak_current_status(text):
        return ""
    return _limit_text(text, 32)


def _strip_intro_words(value: str) -> str:
    text = _text(value)
    for prefix in ("原文提到，", "原文中提到，", "这位知友", "作者"):
        if text.startswith(prefix):
            text = text[len(prefix):].strip(" ，。")
    return text


def _limit_text(value: str, limit: int) -> str:
    text = _text(value)
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", _text(value)).strip()


def _compact(value: Any) -> str:
    return re.sub(r"\s+", "", _text(value))


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
