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
OUTPUT_PATH = BACKEND_DIR / "tmp" / "search_funnel_debug_latest.json"
VENV_PYTHON = BACKEND_DIR / ".venv" / "bin" / "python"

if VENV_PYTHON.exists() and Path(sys.executable).resolve() != VENV_PYTHON.resolve():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.search_pipeline import search_life_samples  # noqa: E402
from app.services.response_formatter import (  # noqa: E402
    _classify_llm_path,
    build_frontend_from_llm_people,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run backend search pipeline and print the recall-to-path funnel.",
    )
    parser.add_argument("query", nargs="?", help="User query to debug.")
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
    parser.add_argument(
        "--regression",
        action="store_true",
        help="Run local career_restart funnel regression fixtures without API calls.",
    )
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    if args.regression:
        run_regression_cases()
        return 0
    if not args.query:
        raise SystemExit("query is required unless --regression is used")
    pipeline_stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(pipeline_stdout):
            response = await search_life_samples(
                query=args.query,
                clarification=args.clarification,
                count=args.count,
            )
        error = ""
    except Exception as exc:
        response = {}
        error = f"{type(exc).__name__}: {exc}"

    debug = _dict(response.get("debug") if isinstance(response, dict) else {})
    sections = build_sections(
        query=args.query,
        clarification=args.clarification,
        response=response,
        debug=debug,
        error=error,
    )
    save_debug_json(
        {
            "query": args.query,
            "clarification": args.clarification,
            "error": error,
            "sections": sections,
            "response": response,
            "pipelineDebug": debug,
            "pipelineStdout": pipeline_stdout.getvalue(),
        }
    )
    print_sections(sections)
    print()
    print("H. 保存完整 JSON")
    print(f"raw debug JSON 保存路径: {OUTPUT_PATH}")
    if error:
        print(f"pipelineError: {error}")
    return 0


def build_sections(
    *,
    query: str,
    clarification: str,
    response: dict[str, Any],
    debug: dict[str, Any],
    error: str,
) -> dict[str, Any]:
    cluster_debug = extract_cluster_debug(debug)
    return {
        "queryUnderstanding": query_understanding_section(
            query=query,
            clarification=clarification,
            debug=debug,
        ),
        "searchRecall": search_recall_section(debug),
        "llmDraftPeople": llm_draft_people_section(debug),
        "formalValidPeople": formal_valid_people_section(response, debug),
        "filteredPeople": filtered_people_section(debug, response),
        "officialPaths": official_paths_section(response),
        "llmClusterDebug": llm_cluster_section(cluster_debug),
        "error": error,
    }


def query_understanding_section(
    *,
    query: str,
    clarification: str,
    debug: dict[str, Any],
) -> dict[str, Any]:
    query_context = _dict(debug.get("queryContext"))
    understanding = _dict(debug.get("understanding"))
    return {
        "query": query,
        "clarification": clarification or debug.get("clarification", ""),
        "queryType": query_context.get("query_type") or understanding.get("query_type"),
        "queryContext": query_context,
        "must_include_topics": _list(query_context.get("must_include_topics")),
        "must_exclude_topics": _list(query_context.get("must_exclude_topics")),
        "searchKeywords": _list(debug.get("searchKeywords") or debug.get("keywords")),
    }


def search_recall_section(debug: dict[str, Any]) -> dict[str, Any]:
    raw_results = _list(debug.get("rawResults"))
    recall_debug = _dict(debug.get("searchRecallDebug"))
    return {
        "rawResultsCount": debug.get("rawResultsCount", len(raw_results)),
        "plannedSearchKeywords": _list(recall_debug.get("plannedSearchKeywords")),
        "actualExecutedSearchKeywords": _list(recall_debug.get("actualExecutedSearchKeywords")),
        "keywordStats": _list(recall_debug.get("keywordStats")),
        "executionDebug": _list(recall_debug.get("executionDebug")),
        "keywordExecutionStoppedByMaxResults": bool(
            recall_debug.get("keywordExecutionStoppedByMaxResults")
        ),
        "skippedKeywordsDueToMaxResults": _list(
            recall_debug.get("skippedKeywordsDueToMaxResults")
        ),
        "totalRawBeforeDedup": recall_debug.get("totalRawBeforeDedup", len(raw_results)),
        "totalRawAfterDedup": recall_debug.get("totalRawAfterDedup", len(raw_results)),
        "finalRawResultsCount": recall_debug.get("finalRawResultsCount", debug.get("rawResultsCount", len(raw_results))),
        "requestedCount": recall_debug.get("requestedCount", 0),
        "perKeywordRequestCount": recall_debug.get("perKeywordRequestCount", 0),
        "primaryKeywordLimit": recall_debug.get("primaryKeywordLimit", 0),
        "plannedKeywordCount": recall_debug.get("plannedKeywordCount", 0),
        "maxKeywordTruncated": bool(recall_debug.get("maxKeywordTruncated")),
        "maxRawResultTruncated": bool(recall_debug.get("maxRawResultTruncated")),
        "countLimitApplied": bool(recall_debug.get("countLimitApplied")),
        "rawResults": [
            {
                "index": index,
                "title": _text(item.get("title")),
                "authorName": _author_name(item),
                "hasSourceUrl": bool(_source_url(item)),
                "sourceUrl": _source_url(item),
                "rawTextPreview": _limit(
                    _text(item.get("excerpt") or item.get("content") or item.get("text")),
                    80,
                ),
            }
            for index, item in enumerate(raw_results)
            if isinstance(item, dict)
        ],
    }


def llm_draft_people_section(debug: dict[str, Any]) -> dict[str, Any]:
    drafts = [item for item in _list(debug.get("llmPeopleDraft")) if isinstance(item, dict)]
    return {
        "llmDraftPeopleCount": debug.get("llmPeopleDraftCount", len(drafts)),
        "people": [draft_summary(draft) for draft in drafts],
    }


def formal_valid_people_section(
    response: dict[str, Any],
    debug: dict[str, Any],
) -> dict[str, Any]:
    people = [item for item in _list(response.get("people")) if isinstance(item, dict)]
    filter_by_id = filter_debug_by_person_id(debug)
    assignment_by_id = assignment_debug_by_person_id(debug)
    path_name_by_id = {
        _text(path.get("id")): _text(path.get("name"))
        for path in _list(response.get("paths"))
        if isinstance(path, dict) and _text(path.get("id"))
    }
    return {
        "validPeopleCount": len(people),
        "people": [
            valid_person_summary(
                person,
                filter_by_id.get(_text(person.get("id")), {}),
                assignment_by_id.get(_text(person.get("id")), {}),
                path_name_by_id,
            )
            for person in people
        ],
    }


