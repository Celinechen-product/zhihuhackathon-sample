from __future__ import annotations

import time
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
    sync_path_counts_with_people,
)
from app.services.zhihu_client import ZhihuClient, ZhihuClientError


async def run_search_pipeline(
    *,
    query: str,
    count: int = 20,
    clarification: str | None = None,
    llm_path_cluster_debug: bool = False,
) -> dict[str, Any]:
    total_start = time.perf_counter()
    safe_count = max(1, min(int(count), 50))
    clean_query = (query or "").strip()
    clean_clarification = (clarification or "").strip()
    performance_debug: dict[str, Any] = {
        "query": clean_query,
        "requestedCount": count,
        "safeCount": safe_count,
        "llmPathClusterDebugEnabled": llm_path_cluster_debug,
        "stages": [],
        "llmExtractionRuns": [],
    }
    query_context_start = time.perf_counter()
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
    _record_perf_stage(
        performance_debug,
        "query_context_and_understanding",
        query_context_start,
        queryType=query_context["query_type"],
        effectiveQuery=query_context["effective_query"],
    )
    search_keywords_start = time.perf_counter()
    keywords = build_search_keywords(
        clean_query,
        clean_clarification,
        understanding,
        query_context=query_context,
    )
    understanding["search_keywords"] = keywords
    _record_perf_stage(
        performance_debug,
        "search_keywords_generation",
        search_keywords_start,
        keywordCount=len(keywords),
        keywords=keywords,
    )

    raw_results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    search_execution_debug: list[dict[str, Any]] = []

    should_try_zhihu = settings.has_zhihu_access_secret and settings.has_zhihu_search_url

    planned_search_keywords = keywords[:5]
    if should_try_zhihu:
        zhihu_search_start = time.perf_counter()
        raw_results = await _search_zhihu_keywords(
            planned_search_keywords,
            max_results=safe_count,
            errors=errors,
            execution_debug=search_execution_debug,
            phase="primary",
        )
        _record_perf_stage(
            performance_debug,
            "zhihu_search_total",
            zhihu_search_start,
            phase="primary",
            keywordCount=len(planned_search_keywords),
            rawResultsCount=len(raw_results),
        )
    else:
        zhihu_search_start = time.perf_counter()
        if not settings.has_zhihu_access_secret:
            errors.append(
                {"keyword": "", "error": "Zhihu access secret is not configured"}
            )
        if not settings.has_zhihu_search_url:
            errors.append({"keyword": "", "error": "Zhihu search URL is not configured"})
        _record_perf_stage(
            performance_debug,
            "zhihu_search_total",
            zhihu_search_start,
            phase="primary",
            skipped=True,
            rawResultsCount=0,
        )

    raw_dedupe_start = time.perf_counter()
    deduped_results = _dedupe_results(raw_results)[:safe_count]
    _record_perf_stage(
        performance_debug,
        "raw_results_dedupe",
        raw_dedupe_start,
        rawResultsCount=len(raw_results),
        dedupedResultsCount=len(deduped_results),
    )
    candidate_filter_start = time.perf_counter()
    experience_candidates = filter_experience_candidates(
        raw_results=deduped_results,
        query=query_context["effective_query"],
        understanding=understanding,
    )
    _record_perf_stage(
        performance_debug,
        "experience_candidate_filter",
        candidate_filter_start,
        candidateCount=len(experience_candidates),
    )
    llm_input_results = (
        _attach_raw_results_for_llm(experience_candidates, deduped_results)
        if experience_candidates
        else deduped_results[:5]
    )
    llm_extraction_timings: list[dict[str, Any]] = []
    llm_extraction_start = time.perf_counter()
    llm_people_draft, llm_errors = await extract_people_with_llm(
        query=clean_query,
        clarification=clean_clarification,
        raw_results=llm_input_results,
        limit=8,
        query_context=query_context,
        timing_debug=llm_extraction_timings,
    )
    llm_extraction_elapsed = _record_perf_stage(
        performance_debug,
        "llm_extraction_total",
        llm_extraction_start,
        phase="primary",
        inputCount=len(llm_input_results),
        draftPeopleCount=len(llm_people_draft),
        errorCount=len(llm_errors),
    )
    _append_llm_extraction_run(
        performance_debug,
        phase="primary",
        elapsed_ms=llm_extraction_elapsed,
        input_count=len(llm_input_results),
        draft_people_count=len(llm_people_draft),
        error_count=len(llm_errors),
        item_timings=llm_extraction_timings,
    )
    rule_extraction_start = time.perf_counter()
    people_draft = extract_people_draft(
        candidates=experience_candidates,
        query=query_context["effective_query"],
        understanding=understanding,
    )
    _record_perf_stage(
        performance_debug,
        "rule_experience_extraction",
        rule_extraction_start,
        phase="primary",
        peopleDraftCount=len(people_draft),
    )
    rule_path_assignment_start = time.perf_counter()
    paths_draft, people_draft_with_path = cluster_people_drafts(
        people_draft=people_draft,
        query=clean_query,
        understanding=understanding,
    )
    _record_perf_stage(
        performance_debug,
        "rule_based_path_assignment",
        rule_path_assignment_start,
        phase="primary",
        pathsDraftCount=len(paths_draft),
        peopleDraftWithPathCount=len(people_draft_with_path),
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
    formal_filter_start = time.perf_counter()
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
    _record_perf_stage(
        performance_debug,
        "formal_valid_people_filter",
        formal_filter_start,
        phase="primary",
        llmDraftPeopleCount=len(llm_people_draft),
        validPeopleCount=len(llm_people),
        pathCount=len(llm_paths),
        pathAssignmentDebugCount=len(llm_path_assignment_debug),
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
            fallback_search_start = time.perf_counter()
            fallback_raw_results = await _search_zhihu_keywords(
                fallback_keywords,
                max_results=12,
                errors=errors,
                execution_debug=search_execution_debug,
                phase="fallback",
            )
            _record_perf_stage(
                performance_debug,
                "zhihu_search_total",
                fallback_search_start,
                phase="fallback",
                keywordCount=len(fallback_keywords),
                rawResultsCount=len(fallback_raw_results),
            )
            fallback_raw_results_count = len(fallback_raw_results)
            if fallback_raw_results:
                raw_results.extend(fallback_raw_results)
                fallback_dedupe_start = time.perf_counter()
                deduped_results = _dedupe_results(raw_results)[
                    : max(safe_count, min(50, safe_count + fallback_raw_results_count))
                ]
                _record_perf_stage(
                    performance_debug,
                    "raw_results_dedupe",
                    fallback_dedupe_start,
                    phase="fallback",
                    rawResultsCount=len(raw_results),
                    dedupedResultsCount=len(deduped_results),
                )
                fallback_candidate_filter_start = time.perf_counter()
                experience_candidates = filter_experience_candidates(
                    raw_results=deduped_results,
                    query=query_context["effective_query"],
                    understanding=understanding,
                )
                _record_perf_stage(
                    performance_debug,
                    "experience_candidate_filter",
                    fallback_candidate_filter_start,
                    phase="fallback",
                    candidateCount=len(experience_candidates),
                )
                llm_input_results = (
                    _attach_raw_results_for_llm(experience_candidates, deduped_results)
                    if experience_candidates
                    else deduped_results[:8]
                )
                fallback_llm_extraction_timings: list[dict[str, Any]] = []
                fallback_llm_extraction_start = time.perf_counter()
                llm_people_draft, fallback_llm_errors = await extract_people_with_llm(
                    query=clean_query,
                    clarification=clean_clarification,
                    raw_results=llm_input_results,
                    limit=8,
                    query_context=query_context,
                    timing_debug=fallback_llm_extraction_timings,
                )
                fallback_llm_extraction_elapsed = _record_perf_stage(
                    performance_debug,
                    "llm_extraction_total",
                    fallback_llm_extraction_start,
                    phase="fallback",
                    inputCount=len(llm_input_results),
                    draftPeopleCount=len(llm_people_draft),
                    errorCount=len(fallback_llm_errors),
                )
                _append_llm_extraction_run(
                    performance_debug,
                    phase="fallback",
                    elapsed_ms=fallback_llm_extraction_elapsed,
                    input_count=len(llm_input_results),
                    draft_people_count=len(llm_people_draft),
                    error_count=len(fallback_llm_errors),
                    item_timings=fallback_llm_extraction_timings,
                )
                llm_errors.extend(fallback_llm_errors)
                fallback_rule_extraction_start = time.perf_counter()
                people_draft = extract_people_draft(
                    candidates=experience_candidates,
                    query=query_context["effective_query"],
                    understanding=understanding,
                )
                _record_perf_stage(
                    performance_debug,
                    "rule_experience_extraction",
                    fallback_rule_extraction_start,
                    phase="fallback",
                    peopleDraftCount=len(people_draft),
                )
                fallback_rule_path_assignment_start = time.perf_counter()
                paths_draft, people_draft_with_path = cluster_people_drafts(
                    people_draft=people_draft,
                    query=clean_query,
                    understanding=understanding,
                )
                _record_perf_stage(
                    performance_debug,
                    "rule_based_path_assignment",
                    fallback_rule_path_assignment_start,
                    phase="fallback",
                    pathsDraftCount=len(paths_draft),
                    peopleDraftWithPathCount=len(people_draft_with_path),
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
                fallback_formal_filter_start = time.perf_counter()
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
                _record_perf_stage(
                    performance_debug,
                    "formal_valid_people_filter",
                    fallback_formal_filter_start,
                    phase="fallback",
                    llmDraftPeopleCount=len(llm_people_draft),
                    validPeopleCount=len(llm_people),
                    pathCount=len(llm_paths),
                    pathAssignmentDebugCount=len(llm_path_assignment_debug),
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
    paths = sync_path_counts_with_people(paths, people)

    llm_cluster_start = time.perf_counter()
    llm_cluster_debug = await cluster_paths_with_llm_debug(
        query=clean_query,
        clarification=clean_clarification,
        query_context=query_context,
        people=people,
        rule_fallback_used=rule_people_fallback_used,
        enabled=llm_path_cluster_debug,
    )
    _record_perf_stage(
        performance_debug,
        "llm_path_clustering_debug",
        llm_cluster_start,
        enabled=llm_path_cluster_debug,
        peopleCount=len(people),
        validationMessageCount=len(llm_cluster_debug.get("llmClusterValidationDebug") or []),
    )

    response_formatting_start = time.perf_counter()
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
    _record_perf_stage(
        performance_debug,
        "response_formatting",
        response_formatting_start,
        pathCount=len(paths),
        peopleCount=len(people),
        rawResultsCount=len(deduped_results),
    )
    total_elapsed_ms = _elapsed_ms(total_start)
    performance_debug["totalElapsedMs"] = total_elapsed_ms
    print(
        "[search.performance] "
        f"stage=total elapsed_ms={total_elapsed_ms} "
        f"raw_results={len(deduped_results)} people={len(people)} paths={len(paths)} "
        f"llm_path_cluster_debug_enabled={llm_path_cluster_debug}"
    )
    response["debug"]["performanceDebug"] = performance_debug
    return response


async def search_life_samples(
    *,
    query: str,
    clarification: str = "",
    count: int = 20,
    llm_path_cluster_debug: bool = False,
) -> dict[str, Any]:
    return await run_search_pipeline(
        query=query,
        clarification=clarification,
        count=count,
        llm_path_cluster_debug=llm_path_cluster_debug,
    )


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)


def _record_perf_stage(
    performance_debug: dict[str, Any],
    stage: str,
    start: float,
    **fields: Any,
) -> float:
    elapsed_ms = _elapsed_ms(start)
    entry = {"stage": stage, "elapsedMs": elapsed_ms, **fields}
    performance_debug.setdefault("stages", []).append(entry)
    _log_perf(stage, elapsed_ms, **fields)
    return elapsed_ms


def _append_llm_extraction_run(
    performance_debug: dict[str, Any],
    *,
    phase: str,
    elapsed_ms: float,
    input_count: int,
    draft_people_count: int,
    error_count: int,
    item_timings: list[dict[str, Any]],
) -> None:
    performance_debug.setdefault("llmExtractionRuns", []).append(
        {
            "phase": phase,
            "elapsedMs": elapsed_ms,
            "inputCount": input_count,
            "draftPeopleCount": draft_people_count,
            "errorCount": error_count,
            "itemTimings": sorted(
                item_timings,
                key=lambda item: int(item.get("index") or 0),
            ),
        }
    )


def _log_perf(stage: str, elapsed_ms: float, **fields: Any) -> None:
    parts = [f"stage={stage}", f"elapsed_ms={elapsed_ms}"]
    for key, value in fields.items():
        parts.append(f"{key}={_format_perf_value(value)}")
    print("[search.performance] " + " ".join(parts))


def _format_perf_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        preview = ",".join(str(item) for item in value[:5])
        suffix = ",..." if len(value) > 5 else ""
        return f"[{preview}{suffix}]"
    if isinstance(value, dict):
        return f"dict_keys({','.join(str(key) for key in list(value)[:5])})"
    text = str(value).replace("\n", " ").strip()
    if len(text) > 80:
        text = text[:77] + "..."
    return repr(text)


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
        keyword_start = time.perf_counter()
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
            "elapsedMs": 0.0,
        }
        if len(results) >= max_results:
            debug_item["skipped"] = True
            debug_item["skipReason"] = "max_results_reached"
            debug_item["elapsedMs"] = _elapsed_ms(keyword_start)
            _log_perf(
                "zhihu_keyword_search",
                debug_item["elapsedMs"],
                phase=phase,
                keyword=keyword,
                skipped=True,
                rawResultCount=0,
            )
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
        debug_item["elapsedMs"] = _elapsed_ms(keyword_start)
        _log_perf(
            "zhihu_keyword_search",
            debug_item["elapsedMs"],
            phase=phase,
            keyword=keyword,
            skipped=debug_item["skipped"],
            rawResultCount=debug_item["rawResultCount"],
            error=bool(debug_item["error"]),
        )
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
