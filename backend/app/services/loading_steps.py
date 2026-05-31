from __future__ import annotations

import re
from typing import Any


MATCHING_PUBLIC_EXPERIENCE_TEXT = "正在从知乎真实内容中筛选"


def build_loading_steps(
    query: str,
    clarification: str | None,
    query_context: dict[str, Any] | None,
    search_keywords: list[str] | None,
) -> list[dict[str, str]]:
    context = query_context or {}
    topics = _first_non_empty_list(
        context.get("must_include_topics"),
        context.get("topic_tags"),
        context.get("topicTags"),
        context.get("focus_tags"),
        context.get("focusTags"),
    )
    keywords = _to_text_list(search_keywords)

    return [
        {"label": "读取问题", "value": _text(query)},
        {
            "label": "识别关键处境",
            "value": _join_first_three(topics) or "正在从你的描述里提取线索",
        },
        {
            "label": "生成搜索线索",
            "value": _join_first_three(keywords) or "围绕这个问题查找真实经历",
        },
        {"label": "匹配公开经历", "value": MATCHING_PUBLIC_EXPERIENCE_TEXT},
    ]


def _first_non_empty_list(*values: Any) -> list[str]:
    for value in values:
        items = _to_text_list(value)
        if items:
            return items
    return []


def _join_first_three(values: list[str]) -> str:
    return "、".join(values[:3])


def _to_text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [_text(item) for item in value if _text(item)]
    if isinstance(value, str):
        return [_text(item) for item in re.split(r"[、,，/]", value) if _text(item)]
    return [_text(value)] if _text(value) else []


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