def filtered_people_section(
    debug: dict[str, Any],
    response: dict[str, Any],
) -> dict[str, Any]:
    drafts = [item for item in _list(debug.get("llmPeopleDraft")) if isinstance(item, dict)]
    filter_debug = [
        item for item in _list(debug.get("llmPeopleFilterDebug")) if isinstance(item, dict)
    ]
    valid_ids = {
        _text(person.get("id"))
        for person in _list(response.get("people"))
        if isinstance(person, dict) and _text(person.get("id"))
    }
    filter_by_id = filter_debug_by_person_id(debug)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for draft in drafts:
        person_id = _text(draft.get("id"))
        debug_item = filter_by_id.get(person_id, {})
        kept = bool(debug_item.get("kept")) or person_id in valid_ids
        if kept:
            continue
        rows.append(filtered_candidate_summary(draft, debug_item))
        seen.add(person_id)

    for item in filter_debug:
        person_id = _text(item.get("personId"))
        if item.get("kept") or person_id in seen or person_id in valid_ids:
            continue
        rows.append(filtered_candidate_summary({}, item))

    return {
        "filteredPeopleCount": len(rows),
        "people": rows,
    }


def official_paths_section(response: dict[str, Any]) -> dict[str, Any]:
    paths = [item for item in _list(response.get("paths")) if isinstance(item, dict)]
    people = [item for item in _list(response.get("people")) if isinstance(item, dict)]
    people_by_path: dict[str, list[dict[str, Any]]] = {}
    for person in people:
        people_by_path.setdefault(_text(person.get("pathId")), []).append(person)
    return {
        "officialPathsCount": len(paths),
        "pathNames": [_text(path.get("name")) for path in paths],
        "paths": [
            {
                "pathId": _text(path.get("id")),
                "name": _text(path.get("name")),
                "peopleCount": len(people_by_path.get(_text(path.get("id")), [])),
                "people": [
                    {
                        "personId": _text(person.get("id")),
                        "name": _text(person.get("name")),
                    }
                    for person in people_by_path.get(_text(path.get("id")), [])
                ],
            }
            for path in paths
        ],
    }


def llm_cluster_section(cluster_debug: dict[str, Any]) -> dict[str, Any]:
    raw = _dict(cluster_debug.get("llmClusterPathsRaw"))
    validation = [
        item
        for item in _list(cluster_debug.get("llmClusterValidationDebug"))
        if isinstance(item, dict)
    ]
    return {
        "llmClusterInputPeopleCount": cluster_debug.get("llmClusterInputPeopleCount", 0),
        "pathGenerationMode": cluster_debug.get("pathGenerationMode", ""),
        "cluster_axis": raw.get("cluster_axis", ""),
        "llmClusterPathsRawPathNames": path_names(raw),
        "validationWarningsErrors": [
            item for item in validation if item.get("level") in {"warning", "error"}
        ],
        "droppedClusterPaths": _list(cluster_debug.get("droppedClusterPaths")),
        "unassignedPersonIds": _list(raw.get("unassignedPersonIds")),
        "singlePersonFallbackPersonIds": _list(raw.get("singlePersonFallbackPersonIds")),
    }


def draft_summary(draft: dict[str, Any]) -> dict[str, Any]:
    source = _dict(draft.get("source"))
    internal = _dict(draft.get("internal"))
    return {
        "name": _text(draft.get("name")),
        "source.title": _text(source.get("title")),
        "isPersonalExperience": draft.get("isPersonalExperience"),
        "experience_owner": _text(draft.get("experience_owner")),
        "can_be_person_sample": draft.get("can_be_person_sample"),
        "sampleType": _text(draft.get("sampleType") or draft.get("sample_type")),
        "confidence": _text(internal.get("confidence") or draft.get("confidence")),
        "filter_reason": _text(draft.get("filter_reason") or draft.get("filterReason")),
        "situation": _text(draft.get("situation")),
        "actionSummary": _text(draft.get("actionSummary") or draft.get("action_summary")),
        "currentStatus": _text(draft.get("currentStatus") or draft.get("current_status")),
        "entrySituation": _text(draft.get("entrySituation") or draft.get("entry_situation")),
        "entryStatus": _text(draft.get("entryStatus") or draft.get("entry_status")),
    }


def valid_person_summary(
    person: dict[str, Any],
    debug_item: dict[str, Any],
    assignment_item: dict[str, Any],
    path_name_by_id: dict[str, str],
) -> dict[str, Any]:
    source = _dict(person.get("source"))
    assigned_path_id = _text(assignment_item.get("assignedPathId") or person.get("pathId"))
    return {
        "personId": _text(person.get("id")),
        "name": _text(person.get("name")),
        "source.title": _text(source.get("title") or person.get("sourceTitle")),
        "source.url": _text(source.get("url") or person.get("sourceUrl")),
        "sampleType": _text(person.get("sampleType") or person.get("sample_type")),
        "situation": _text(person.get("situation")),
        "actionSummary": _text(person.get("actionSummary")),
        "currentStatus": _text(person.get("currentStatus")),
        "entrySituation": _text(person.get("entrySituation")),
        "entryStatus": _text(person.get("entryStatus")),
        "pathId": _text(person.get("pathId")),
        "assignedPathId": assigned_path_id,
        "assignedPathName": path_name_by_id.get(assigned_path_id, ""),
        "assignmentReason": _text(assignment_item.get("reason")),
        "matchedAssignmentKeywords": _list(
            assignment_item.get("matchedKeywords") or assignment_item.get("matchedEvidence")
        ),
        "rescue_reason": _text(debug_item.get("rescue_reason")),
        "final_filter_reason": _text(debug_item.get("final_filter_reason")),
        "original_filter_reason": _text(debug_item.get("original_filter_reason")),
        "matched_structured_fields": _list(debug_item.get("matched_structured_fields")),
        "evidence_score": debug_item.get("evidence_score", 0),
        "can_rescue_by_structured_fields": bool(debug_item.get("can_rescue_by_structured_fields")),
        "matched_query_premise_positive": _list(debug_item.get("matched_query_premise_positive")),
        "matched_query_premise_negative": _list(debug_item.get("matched_query_premise_negative")),
        "query_premise_verdict": _text(debug_item.get("query_premise_verdict")),
        "matched_query_premise_positive_by_field": _dict(
            debug_item.get("matched_query_premise_positive_by_field")
        ),
        "matched_query_premise_negative_by_field": _dict(
            debug_item.get("matched_query_premise_negative_by_field")
        ),
        "matched_family_money_interaction_keywords": _list(
            debug_item.get("matched_family_money_interaction_keywords")
        ),
        "matched_family_money_transfer_keywords": _list(
            debug_item.get("matched_family_money_transfer_keywords")
        ),
        "migration_target_location_positive": _list(
            debug_item.get("migration_target_location_positive")
        ),
        "migration_target_location_negative": _list(
            debug_item.get("migration_target_location_negative")
        ),
        "migration_target_location_verdict": _text(
            debug_item.get("migration_target_location_verdict")
        ),
        "matched_migration_author_journey_keywords": _list(
            debug_item.get("matched_migration_author_journey_keywords")
        ),
        "migration_author_journey_keywords": _list(
            debug_item.get("migration_author_journey_keywords")
            or debug_item.get("matched_migration_author_journey_keywords")
        ),
        "migration_author_journey_hard_negative_keywords": _list(
            debug_item.get("migration_author_journey_hard_negative_keywords")
        ),
        "migration_rescue_blocked_reason": _text(
            debug_item.get("migration_rescue_blocked_reason")
        ),
    }


