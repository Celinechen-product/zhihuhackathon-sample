from __future__ import annotations

import uuid
from typing import Any

from app.services.loading_steps import build_loading_steps


def build_analysis(query: str, understanding: dict[str, Any] | None = None) -> dict[str, Any]:
    understanding = understanding or {}
    core_question = understanding.get("core_question") or query
    return {
        "question_type": understanding.get("question_type") or "other",
        "core_question": core_question,
        "actors": understanding.get("actors") or [],
        "user_state": understanding.get("user_state") or "",
        "goal": understanding.get("goal") or "",
        "constraints": understanding.get("constraints") or [],
        "conflict": understanding.get("conflict") or "",
        "steps": [
            {"title": "读取问题", "text": query},
            {
                "title": "识别核心变量",
                "text": core_question,
            },
            {
                "title": "生成待确认问题",
                "text": "已完成轻量追问判断",
            },
            {
                "title": "匹配公开经历",
                "text": "正在从知乎公开内容中寻找相似经历",
            },
        ],
        "focusTags": understanding.get("focus_tags") or [],
    }


def build_fallback_response(
    *,
    query: str,
    clarification: str,
    combined_query: str,
    understanding: dict[str, Any],
    keywords: list[str],
    query_context: dict[str, Any] | None = None,
    raw_results: list[dict[str, Any]] | None = None,
    experience_candidates: list[dict[str, Any]] | None = None,
    people_draft: list[dict[str, Any]] | None = None,
    paths_draft: list[dict[str, Any]] | None = None,
    people_draft_with_path: list[dict[str, Any]] | None = None,
    llm_enabled: bool = False,
    llm_people_draft: list[dict[str, Any]] | None = None,
    llm_errors: list[Any] | None = None,
    llm_people_used: bool = False,
    llm_people_used_count: int = 0,
    rule_people_fallback_used: bool = False,
    llm_path_assignment_debug: list[dict[str, Any]] | None = None,
    llm_people_filter_debug: list[dict[str, Any]] | None = None,
    path_relevance_debug: list[dict[str, Any]] | None = None,
    dropped_paths: list[dict[str, Any]] | None = None,
    paths: list[dict[str, Any]] | None = None,
    people: list[dict[str, Any]] | None = None,
    result_source: str = "fallback",
    errors: list[dict[str, Any]] | None = None,
    search_fallback_used: bool = False,
    fallback_keywords: list[str] | None = None,
    fallback_raw_results_count: int = 0,
) -> dict[str, Any]:
    raw_results = raw_results or []
    experience_candidates = experience_candidates or []
    people_draft = people_draft or []
    paths_draft = paths_draft or []
    people_draft_with_path = people_draft_with_path or []
    llm_people_draft = llm_people_draft or []
    llm_errors = llm_errors or []
    llm_path_assignment_debug = llm_path_assignment_debug or []
    llm_people_filter_debug = llm_people_filter_debug or []
    path_relevance_debug = path_relevance_debug or []
    dropped_paths = dropped_paths or []
    query_context = query_context or understanding.get("query_context") or {}
    errors = errors or []
    fallback_keywords = fallback_keywords or []
    frontend_paths = paths if paths is not None else _fallback_paths()
    frontend_people = people if people is not None else _fallback_people()
    safe_result_source = result_source if paths is not None and people is not None else "fallback"
    loading_context = {
        **query_context,
        "topic_tags": understanding.get("topic_tags") or [],
        "focusTags": understanding.get("focus_tags") or [],
    }
    loading_steps = build_loading_steps(
        query=query,
        clarification=clarification,
        query_context=loading_context,
        search_keywords=keywords,
    )

    return {
        "queryId": f"query_{uuid.uuid4().hex}",
        "query": query,
        "loadingSteps": loading_steps,
        "analysis": build_analysis(query, understanding),
        "paths": frontend_paths,
        "people": frontend_people,
        "debug": {
            "clarification": clarification,
            "combinedQuery": combined_query,
            "queryContext": query_context,
            "effectiveQuery": query_context.get("effective_query", combined_query),
            "resultSource": safe_result_source,
            "frontendPathsCount": len(frontend_paths),
            "frontendPeopleCount": len(frontend_people),
            "understanding": understanding,
            "keywords": keywords,
            "searchKeywords": keywords,
            "searchFallbackUsed": search_fallback_used,
            "fallbackKeywords": fallback_keywords,
            "fallbackRawResultsCount": fallback_raw_results_count,
            "finalDropSummary": _summarize_drop_reasons(llm_people_filter_debug, path_relevance_debug, dropped_paths),
            "rawResultsCount": len(raw_results),
            "rawResults": raw_results,
            "experienceCandidatesCount": len(experience_candidates),
            "experienceCandidates": experience_candidates,
            "peopleDraftCount": len(people_draft),
            "peopleDraft": people_draft,
            "pathsDraftCount": len(paths_draft),
            "pathsDraft": paths_draft,
            "peopleDraftWithPathCount": len(people_draft_with_path),
            "peopleDraftWithPath": people_draft_with_path,
            "llmEnabled": llm_enabled,
            "llmPeopleDraftCount": len(llm_people_draft),
            "llmPeopleDraft": llm_people_draft,
            "llmErrors": llm_errors,
            "llmPeopleUsed": llm_people_used,
            "llmPeopleUsedCount": llm_people_used_count,
            "rulePeopleFallbackUsed": rule_people_fallback_used,
            "llmPathAssignmentDebug": llm_path_assignment_debug,
            "pathAssignmentDebug": llm_path_assignment_debug,
            "llmPeopleFilterDebug": llm_people_filter_debug,
            "pathRelevanceDebug": path_relevance_debug,
            "droppedPaths": dropped_paths,
            "errors": errors,
        },
    }


