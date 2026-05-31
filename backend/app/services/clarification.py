from __future__ import annotations

from app.schemas import ClarifyResponse
from app.services.loading_steps import build_loading_steps
from app.services.query_context import build_query_context
from app.services.query_understanding import (
    CLARIFICATION_OPTIONS,
    CLARIFICATION_QUESTION,
    build_search_keywords,
    need_clarification,
    understand_query,
)


def build_clarification(query: str, clarification: str | None = None) -> ClarifyResponse:
    clean_clarification = (clarification or "").strip()
    loading_steps = _build_initial_loading_steps(query, clean_clarification)
    if clean_clarification or not need_clarification(query):
        return ClarifyResponse(
            needClarification=False,
            clarificationQuestion="",
            clarificationOptions=[],
            loadingSteps=loading_steps,
        )

    return ClarifyResponse(
        needClarification=True,
        clarificationQuestion=CLARIFICATION_QUESTION,
        clarificationOptions=CLARIFICATION_OPTIONS,
            loadingSteps=loading_steps,
        )


def _build_initial_loading_steps(query: str, clarification: str) -> list[dict[str, str]]:
    understanding = understand_query(query, clarification)
    query_context = build_query_context(query, clarification, understanding=understanding)
    keywords = build_search_keywords(
        query,
        clarification,
        understanding,
        query_context=query_context,
    )
    loading_context = {
        **query_context,
        "topic_tags": understanding.get("topic_tags") or [],
        "focusTags": understanding.get("focus_tags") or [],
    }
    return build_loading_steps(
        query=query,
        clarification=clarification,
        query_context=loading_context,
        search_keywords=keywords,
    )