def filtered_candidate_summary(
    draft: dict[str, Any],
    debug_item: dict[str, Any],
) -> dict[str, Any]:
    source = _dict(draft.get("source"))
    draft_fields = draft_summary(draft) if draft else {}
    return {
        "name": draft_fields.get("name") or _text(debug_item.get("name")),
        "source.title": draft_fields.get("source.title") or _text(source.get("title")),
        "filter_reason": draft_fields.get("filter_reason") or _text(debug_item.get("filter_reason")),
        "internal debug reason": _text(debug_item.get("dropReason")),
        "rescue_reason": _text(debug_item.get("rescue_reason")),
        "final_filter_reason": _text(debug_item.get("final_filter_reason")),
        "original_filter_reason": _text(debug_item.get("original_filter_reason")),
        "matched_structured_fields": _list(debug_item.get("matched_structured_fields")),
        "evidence_score": debug_item.get("evidence_score", 0),
        "can_rescue_by_structured_fields": bool(debug_item.get("can_rescue_by_structured_fields")),
        "matched_query_premise_positive": _list(debug_item.get("matched_query_premise_positive")),
        "matched_query_premise_negative": _list(debug_item.get("matched_query_premise_negative")),
        "query_premise_verdict": _text(debug_item.get("query_premise_verdict")),
        "matched_query_premise_positive_by_field": _dict(
            debug_item.get("matched_query_premise_positive_by_field")
        ),
        "matched_query_premise_negative_by_field": _dict(
            debug_item.get("matched_query_premise_negative_by_field")
        ),
        "matched_family_money_interaction_keywords": _list(
            debug_item.get("matched_family_money_interaction_keywords")
        ),
        "matched_family_money_transfer_keywords": _list(
            debug_item.get("matched_family_money_transfer_keywords")
        ),
        "migration_target_location_positive": _list(
            debug_item.get("migration_target_location_positive")
        ),
        "migration_target_location_negative": _list(
            debug_item.get("migration_target_location_negative")
        ),
        "migration_target_location_verdict": _text(
            debug_item.get("migration_target_location_verdict")
        ),
        "matched_migration_author_journey_keywords": _list(
            debug_item.get("matched_migration_author_journey_keywords")
        ),
        "migration_author_journey_keywords": _list(
            debug_item.get("migration_author_journey_keywords")
            or debug_item.get("matched_migration_author_journey_keywords")
        ),
        "migration_author_journey_hard_negative_keywords": _list(
            debug_item.get("migration_author_journey_hard_negative_keywords")
        ),
        "migration_rescue_blocked_reason": _text(
            debug_item.get("migration_rescue_blocked_reason")
        ),
        "situation": draft_fields.get("situation", ""),
        "actionSummary": draft_fields.get("actionSummary", ""),
        "currentStatus": draft_fields.get("currentStatus", ""),
        "entrySituation": draft_fields.get("entrySituation", ""),
        "entryStatus": draft_fields.get("entryStatus", ""),
    }


def filter_debug_by_person_id(debug: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _text(item.get("personId")): item
        for item in _list(debug.get("llmPeopleFilterDebug"))
        if isinstance(item, dict) and _text(item.get("personId"))
    }


def assignment_debug_by_person_id(debug: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _text(item.get("personId")): item
        for item in _list(debug.get("llmPathAssignmentDebug") or debug.get("pathAssignmentDebug"))
        if isinstance(item, dict) and _text(item.get("personId"))
    }


def extract_cluster_debug(debug: dict[str, Any]) -> dict[str, Any]:
    understanding = _dict(debug.get("understanding"))
    nested = understanding.get("llmPathClusterDebug")
    if isinstance(nested, dict):
        return nested

    keys = {
        "pathGenerationMode",
        "llmClusterInputPeopleCount",
        "llmClusterPathsRaw",
        "llmClusterValidationDebug",
        "droppedClusterPaths",
        "ruleFallbackUsed",
    }
    return {key: debug.get(key) for key in keys if key in debug}


