from __future__ import annotations

from typing import Any

from app.config import settings
from app.mock_data import build_fallback_response
from app.services.experience_extractor import extract_people_draft
from app.services.experience_filter import filter_experience_candidates
from app.services.llm_experience_extractor import extract_people_with_llm
from app.services.llm_path_clusterer import cluster_paths_with_llm_debug
from app.services.path_clusterer import cluster_people_drafts
from app.services.query_understanding import (
    build_combined_query,
    build_search_keywords,
    understand_query,
)
from app.services.query_context import build_query_context
from app.services.response_formatter import (
    build_frontend_from_llm_people,
    build_frontend_paths,
    build_frontend_people,
    should_use_real_results,
)
from app.services.zhihu_client import ZhihuClient, ZhihuClientError


async def run_search_pipeline(
    *,
    query: str,
    count: int = 20,
    clarification: str | None = None,
) -> dict[str, Any]:
    safe_count = max(1, min(int(count), 50))
    clean_query = (query or "").strip()
    clean_clarification = (clarification or "").strip()
    combined_query = build_combined_query(clean_query, clean_clarification)
    understanding = understand_query(clean_query, clean_clarification)
    query_context = build_query_context(
        clean_query,
        clean_clarification,
        understanding=understanding,
    )
    understanding["query_context"] = query_context
    understanding["query_type"] = query_context["query_type"]
    understanding["effective_query"] = query_context["effective_query"]
    keywords = build_search_keywords(
        clean_query,
        clean_clarification,
        understanding,
        query_context=query_context,
    )
    understanding["search_keywords"] = keywords

    raw_results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    search_execution_debug: list[dict[str, Any]] = []

    should_try_zhihu = settings.has_zhihu_access_secret and settings.has_zhihu_search_url

    planned_search_keywords = keywords[:5]
    if should_try_zhihu:
        raw_results = await _search_zhihu_keywords(
            planned_search_keywords,
            max_results=safe_count,
            errors=errors,
            execution_debug=search_execution_debug,
            phase="primary",
        )
    else:
        if not settings.has_zhihu_access_secret:
            errors.append(
                {"keyword": "", "error": "Zhihu access secret is not configured"}
            )
        if not settings.has_zhihu_search_url:
            errors.append({"keyword": "", "error": "Zhihu search URL is not configured"})

    deduped_results = _dedupe_results(raw_results)[:safe_count]
    experience_candidates = filter_experience_candidates(
        raw_results=deduped_results,
        query=query_context["effective_query"],
        understanding=understanding,
    )
    llm_input_results = (
        _attach_raw_results_for_llm(experience_candidates, deduped_results)
        if experience_candidates
        else deduped_results[:5]
    )
    llm_people_draft, llm_errors = await extract_people_with_llm(
        query=clean_query,
        clarification=clean_clarification,
        raw_results=llm_input_results,
        limit=8,
        query_context=query_context,
    )
    people_draft = extract_people_draft(
        candidates=experience_candidates,
        query=query_context["effective_query"],
        understanding=understanding,
    )
    paths_draft, people_draft_with_path = cluster_people_drafts(
        people_draft=people_draft,
        query=clean_query,
        understanding=understanding,
    )
    paths: list[dict[str, Any]] | None = None
    people: list[dict[str, Any]] | None = None
    llm_people_used = False
    rule_people_fallback_used = True
    result_source = "fallback"

    if query_context["query_type"] == "career_restart" and should_use_real_results(paths_draft, people_draft_with_path):
        valid_path_ids = {
            str(path.get("id", "")).strip()
            for path in paths_draft
            if str(path.get("id", "")).strip()
        }
        people = build_frontend_people(
            people_draft_with_path,
            valid_path_ids=valid_path_ids,
        )
        paths = build_frontend_paths(paths_draft, frontend_people=people)
        valid_frontend_path_ids = {
            str(path.get("id", "")).strip()
            for path in paths
            if str(path.get("id", "")).strip()
        }
        people = [
            person
            for person in people
            if str(person.get("pathId", "")).strip() in valid_frontend_path_ids
        ]
        if paths and people:
            result_source = "real_zhihu_rule_fallback"
        else:
            paths = None
            people = None

    llm_path_assignment_debug: list[dict[str, Any]] = []
    llm_people_filter_debug: list[dict[str, Any]] = []
    path_relevance_debug: list[dict[str, Any]] = []
    dropped_paths: list[dict[str, Any]] = []
    search_fallback_used = False
    fallback_keywords: list[str] = []
    fallback_raw_results_count = 0
    (
        llm_paths,
        llm_people,
        llm_path_assignment_debug,
        llm_people_filter_debug,
        path_relevance_debug,
        dropped_paths,
    ) = build_frontend_from_llm_people(
        llm_people_draft=llm_people_draft,
        query=clean_query,
        clarification=clean_clarification,
        query_context=query_context,
    )
    if (
        deduped_results
        and not (paths and people)
        and not (llm_paths and llm_people)
        and should_try_zhihu
    ):
        fallback_keywords = _fallback_keywords_for_query_type(
            query_context["query_type"],
            existing_keywords=keywords,
        )
        if fallback_keywords:
            search_fallback_used = True
            fallback_raw_results = await _search_zhihu_keywords(
                fallback_keywords,
                max_results=12,
                errors=errors,
                execution_debug=search_execution_debug,
                phase="fallback",
            )
            fallback_raw_results_count = len(fallback_raw_results)
            if fallback_raw_results:
                raw_results.extend(fallback_raw_results)
                deduped_results = _dedupe_results(raw_results)[
                    : max(safe_count, min(50, safe_count + fallback_raw_results_count))
                ]
                experience_candidates = filter_experience_candidates(
                    raw_results=deduped_results,
                    query=query_context["effective_query"],
                    understanding=understanding,
                )
                llm_input_results = (
                    _attach_raw_results_for_llm(experience_candidates, deduped_results)
                    if experience_candidates
                    else deduped_results[:8]
                )
                llm_people_draft, fallback_llm_errors = await extract_people_with_llm(
                    query=clean_query,
                    clarification=clean_clarification,
                    raw_results=llm_input_results,
                    limit=8,
                    query_context=query_context,
                )
                llm_errors.extend(fallback_llm_errors)
                people_draft = extract_people_draft(
                    candidates=experience_candidates,
                    query=query_context["effective_query"],
                    understanding=understanding,
                )
                paths_draft, people_draft_with_path = cluster_people_drafts(
                    people_draft=people_draft,
                    query=clean_query,
                    understanding=understanding,
                )
                paths = None
                people = None
                llm_people_used = False
                rule_people_fallback_used = True
                result_source = "fallback"
                if query_context["query_type"] == "career_restart" and should_use_real_results(paths_draft, people_draft_with_path):
                    valid_path_ids = {
                        str(path.get("id", "")).strip()
                        for path in paths_draft
                        if str(path.get("id", "")).strip()
                    }
                    people = build_frontend_people(
                        people_draft_with_path,
                        valid_path_ids=valid_path_ids,
                    )
                    paths = build_frontend_paths(paths_draft, frontend_people=people)
                    valid_frontend_path_ids = {
                        str(path.get("id", "")).strip()
                        for path in paths
                        if str(path.get("id", "")).strip()
                    }
                    people = [
                        person
                        for person in people
                        if str(person.get("pathId", "")).strip() in valid_frontend_path_ids
                    ]
                    if paths and people:
                        result_source = "real_zhihu_rule_fallback"
                    else:
                        paths = None
                        people = None
                (
                    llm_paths,
                    llm_people,
                    llm_path_assignment_debug,
                    llm_people_filter_debug,
                    path_relevance_debug,
                    dropped_paths,
                ) = build_frontend_from_llm_people(
                    llm_people_draft=llm_people_draft,
                    query=clean_query,
                    clarification=clean_clarification,
                    query_context=query_context,
                )
    if llm_paths and llm_people:
        paths = llm_paths
        people = llm_people
        llm_people_used = True
        rule_people_fallback_used = False
        result_source = "real_zhihu_llm_people"

    if paths is None or people is None:
        paths = []
        people = []
        if result_source == "fallback":
            result_source = "low_recall_no_valid_people"

    llm_cluster_debug = await cluster_paths_with_llm_debug(
        query=clean_query,
        clarification=clean_clarification,
        query_context=query_context,
        people=people,
        rule_fallback_used=rule_people_fallback_used,
    )

    response = build_fallback_response(
        query=clean_query,
        clarification=clean_clarification,
        combined_query=combined_query,
        understanding=understanding,
        query_context=query_context,
        keywords=keywords,
        raw_results=deduped_results,
        experience_candidates=experience_candidates,
        people_draft=people_draft,
        paths_draft=paths_draft,
        people_draft_with_path=people_draft_with_path,
        llm_enabled=settings.has_llm_config,
        llm_people_draft=llm_people_draft,
        llm_errors=llm_errors,
        llm_people_used=llm_people_used,
        llm_people_used_count=len(people or []) if llm_people_used else 0,
        rule_people_fallback_used=rule_people_fallback_used,
        llm_path_assignment_debug=llm_path_assignment_debug if llm_people_used else [],
        llm_people_filter_debug=llm_people_filter_debug,
        path_relevance_debug=path_relevance_debug,
        dropped_paths=dropped_paths,
        paths=paths,
        people=people,
        result_source=result_source,
        errors=errors,
        search_fallback_used=search_fallback_used,
        fallback_keywords=fallback_keywords,
        fallback_raw_results_count=fallback_raw_results_count,
    )
    response.setdefault("debug", {}).update(llm_cluster_debug)
    response["debug"]["searchRecallDebug"] = _build_search_recall_debug(
        planned_keywords=keywords,
        primary_keywords=planned_search_keywords,
        execution_debug=search_execution_debug,
        raw_results=raw_results,
        deduped_results=deduped_results,
        llm_people_draft=llm_people_draft,
        valid_people=people,
        count=safe_count,
    )
    response["debug"].setdefault("understanding", {})[
        "llmPathClusterDebug"
    ] = llm_cluster_debug
    return response