def _summarize_drop_reasons(
    llm_people_filter_debug: list[dict[str, Any]],
    path_relevance_debug: list[dict[str, Any]],
    dropped_paths: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for item in llm_people_filter_debug:
        if item.get("kept"):
            continue
        reason = str(item.get("dropReason") or item.get("filter_reason") or "unknown").strip()
        if reason:
            counts[reason] = counts.get(reason, 0) + 1
    for item in path_relevance_debug:
        if item.get("kept"):
            continue
        reason = str(item.get("dropReason") or "path dropped").strip()
        if reason:
            counts[reason] = counts.get(reason, 0) + 1
    for item in dropped_paths:
        reason = str(item.get("dropReason") or "path dropped").strip()
        if reason:
            counts[reason] = counts.get(reason, 0) + 1
    return [
        {"dropReason": reason, "count": count}
        for reason, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _fallback_paths() -> list[dict[str, Any]]:
    return [
        {
            "id": "fallback_path_1",
            "name": "先看相近经历",
            "desc": "当前先展示可用于联调的 fallback 路径，后续会由真实知乎内容聚类生成。",
            "count": 1,
        }
    ]


def _fallback_people() -> list[dict[str, Any]]:
    return [
        {
            "id": "fallback_person_1",
            "sample_type": "partial_experience",
            "contentType": "fragment_experience",
            "name": "知乎用户",
            "pathId": "fallback_path_1",
            "role": "知乎用户",
            "badge": "fallback 联调样本",
            "oneLine": "这是后端联调 fallback 样本，不代表真实知乎经历。",
            "who": "当前知乎搜索或经历抽取尚未完成，先用 fallback 样本保证前端链路可跑通。",
            "matchReasons": [
                "用于验证前端路径页和人物样本卡渲染",
                "后续会替换为真实知乎公开内容",
            ],
            "timeline": [],
            "keyExperience": "暂未完成真实经历抽取。",
            "sourceExcerpt": "",
            "sourceTitle": "fallback source",
            "sourceUrl": "",
            "source": {
                "title": "fallback source",
                "url": "",
                "content_type": "mock",
                "author_name": "",
                "author_avatar": "",
                "excerpt": "",
            },
        }
    ]