def save_debug_json(payload: dict[str, Any]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def print_sections(sections: dict[str, Any]) -> None:
    print_section_a(sections["queryUnderstanding"])
    print_section_b(sections["searchRecall"])
    print_section_c(sections["llmDraftPeople"])
    print_section_d(sections["formalValidPeople"])
    print_section_e(sections["filteredPeople"])
    print_section_f(sections["officialPaths"])
    print_section_g(sections["llmClusterDebug"])


def print_section_a(section: dict[str, Any]) -> None:
    print("A. Query understanding")
    print(f"query: {section['query']}")
    print(f"clarification: {section['clarification']}")
    print(f"queryType: {section['queryType']}")
    print(f"queryContext: {_json(section['queryContext'])}")
    print(f"must_include_topics: {_json(section['must_include_topics'])}")
    print(f"must_exclude_topics: {_json(section['must_exclude_topics'])}")
    print(f"searchKeywords: {_json(section['searchKeywords'])}")


def print_section_b(section: dict[str, Any]) -> None:
    print()
    print("B. Search recall")
    print(f"rawResultsCount: {section['rawResultsCount']}")
    print(f"plannedSearchKeywords: {_json(section['plannedSearchKeywords'])}")
    print(f"actualExecutedSearchKeywords: {_json(section['actualExecutedSearchKeywords'])}")
    print(f"totalRawBeforeDedup: {section['totalRawBeforeDedup']}")
    print(f"totalRawAfterDedup: {section['totalRawAfterDedup']}")
    print(f"finalRawResultsCount: {section['finalRawResultsCount']}")
    print(f"requestedCount: {section['requestedCount']}")
    print(f"perKeywordRequestCount: {section['perKeywordRequestCount']}")
    print(f"primaryKeywordLimit: {section['primaryKeywordLimit']}")
    print(f"plannedKeywordCount: {section['plannedKeywordCount']}")
    print(f"maxKeywordTruncated: {section['maxKeywordTruncated']}")
    print(
        "keywordExecutionStoppedByMaxResults: "
        f"{section['keywordExecutionStoppedByMaxResults']}"
    )
    print(
        "skippedKeywordsDueToMaxResults: "
        f"{_json(section['skippedKeywordsDueToMaxResults'])}"
    )
    print(f"maxRawResultTruncated: {section['maxRawResultTruncated']}")
    print(f"countLimitApplied: {section['countLimitApplied']}")
    print("keyword contribution:")
    for item in section["keywordStats"]:
        print(
            f"    keyword={item.get('keyword')} | executed={item.get('executed')} "
            f"| raw={item.get('rawResultCount')} | deduped={item.get('dedupedKeepCount')} "
            f"| llmDraftPeople={item.get('llmDraftPeopleCount')} "
            f"| validPeople={item.get('validPeopleCount')}"
        )
    print("execution detail:")
    for item in section["executionDebug"]:
        print(
            f"    phase={item.get('phase')} keyword={item.get('keyword')} "
            f"| requested={item.get('requestedCount')} | raw={item.get('rawResultCount')} "
            f"| cumulativeBefore={item.get('cumulativeRawBefore')} "
            f"| cumulativeAfter={item.get('cumulativeRawAfter')} "
            f"| error={item.get('error')}"
        )
    for item in section["rawResults"]:
        print(
            f"[{item['index']}] title={item['title']} | authorName={item['authorName']} "
            f"| sourceUrlExists={item['hasSourceUrl']}"
        )
        print(f"    sourceUrl: {item['sourceUrl']}")
        print(f"    rawTextPreview: {item['rawTextPreview']}")


def print_section_c(section: dict[str, Any]) -> None:
    print()
    print("C. LLM draft people")
    print(f"llmDraftPeopleCount: {section['llmDraftPeopleCount']}")
    for index, person in enumerate(section["people"]):
        print(f"[{index}] name={person['name']} | source.title={person['source.title']}")
        print(
            "    "
            f"isPersonalExperience={person['isPersonalExperience']} "
            f"experience_owner={person['experience_owner']} "
            f"can_be_person_sample={person['can_be_person_sample']} "
            f"sampleType={person['sampleType']} confidence={person['confidence']}"
        )
        print(f"    filter_reason: {person['filter_reason']}")
        print(f"    situation: {person['situation']}")
        print(f"    actionSummary: {person['actionSummary']}")
        print(f"    currentStatus: {person['currentStatus']}")
        print(f"    entrySituation: {person['entrySituation']}")
        print(f"    entryStatus: {person['entryStatus']}")


def print_section_d(section: dict[str, Any]) -> None:
    print()
    print("D. Formal valid people")
    print(f"validPeopleCount: {section['validPeopleCount']}")
    for index, person in enumerate(section["people"]):
        print(
            f"[{index}] personId={person['personId']} | name={person['name']} "
            f"| pathId={person['pathId']}"
        )
        print(f"    source.title: {person['source.title']}")
        print(f"    source.url: {person['source.url']}")
        print(f"    sampleType: {person['sampleType']}")
        print(f"    assignedPathId: {person['assignedPathId']}")
        print(f"    assignedPathName: {person['assignedPathName']}")
        print(f"    assignmentReason: {person['assignmentReason']}")
        print(f"    matchedAssignmentKeywords: {_json(person['matchedAssignmentKeywords'])}")
        print(f"    situation: {person['situation']}")
        print(f"    actionSummary: {person['actionSummary']}")
        print(f"    currentStatus: {person['currentStatus']}")
        print(f"    entrySituation: {person['entrySituation']}")
        print(f"    entryStatus: {person['entryStatus']}")
        print(f"    rescue_reason: {person['rescue_reason']}")
        print(f"    final_filter_reason: {person['final_filter_reason']}")
        print(f"    original_filter_reason: {person['original_filter_reason']}")
        print(
            "    matched_structured_fields: "
            f"{_json(person['matched_structured_fields'])} "
            f"| evidence_score={person['evidence_score']} "
            f"| can_rescue={person['can_rescue_by_structured_fields']}"
        )
        print(
            "    query_premise_evidence: "
            f"positive={_json(person['matched_query_premise_positive'])} "
            f"negative={_json(person['matched_query_premise_negative'])} "
            f"verdict={person['query_premise_verdict']}"
        )
        print(
            "    query_premise_by_field: "
            f"positive={_json(person['matched_query_premise_positive_by_field'])} "
            f"negative={_json(person['matched_query_premise_negative_by_field'])}"
        )
        print(
            "    matched_family_money_interaction_keywords: "
            f"{_json(person['matched_family_money_interaction_keywords'])}"
        )
        print(
            "    matched_family_money_transfer_keywords: "
            f"{_json(person['matched_family_money_transfer_keywords'])}"
        )
        print(
            "    migration_target_location: "
            f"positive={_json(person['migration_target_location_positive'])} "
            f"negative={_json(person['migration_target_location_negative'])} "
            f"verdict={person['migration_target_location_verdict']}"
        )
        print(
            "    matched_migration_author_journey_keywords: "
            f"{_json(person['matched_migration_author_journey_keywords'])}"
        )
        print(
            "    migration_author_journey_keywords: "
            f"{_json(person['migration_author_journey_keywords'])}"
        )
        print(
            "    migration_author_journey_hard_negative_keywords: "
            f"{_json(person['migration_author_journey_hard_negative_keywords'])}"
        )
        print(
            "    migration_rescue_blocked_reason: "
            f"{person['migration_rescue_blocked_reason']}"
        )


def print_section_e(section: dict[str, Any]) -> None:
    print()
    print("E. Filtered people")
    print(f"filteredPeopleCount: {section['filteredPeopleCount']}")
    for index, person in enumerate(section["people"]):
        print(f"[{index}] name={person['name']} | source.title={person['source.title']}")
        print(f"    filter_reason: {person['filter_reason']}")
        print(f"    internal debug reason: {person['internal debug reason']}")
        print(f"    situation: {person['situation']}")
        print(f"    actionSummary: {person['actionSummary']}")
        print(f"    currentStatus: {person['currentStatus']}")
        print(f"    entrySituation: {person['entrySituation']}")
        print(f"    entryStatus: {person['entryStatus']}")
        print(f"    rescue_reason: {person['rescue_reason']}")
        print(f"    final_filter_reason: {person['final_filter_reason']}")
        print(f"    original_filter_reason: {person['original_filter_reason']}")
        print(
            "    matched_structured_fields: "
            f"{_json(person['matched_structured_fields'])} "
            f"| evidence_score={person['evidence_score']} "
            f"| can_rescue={person['can_rescue_by_structured_fields']}"
        )
        print(
            "    query_premise_evidence: "
            f"positive={_json(person['matched_query_premise_positive'])} "
            f"negative={_json(person['matched_query_premise_negative'])} "
            f"verdict={person['query_premise_verdict']}"
        )
        print(
            "    query_premise_by_field: "
            f"positive={_json(person['matched_query_premise_positive_by_field'])} "
            f"negative={_json(person['matched_query_premise_negative_by_field'])}"
        )
        print(
            "    matched_family_money_interaction_keywords: "
            f"{_json(person['matched_family_money_interaction_keywords'])}"
        )
        print(
            "    matched_family_money_transfer_keywords: "
            f"{_json(person['matched_family_money_transfer_keywords'])}"
        )
        print(
            "    migration_target_location: "
            f"positive={_json(person['migration_target_location_positive'])} "
            f"negative={_json(person['migration_target_location_negative'])} "
            f"verdict={person['migration_target_location_verdict']}"
        )
        print(
            "    matched_migration_author_journey_keywords: "
            f"{_json(person['matched_migration_author_journey_keywords'])}"
        )
        print(
            "    migration_author_journey_keywords: "
            f"{_json(person['migration_author_journey_keywords'])}"
        )
        print(
            "    migration_author_journey_hard_negative_keywords: "
            f"{_json(person['migration_author_journey_hard_negative_keywords'])}"
        )
        print(
            "    migration_rescue_blocked_reason: "
            f"{person['migration_rescue_blocked_reason']}"
        )


def print_section_f(section: dict[str, Any]) -> None:
    print()
    print("F. Rule-based official paths")
    print(f"officialPathsCount: {section['officialPathsCount']}")
    print(f"path names: {_json(section['pathNames'])}")
    for path in section["paths"]:
        print(
            f"[{path['pathId']}] {path['name']} | peopleCount={path['peopleCount']} "
            f"| people={_json(path['people'])}"
        )


def print_section_g(section: dict[str, Any]) -> None:
    print()
    print("G. LLM cluster debug")
    print(f"llmClusterInputPeopleCount: {section['llmClusterInputPeopleCount']}")
    print(f"pathGenerationMode: {section['pathGenerationMode']}")
    print(f"cluster_axis: {section['cluster_axis']}")
    print(f"llmClusterPathsRaw path names: {_json(section['llmClusterPathsRawPathNames'])}")
    print(f"validation warnings/errors: {_json(section['validationWarningsErrors'])}")
    print(f"droppedClusterPaths: {_json(section['droppedClusterPaths'])}")
    print(f"unassignedPersonIds: {_json(section['unassignedPersonIds'])}")
    print(f"singlePersonFallbackPersonIds: {_json(section['singlePersonFallbackPersonIds'])}")


def run_regression_cases() -> None:
    query = "30岁裸辞后怎么办"
    query_context = {
        "query_type": "career_restart",
        "effective_query": query,
        "original_query": query,
    }
    results: list[dict[str, Any]] = []

    path_id, matched, _, reason = _classify_llm_path(
        "裸辞后有一段时间不上班，后来顺利找到新工作，已入职新岗位。",
        "career_restart",
    )
    _assert_equal(
        path_id,
        "path_return_to_work",
        "strong return-to-work result beats weak status word",
    )
    results.append(
        {
            "case": "return result beats weak status",
            "pathId": path_id,
            "matched": matched,
            "reason": reason,
        }
    )

    _, people, assignment_debug, filter_debug, _, _ = build_frontend_from_llm_people(
        [
            regression_draft(
                person_id="regression_post_premise_return_to_work",
                name="regression_post_premise_return_to_work",
                filter_reason="not yet entered query premise state",
                can_be_person_sample=False,
                situation="30岁裸辞后经历了一段求职期。",
                action_summary="裸辞后重新找工作，连续投简历和面试。",
                current_status="裸辞后顺利找到新工作，已入职新岗位。",
                entry_status="裸辞后顺利找到新工作。",
                real_details=[
                    "裸辞后重新找工作。",
                    "后来顺利找到新工作并入职。",
                ],
                author_evidence=["我裸辞后顺利找到新工作。"],
            )
        ],
        query=query,
        clarification="",
        query_context=query_context,
    )
    _assert_equal(len(people), 1, "strong post-premise status rescues not-yet premise reason")
    _assert_equal(
        people[0].get("pathId"),
        "path_return_to_work",
        "post-premise return-to-work status maps to return_to_work",
    )
    _assert_equal(
        filter_debug[0].get("rescue_reason"),
        "rescued_by_post_premise_evidence",
        "post-premise return rescue reason is visible",
    )
    results.append(
        {
            "case": "post-premise return status rescues premise guard",
            "peopleCount": len(people),
            "pathId": people[0].get("pathId"),
            "assignmentReason": assignment_debug[0].get("reason") if assignment_debug else "",
            "rescueReason": filter_debug[0].get("rescue_reason") if filter_debug else "",
            "premiseVerdict": filter_debug[0].get("query_premise_verdict") if filter_debug else "",
        }
    )

    _, people, assignment_debug, filter_debug, _, _ = build_frontend_from_llm_people(
        [
            regression_draft(
                person_id="regression_post_premise_freelance",
                name="regression_post_premise_freelance",
                filter_reason="not yet entered query premise state",
                can_be_person_sample=False,
                situation="30岁，裸辞两年后仍在重新寻找职业方向。",
                action_summary="裸辞后尝试创业，也投递简历和面试，最终选择离开传统职场继续做自己的项目。",
                current_status="继续创业，暂时不回传统职场。",
                entry_status="裸辞两年后继续创业。",
            )
        ],
        query=query,
        clarification="",
        query_context=query_context,
    )
    _assert_equal(len(people), 1, "post-premise evidence rescues not-yet premise reason")
    _assert_equal(
        people[0].get("pathId"),
        "path_freelance_trials",
        "post-premise entrepreneurship stays in freelance path",
    )
    _assert_equal(
        filter_debug[0].get("rescue_reason"),
        "rescued_by_post_premise_evidence",
        "post-premise rescue reason is visible",
    )
    results.append(
        {
            "case": "post-premise evidence rescues premise guard",
            "peopleCount": len(people),
            "pathId": people[0].get("pathId"),
            "assignmentReason": assignment_debug[0].get("reason") if assignment_debug else "",
            "rescueReason": filter_debug[0].get("rescue_reason") if filter_debug else "",
        }
    )

    _, people, _, filter_debug, _, _ = build_frontend_from_llm_people(
        [
            regression_draft(
                person_id="regression_pre_premise_only",
                name="regression_pre_premise_only",
                filter_reason="not yet entered query premise state",
                can_be_person_sample=False,
                situation="30岁，已经提出离职，但尚未正式离职。",
                action_summary="提出离职但尚未完成交接，仍在继续原工作，离职日期未定。",
                current_status="仍在继续原工作，离职日期未定。",
                entry_status="提出离职但尚未完成交接。",
                real_details=[
                    "我记录的是提出离职后的沟通和交接安排。",
                    "原文明确写到尚未正式离职。",
                ],
                author_evidence=["我提出离职后还在交接中"],
            )
        ],
        query=query,
        clarification="",
        query_context=query_context,
    )
    _assert_equal(len(people), 0, "pre-premise-only candidate stays filtered")
    _assert_equal(
        filter_debug[0].get("final_filter_reason"),
        "not_yet_entered_query_premise_state",
        "pre-premise final filter reason remains premise guard",
    )
    results.append(
        {
            "case": "pre-premise-only remains filtered",
            "peopleCount": len(people),
            "finalFilterReason": filter_debug[0].get("final_filter_reason") if filter_debug else "",
            "premiseVerdict": filter_debug[0].get("query_premise_verdict") if filter_debug else "",
        }
    )

    path_id, matched, _, reason = _classify_llm_path(
        "辞职后一直休息，未积极找工作，考虑转行或找本地企业上班。",
        "career_restart",
    )
    _assert_equal(
        path_id,
        "path_rest_then_restart",
        "rest and direction-shift evidence maps to rest_then_restart",
    )
    results.append(
        {
            "case": "rest then restart assignment",
            "pathId": path_id,
            "matched": matched,
            "reason": reason,
        }
    )

    _, people, assignment_debug, filter_debug, _, _ = build_frontend_from_llm_people(
        [
            regression_draft(
                person_id="regression_post_premise_rest",
                name="regression_post_premise_rest",
                filter_reason="",
                can_be_person_sample=True,
                situation="30岁辞职后进入休整阶段。",
                action_summary="辞职后一直休息，未积极找工作，考虑转行。",
                current_status="辞职后一直休息，仍在重新考虑方向。",
                entry_status="辞职后一直休息。",
                real_details=[
                    "辞职后一直休息。",
                    "没有积极找工作，开始考虑转行。",
                ],
                author_evidence=["我辞职后一直休息，重新考虑方向。"],
            )
        ],
        query=query,
        clarification="",
        query_context=query_context,
    )
    _assert_equal(len(people), 1, "rest-after-resignation candidate stays valid")
    _assert_equal(
        people[0].get("pathId"),
        "path_rest_then_restart",
        "rest-after-resignation maps to rest_then_restart",
    )
    results.append(
        {
            "case": "post-premise rest candidate stays valid",
            "peopleCount": len(people),
            "pathId": people[0].get("pathId"),
            "assignmentReason": assignment_debug[0].get("reason") if assignment_debug else "",
            "premiseVerdict": filter_debug[0].get("query_premise_verdict") if filter_debug else "",
        }
    )

    family_query = "出来工作后，父母要求给他们钱怎么办"
    family_context = {
        "query_type": "family_money",
        "effective_query": family_query,
        "original_query": family_query,
    }
    _, people, assignment_debug, filter_debug, _, _ = build_frontend_from_llm_people(
        [
            regression_draft(
                person_id="regression_family_money_interaction",
                name="regression_family_money_interaction",
                filter_reason="post-check: mentioned_person/case rather than author's own lived experience",
                can_be_person_sample=False,
                situation="刚毕业工作半年，父母50岁，家庭收入紧张。",
                action_summary="春节回家给父母5000元，之后每年给一万到两万；后来减少给款，不主动联系父母，不买东西也不给钱。",
                current_status="几个月来不主动联系父母，不买东西也不给钱。",
                entry_status="已经开始减少给父母的经济支持。",
                real_details=[
                    "刚工作半年春节回家给父母5000元。",
                    "后来不主动联系父母，不买东西也不给钱。",
                ],
                author_evidence=["我给父母钱，也因为钱和父母大吵后减少给款。"],
            )
        ],
        query=family_query,
        clarification="",
        query_context=family_context,
    )
    _assert_equal(len(people), 1, "family money author interaction rescues post-check")
    _assert_equal(
        filter_debug[0].get("rescue_reason"),
        "rescued_by_family_money_author_interaction",
        "family money rescue reason is visible",
    )
    _assert_equal(
        people[0].get("pathId"),
        "path_family_money_boundary",
        "reduced or stopped support maps to money boundary path",
    )
    results.append(
        {
            "case": "family money author interaction rescues post-check",
            "peopleCount": len(people),
            "pathId": people[0].get("pathId"),
            "assignmentReason": assignment_debug[0].get("reason") if assignment_debug else "",
            "rescueReason": filter_debug[0].get("rescue_reason") if filter_debug else "",
            "matchedFamilyMoneyKeywords": filter_debug[0].get("matched_family_money_interaction_keywords")
            if filter_debug
            else [],
        }
    )

    _, people, assignment_debug, filter_debug, _, _ = build_frontend_from_llm_people(
        [
            regression_draft(
                person_id="regression_family_money_transfer",
                name="regression_family_money_transfer",
                filter_reason="advice/commentary without author journey",
                can_be_person_sample=False,
                situation="应届毕业生，刚工作半年，父母无正式工作，家庭经济困难。",
                action_summary="父亲打电话向我要钱，先后转账四千元，因家庭经济压力和个人健康问题感到矛盾和崩溃。",
                current_status="",
                entry_status="",
                real_details=[
                    "父亲打电话向我要钱。",
                    "我先后转账四千元，自己的治疗和生活安排受到影响。",
                ],
                author_evidence=["父亲打电话向我要钱后，我先后转账四千元。"],
                has_outcome=False,
            )
        ],
        query=family_query,
        clarification="",
        query_context=family_context,
    )
    _assert_equal(len(people), 1, "temporary family transfer rescues advice-like filter reason")
    _assert_equal(
        filter_debug[0].get("rescue_reason"),
        "rescued_by_family_money_transfer_interaction",
        "temporary transfer rescue reason is visible",
    )
    _assert_equal(
        people[0].get("pathId"),
        "path_family_support_money",
        "temporary transfer maps to family support path",
    )
    results.append(
        {
            "case": "temporary transfer rescues advice-like filter reason",
            "peopleCount": len(people),
            "pathId": people[0].get("pathId"),
            "assignmentReason": assignment_debug[0].get("reason") if assignment_debug else "",
            "rescueReason": filter_debug[0].get("rescue_reason") if filter_debug else "",
            "matchedTransferKeywords": filter_debug[0].get("matched_family_money_transfer_keywords")
            if filter_debug
            else [],
        }
    )

    _, people, _, filter_debug, _, _ = build_frontend_from_llm_people(
        [
            regression_draft(
                person_id="regression_family_money_formula_advice",
                name="regression_family_money_formula_advice",
                filter_reason="advice/commentary without author journey",
                can_be_person_sample=True,
                situation="讨论工作后给父母钱的比例问题。",
                action_summary="建议按照收入、必要开销和储蓄目标计算给父母钱的金额，没有作者实际转账或被父母要钱的过程。",
                current_status="",
                entry_status="",
                real_details=[
                    "文章主要给出计算公式和理财建议。",
                    "未涉及转账或父母开口要钱的作者经历。",
                ],
                author_evidence=[],
                has_outcome=False,
            )
        ],
        query=family_query,
        clarification="",
        query_context=family_context,
    )
    _assert_equal(len(people), 0, "formula advice without transfer action stays filtered")
    results.append(
        {
            "case": "formula advice without transfer action filtered",
            "peopleCount": len(people),
            "finalFilterReason": filter_debug[0].get("final_filter_reason") if filter_debug else "",
        }
    )

    _, people, _, filter_debug, _, _ = build_frontend_from_llm_people(
        [
            regression_draft(
                person_id="regression_family_money_subject_mismatch",
                name="regression_family_money_subject_mismatch",
                filter_reason="",
                can_be_person_sample=True,
                situation="母亲来北京照顾孩子和家务。",
                action_summary="作者记录母亲帮忙做饭、带孩子和家庭照护压力，未涉及给父母钱或父母要钱。",
                current_status="母亲仍在家里帮忙照护。",
                entry_status="母亲来家里帮忙。",
                real_details=[
                    "母亲来家里做饭和照顾孩子。",
                    "原文主要记录家务和照护安排。",
                ],
                author_evidence=["我记录的是母亲来家里照顾孩子。"],
            )
        ],
        query=family_query,
        clarification="",
        query_context=family_context,
    )
    _assert_equal(len(people), 0, "family care without money interaction stays filtered")
    _assert_equal(
        filter_debug[0].get("final_filter_reason"),
        "family_money_subject_mismatch",
        "family care mismatch gets family_money_subject_mismatch",
    )
    results.append(
        {
            "case": "family care without money interaction filtered",
            "peopleCount": len(people),
            "finalFilterReason": filter_debug[0].get("final_filter_reason") if filter_debug else "",
        }
    )

    migration_query = "不工作之后，我想去新西兰生活"
    migration_context = {
        "query_type": "migration_new_zealand",
        "effective_query": migration_query,
        "original_query": migration_query,
    }
    _, people, _, filter_debug, _, _ = build_frontend_from_llm_people(
        [
            regression_draft(
                person_id="regression_migration_australia_whv",
                name="regression_migration_australia_whv",
                filter_reason="",
                can_be_person_sample=True,
                situation="28岁，准备申请澳洲 WHV。",
                action_summary="作者考虑去澳大利亚打工度假，纠结要不要抓住澳洲 WHV 的尾巴。",
                current_status="仍在准备澳洲 WHV。",
                entry_status="准备澳大利亚打工度假。",
                real_details=[
                    "目标地是澳大利亚。",
                    "内容围绕澳洲 WHV，不涉及新西兰。",
                ],
                author_evidence=["我准备申请澳洲 WHV。"],
                source_title="28岁，要不要抓住澳洲whv的尾巴出去闯一闯？",
            )
        ],
        query=migration_query,
        clarification="",
        query_context=migration_context,
    )
    _assert_equal(len(people), 0, "Australia WHV without New Zealand evidence stays filtered")
    _assert_equal(
        filter_debug[0].get("final_filter_reason"),
        "migration_target_location_mismatch",
        "Australia WHV gets migration target mismatch",
    )
    results.append(
        {
            "case": "Australia WHV target mismatch",
            "peopleCount": len(people),
            "finalFilterReason": filter_debug[0].get("final_filter_reason") if filter_debug else "",
            "migrationVerdict": filter_debug[0].get("migration_target_location_verdict") if filter_debug else "",
        }
    )

    _, people, assignment_debug, filter_debug, _, _ = build_frontend_from_llm_people(
        [
            regression_draft(
                person_id="regression_migration_nz_whv",
                name="regression_migration_nz_whv",
                filter_reason="",
                can_be_person_sample=True,
                situation="30岁前申请新西兰 WHV。",
                action_summary="我申请到新西兰 WHV，去新西兰打工度假，在真实工作和生活成本里试生活。",
                current_status="已经在新西兰打工度假。",
                entry_status="通过新西兰 WHV 去试生活。",
                real_details=[
                    "我申请新西兰 WHV。",
                    "到新西兰后打工度假并记录生活成本。",
                ],
                author_evidence=["我去新西兰 WHV 打工度假。"],
                source_title="新西兰 WHV 打工度假经历",
            )
        ],
        query=migration_query,
        clarification="",
        query_context=migration_context,
    )
    _assert_equal(len(people), 1, "New Zealand WHV stays valid")
    _assert_equal(
        people[0].get("pathId"),
        "path_nz_whv_trial",
        "New Zealand WHV maps to WHV path",
    )
    results.append(
        {
            "case": "New Zealand WHV valid",
            "peopleCount": len(people),
            "pathId": people[0].get("pathId"),
            "assignmentReason": assignment_debug[0].get("reason") if assignment_debug else "",
            "migrationVerdict": filter_debug[0].get("migration_target_location_verdict") if filter_debug else "",
        }
    )

    _, people, assignment_debug, filter_debug, _, _ = build_frontend_from_llm_people(
        [
            regression_draft(
                person_id="regression_migration_nz_city_life",
                name="regression_migration_nz_city_life",
                filter_reason="",
                can_be_person_sample=True,
                situation="不工作后去新西兰生活，先落脚奥克兰和基督城。",
                action_summary="我在奥克兰生活了一段时间，后来搬到基督城，靠存款和阶段性收入维持日常。",
                current_status="仍在基督城生活。",
                entry_status="在奥克兰和基督城试生活。",
                real_details=[
                    "我在奥克兰生活。",
                    "后来搬到基督城继续生活。",
                ],
                author_evidence=["我在奥克兰和基督城生活。"],
                source_title="奥克兰和基督城生活记录",
            )
        ],
        query=migration_query,
        clarification="",
        query_context=migration_context,
    )
    _assert_equal(len(people), 1, "New Zealand city life stays valid")
    _assert_equal(
        people[0].get("pathId"),
        "path_nz_living_migrate",
        "New Zealand city life maps to living path",
    )
    results.append(
        {
            "case": "New Zealand city life valid",
            "peopleCount": len(people),
            "pathId": people[0].get("pathId"),
            "assignmentReason": assignment_debug[0].get("reason") if assignment_debug else "",
            "migrationVerdict": filter_debug[0].get("migration_target_location_verdict") if filter_debug else "",
        }
    )

    _, people, assignment_debug, filter_debug, _, _ = build_frontend_from_llm_people(
        [
            regression_draft(
                person_id="regression_migration_beijing_offer_auckland_life",
                name="regression_migration_beijing_offer_auckland_life",
                filter_reason="",
                can_be_person_sample=True,
                situation="中年北京外企职员，因北京雾霾影响健康，决定移居新西兰奥克兰。",
                action_summary=(
                    "评估多个城市后决定搬新西兰，申请博士项目作为备选，"
                    "最终在北京拿到新西兰工作offer，搬到奥克兰后经历生活适应期。"
                ),
                current_status="已在新西兰奥克兰生活十多年，适应并喜欢当地生活节奏。",
                entry_status="拿到新西兰工作offer后搬到奥克兰生活。",
                real_details=[
                    "决定搬新西兰。",
                    "拿到新西兰工作offer后搬到奥克兰。",
                ],
                author_evidence=[
                    "我最终拿到新西兰工作offer，搬到奥克兰生活。"
                ],
                source_title="移民故事：邀请北京外企职员聊搬到奥克兰",
            )
        ],
        query=migration_query,
        clarification="",
        query_context=migration_context,
    )
    _assert_equal(len(people), 1, "Beijing offer to Auckland journey rescues mentioned_person post-check")
    _assert_equal(
        filter_debug[0].get("rescue_reason"),
        "rescued_by_migration_author_journey",
        "Beijing offer to Auckland rescue reason is visible",
    )
    results.append(
        {
            "case": "Beijing offer to Auckland rescues mentioned_person post-check",
            "peopleCount": len(people),
            "pathId": people[0].get("pathId"),
            "assignmentReason": assignment_debug[0].get("reason") if assignment_debug else "",
            "rescueReason": filter_debug[0].get("rescue_reason") if filter_debug else "",
            "blockedReason": filter_debug[0].get("migration_rescue_blocked_reason") if filter_debug else "",
            "matchedJourneyKeywords": filter_debug[0].get("migration_author_journey_keywords")
            if filter_debug
            else [],
        }
    )

    _, people, assignment_debug, filter_debug, _, _ = build_frontend_from_llm_people(
        [
            regression_draft(
                person_id="regression_migration_author_journey_rescue",
                name="regression_migration_author_journey_rescue",
                filter_reason="experience subject mismatch with query",
                can_be_person_sample=False,
                situation="作者从国内搬到新西兰，落地基督城后重新安排生活。",
                action_summary="我搬到新西兰后在基督城生活，也在奥克兰打工，后来拿到新西兰工作 offer。",
                current_status="仍在新西兰工作和生活。",
                entry_status="落地基督城后开始新西兰生活。",
                real_details=[
                    "我搬到新西兰。",
                    "在基督城生活，也在奥克兰打工。",
                ],
                author_evidence=["我搬到新西兰后在基督城生活并拿到新西兰工作 offer。"],
                source_title="搬到新西兰后的生活和工作记录",
            )
        ],
        query=migration_query,
        clarification="",
        query_context=migration_context,
    )
    _assert_equal(len(people), 1, "New Zealand author journey rescues subject mismatch")
    _assert_equal(
        filter_debug[0].get("rescue_reason"),
        "rescued_by_migration_author_journey",
        "migration author journey rescue reason is visible",
    )
    results.append(
        {
            "case": "New Zealand author journey rescues subject mismatch",
            "peopleCount": len(people),
            "pathId": people[0].get("pathId"),
            "assignmentReason": assignment_debug[0].get("reason") if assignment_debug else "",
            "rescueReason": filter_debug[0].get("rescue_reason") if filter_debug else "",
            "matchedJourneyKeywords": filter_debug[0].get("matched_migration_author_journey_keywords")
            if filter_debug
            else [],
        }
    )

    for case_name, situation, action_summary in (
        (
            "New Zealand short travel filtered",
            "新西兰短期旅行。",
            "我短期去新西兰旅行，整理旅游攻略和行程，没有在新西兰生活或工作。",
        ),
        (
            "New Zealand parent-child placement filtered",
            "带孩子去新西兰插班。",
            "我带孩子去新西兰插班体验，主要记录亲子短期游学安排。",
        ),
        (
            "New Zealand policy guide filtered",
            "新西兰 WHV申请指南。",
            "整理新西兰 WHV申请流程和移民政策攻略，说明材料和步骤，没有作者本人去新西兰生活经历。",
        ),
    ):
        _, people, _, filter_debug, _, _ = build_frontend_from_llm_people(
            [
                regression_draft(
                    person_id=f"regression_migration_{case_name.lower().replace(' ', '_')}",
                    name=f"regression_migration_{case_name.lower().replace(' ', '_')}",
                    filter_reason="",
                    can_be_person_sample=True,
                    situation=situation,
                    action_summary=action_summary,
                    current_status="",
                    entry_status="",
                    real_details=[action_summary],
                    author_evidence=[action_summary],
                    source_title=case_name,
                )
            ],
            query=migration_query,
            clarification="",
            query_context=migration_context,
        )
        _assert_equal(len(people), 0, case_name)
        results.append(
            {
                "case": case_name,
                "peopleCount": len(people),
                "finalFilterReason": filter_debug[0].get("final_filter_reason") if filter_debug else "",
                "migrationVerdict": filter_debug[0].get("migration_target_location_verdict") if filter_debug else "",
            }
        )

    print("backend regression cases passed")
    print(_json(results))


def regression_draft(
    *,
    person_id: str,
    name: str,
    filter_reason: str,
    can_be_person_sample: bool,
    situation: str,
    action_summary: str,
    current_status: str,
    entry_status: str,
    real_details: list[str] | None = None,
    author_evidence: list[str] | None = None,
    has_outcome: bool = True,
    source_title: str | None = None,
) -> dict[str, Any]:
    details = real_details or [
        "我裸辞后的经历持续记录了找工作、创业或休整的过程。",
        "文中有明确阶段变化和当前状态。",
    ]
    return {
        "id": person_id,
        "name": name,
        "sampleType": "full_story",
        "isPersonalExperience": True,
        "is_first_person_experience": True,
        "experience_owner": "author",
        "can_be_person_sample": can_be_person_sample,
        "filter_reason": filter_reason,
        "situation": situation,
        "actionSummary": action_summary,
        "currentStatus": current_status,
        "entrySituation": situation,
        "entryStatus": entry_status,
        "realDetails": details,
        "author_experience_evidence": author_evidence or ["我裸辞后的真实经历"],
        "internal": {"confidence": "high", "hasOutcome": has_outcome},
        "source": {
            "title": source_title or f"{name} 的裸辞后记录",
            "url": f"https://example.com/{person_id}",
            "type": "answer",
            "authorName": name,
            "excerpt": action_summary,
        },
        "rawContentPreview": action_summary,
    }


def _assert_equal(actual: Any, expected: Any, message: str) -> None:
    if actual != expected:
        raise AssertionError(f"{message}: expected {expected!r}, got {actual!r}")


def path_names(raw: dict[str, Any]) -> list[str]:
    paths = raw.get("paths")
    if not isinstance(paths, list):
        return []
    return [
        _text(path.get("name"))
        for path in paths
        if isinstance(path, dict) and _text(path.get("name"))
    ]


def _author_name(item: dict[str, Any]) -> str:
    author = _dict(item.get("author"))
    raw = _dict(item.get("raw"))
    return _text(author.get("name") or item.get("authorName") or raw.get("AuthorName"))


def _source_url(item: dict[str, Any]) -> str:
    raw = _dict(item.get("raw"))
    return _text(item.get("url") or raw.get("Url"))


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").strip()


def _limit(value: str, limit: int) -> str:
    clean = _text(value)
    return clean if len(clean) <= limit else f"{clean[:limit]}..."


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