async def search_life_samples(
    *,
    query: str,
    clarification: str = "",
    count: int = 20,
) -> dict[str, Any]:
    return await run_search_pipeline(
        query=query,
        clarification=clarification,
        count=count,
    )


def _dedupe_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in results:
        key = _result_key(item)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _attach_raw_results_for_llm(
    candidates: list[dict[str, Any]],
    raw_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    raw_by_url = {
        str(item.get("url", "")).strip(): item
        for item in raw_results
        if str(item.get("url", "")).strip()
    }
    enriched = []
    for candidate in candidates:
        source = candidate.get("source") if isinstance(candidate.get("source"), dict) else {}
        url = str(source.get("url", "")).strip()
        item = dict(candidate)
        if url in raw_by_url:
            item["_rawResult"] = raw_by_url[url]
        enriched.append(item)
    return enriched


def _result_key(item: dict[str, Any]) -> str:
    for field in ("url", "id", "title"):
        value = item.get(field)
        if value:
            return f"{field}:{value}"
    return repr(sorted(item.items()))


async def _search_zhihu_keywords(
    keywords: list[str],
    *,
    max_results: int,
    errors: list[dict[str, str]],
    execution_debug: list[dict[str, Any]] | None = None,
    phase: str = "primary",
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    client = ZhihuClient()
    for index, keyword in enumerate(keywords):
        before_count = len(results)
        debug_item = {
            "phase": phase,
            "keyword": keyword,
            "keywordIndex": index,
            "requestedCount": 10,
            "rawResultCount": 0,
            "cumulativeRawBefore": before_count,
            "cumulativeRawAfter": before_count,
            "skipped": False,
            "skipReason": "",
            "error": "",
        }
        if len(results) >= max_results:
            debug_item["skipped"] = True
            debug_item["skipReason"] = "max_results_reached"
            if execution_debug is not None:
                execution_debug.append(debug_item)
            continue
        try:
            batch = await client.search(
                keyword=keyword,
                count=10,
            )
            tagged_batch = []
            for item in batch:
                tagged_item = dict(item) if isinstance(item, dict) else {"value": item}
                tagged_item["_searchKeyword"] = keyword
                tagged_item["_searchKeywordPhase"] = phase
                tagged_item["_searchKeywordIndex"] = index
                tagged_batch.append(tagged_item)
            results.extend(tagged_batch)
            debug_item["rawResultCount"] = len(tagged_batch)
            debug_item["cumulativeRawAfter"] = len(results)
        except ZhihuClientError as exc:
            message = str(exc)
            errors.append({"keyword": keyword, "error": message})
            debug_item["error"] = message
            print(f"[search] {message}")
        except Exception as exc:
            message = f"Unexpected Zhihu search error for keyword={keyword!r}: {exc}"
            errors.append({"keyword": keyword, "error": message})
            debug_item["error"] = message
            print(f"[search] {message}")
        if execution_debug is not None:
            execution_debug.append(debug_item)
    return results


def _build_search_recall_debug(
    *,
    planned_keywords: list[str],
    primary_keywords: list[str],
    execution_debug: list[dict[str, Any]],
    raw_results: list[dict[str, Any]],
    deduped_results: list[dict[str, Any]],
    llm_people_draft: list[dict[str, Any]],
    valid_people: list[dict[str, Any]],
    count: int,
) -> dict[str, Any]:
    actual_keywords = [
        str(item.get("keyword", "")).strip()
        for item in execution_debug
        if item.get("phase") == "primary" and str(item.get("keyword", "")).strip()
    ]
    raw_by_keyword = _count_by_search_keyword(raw_results)
    deduped_by_keyword = _count_by_search_keyword(deduped_results)
    draft_by_keyword = _count_people_by_source_keyword(llm_people_draft, deduped_results)
    valid_by_keyword = _count_people_by_source_keyword(valid_people, deduped_results)
    keyword_stats = []
    for keyword in planned_keywords:
        keyword_stats.append(
            {
                "keyword": keyword,
                "executed": keyword in actual_keywords,
                "rawResultCount": raw_by_keyword.get(keyword, 0),
                "dedupedKeepCount": deduped_by_keyword.get(keyword, 0),
                "llmDraftPeopleCount": draft_by_keyword.get(keyword, 0),
                "validPeopleCount": valid_by_keyword.get(keyword, 0),
            }
        )
    return {
        "plannedSearchKeywords": planned_keywords,
        "primaryPlannedSearchKeywords": primary_keywords,
        "actualExecutedSearchKeywords": actual_keywords,
        "keywordStats": keyword_stats,
        "executionDebug": execution_debug,
        "keywordExecutionStoppedByMaxResults": any(
            item.get("skipReason") == "max_results_reached"
            for item in execution_debug
            if item.get("phase") == "primary"
        ),
        "skippedKeywordsDueToMaxResults": [
            str(item.get("keyword", "")).strip()
            for item in execution_debug
            if item.get("phase") == "primary"
            and item.get("skipReason") == "max_results_reached"
            and str(item.get("keyword", "")).strip()
        ],
        "totalRawBeforeDedup": len(raw_results),
        "totalRawAfterDedup": len(_dedupe_results(raw_results)),
        "finalRawResultsCount": len(deduped_results),
        "requestedCount": count,
        "perKeywordRequestCount": 10,
        "maxKeywordTruncated": len(primary_keywords) < len(planned_keywords),
        "primaryKeywordLimit": len(primary_keywords),
        "plannedKeywordCount": len(planned_keywords),
        "maxRawResultTruncated": len(_dedupe_results(raw_results)) > len(deduped_results),
        "countLimitApplied": len(deduped_results) >= count,
    }


def _count_by_search_keyword(results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in results:
        if not isinstance(item, dict):
            continue
        keyword = str(item.get("_searchKeyword", "")).strip()
        if not keyword:
            keyword = "unknown"
        counts[keyword] = counts.get(keyword, 0) + 1
    return counts


def _count_people_by_source_keyword(
    people: list[dict[str, Any]],
    deduped_results: list[dict[str, Any]],
) -> dict[str, int]:
    keyword_by_url = {
        str(item.get("url", "")).strip(): str(item.get("_searchKeyword", "")).strip()
        for item in deduped_results
        if isinstance(item, dict) and str(item.get("url", "")).strip()
    }
    counts: dict[str, int] = {}
    for person in people:
        if not isinstance(person, dict):
            continue
        source = person.get("source") if isinstance(person.get("source"), dict) else {}
        url = str(source.get("url") or person.get("sourceUrl") or "").strip()
        keyword = keyword_by_url.get(url, "")
        if not keyword:
            continue
        counts[keyword] = counts.get(keyword, 0) + 1
    return counts


def _fallback_keywords_for_query_type(
    query_type: str,
    *,
    existing_keywords: list[str],
) -> list[str]:
    candidates = {
        "family_money": [
            "父母要钱经历",
            "给父母钱经历",
            "家庭经济压力经历",
            "父母再就业经历",
        ],
        "education_gaokao_major": [
            "高考志愿经历",
            "选专业后悔",
            "理科专业选择经历",
            "大学专业选择",
        ],
        "education_postgrad_switch": [
            "跨专业考研经验",
            "专业不喜欢考研",
            "考研转专业经历",
            "跨考上岸经历",
        ],
        "relationship": [
            "分手经历",
            "关系迷茫经历",
            "亲密关系困扰",
        ],
        "migration_new_zealand": [
            "新西兰生活经历",
            "新西兰 WHV经历",
            "新西兰 打工度假经历",
            "新西兰 留学转工签经历",
            "新西兰 旅居经历",
            "奥克兰 生活经历",
            "基督城 生活经历",
        ],
    }.get(query_type, [])
    existing = {keyword.strip() for keyword in existing_keywords if keyword.strip()}
    return [keyword for keyword in candidates if keyword and keyword not in existing]
