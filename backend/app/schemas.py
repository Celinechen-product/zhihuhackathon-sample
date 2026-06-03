from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ClarifyRequest(BaseModel):
    query: str = ""
    clarification: str = ""


class LoadingStep(BaseModel):
    label: str
    value: str


class ClarifyResponse(BaseModel):
    needClarification: bool
    clarificationQuestion: str
    clarificationOptions: list[str]
    loadingSteps: list[LoadingStep] = Field(default_factory=list)


class AnalysisStep(BaseModel):
    title: str
    text: str


class Analysis(BaseModel):
    question_type: str = "other"
    core_question: str
    actors: list[str] = Field(default_factory=list)
    user_state: str = ""
    goal: str = ""
    constraints: list[str] = Field(default_factory=list)
    conflict: str = ""
    steps: list[AnalysisStep]
    focusTags: list[str] = Field(default_factory=list)


class PathItem(BaseModel):
    id: str
    name: str
    desc: str
    count: int
    supporting_person_ids: list[str] = Field(default_factory=list)
    query_relevance_check: str = ""


class Source(BaseModel):
    title: str
    url: str
    content_type: str = ""
    type: str = ""
    author_name: str = ""
    author_avatar: str = ""
    authorName: str = ""
    updatedAt: str = ""
    excerpt: str = ""


class PersonaChatSource(BaseModel):
    title: str = ""
    url: str = ""
    excerpt: str = ""


class PersonaChatPerson(BaseModel):
    name: str = ""
    situation: str = ""
    actionSummary: str = ""
    realDetails: list[str] = Field(default_factory=list)
    key_fragments: list[str] = Field(default_factory=list)
    currentStatus: str = ""
    entrySituation: str = ""
    entryStatus: str = ""
    source: PersonaChatSource = Field(default_factory=PersonaChatSource)


class PersonaChatRequest(BaseModel):
    personId: str = ""
    question: str = ""
    query: str = ""
    queryId: str = ""
    person: PersonaChatPerson = Field(default_factory=PersonaChatPerson)


class PersonaChatResponse(BaseModel):
    answer: str
    basedOnPublicContent: bool = True
    sourceUrl: str = ""
    insufficientContext: bool = False


class Person(BaseModel):
    id: str
    sample_type: str = ""
    sampleType: str = ""
    contentType: str = ""
    name: str
    avatar: str = ""
    pathId: str
    role: str = ""
    badge: str = ""
    situation: str = ""
    actionSummary: str = ""
    realDetails: list[str] = Field(default_factory=list)
    key_fragments: list[str] = Field(default_factory=list)
    currentStatus: str = ""
    entrySituation: str = ""
    entryStatus: str = ""
    internal: dict[str, Any] = Field(default_factory=dict)
    oneLine: str = ""
    who: str = ""
    matchReasons: list[str] = Field(default_factory=list)
    timeline: list[Any] = Field(default_factory=list)
    keyExperience: str = ""
    sourceExcerpt: str = ""
    sourceTitle: str = ""
    sourceUrl: str = ""
    source: Source


class DebugInfo(BaseModel):
    clarification: str
    combinedQuery: str
    resultSource: str = "fallback"
    frontendPathsCount: int = 0
    frontendPeopleCount: int = 0
    understanding: dict[str, Any]
    keywords: list[str]
    queryContext: dict[str, Any] = Field(default_factory=dict)
    effectiveQuery: str = ""
    searchKeywords: list[str] = Field(default_factory=list)
    searchFallbackUsed: bool = False
    fallbackKeywords: list[str] = Field(default_factory=list)
    fallbackRawResultsCount: int = 0
    finalDropSummary: list[dict[str, Any]] = Field(default_factory=list)
    rawResultsCount: int
    rawResults: list[dict[str, Any]]
    experienceCandidatesCount: int = 0
    experienceCandidates: list[dict[str, Any]] = Field(default_factory=list)
    peopleDraftCount: int = 0
    peopleDraft: list[dict[str, Any]] = Field(default_factory=list)
    pathsDraftCount: int = 0
    pathsDraft: list[dict[str, Any]] = Field(default_factory=list)
    peopleDraftWithPathCount: int = 0
    peopleDraftWithPath: list[dict[str, Any]] = Field(default_factory=list)
    llmEnabled: bool = False
    llmPeopleDraftCount: int = 0
    llmPeopleDraft: list[dict[str, Any]] = Field(default_factory=list)
    llmErrors: list[Any] = Field(default_factory=list)
    llmDebug: list[dict[str, Any]] = Field(default_factory=list)
    llmPeopleUsed: bool = False
    llmPeopleUsedCount: int = 0
    rulePeopleFallbackUsed: bool = False
    llmPathAssignmentDebug: list[dict[str, Any]] = Field(default_factory=list)
    pathAssignmentDebug: list[dict[str, Any]] = Field(default_factory=list)
    llmPeopleFilterDebug: list[dict[str, Any]] = Field(default_factory=list)
    pathRelevanceDebug: list[dict[str, Any]] = Field(default_factory=list)
    droppedPaths: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    performanceDebug: dict[str, Any] = Field(default_factory=dict)
    zhihuEnvDebug: dict[str, Any] = Field(default_factory=dict)
    zhihuSearchDebug: list[dict[str, Any]] = Field(default_factory=list)
    pathGenerationMode: str = ""
    llmClusterDebugEnabled: bool = False
    llmClusterInputPeopleCount: int = 0
    llmClusterPathsRaw: dict[str, Any] = Field(default_factory=dict)
    llmClusterValidationDebug: list[dict[str, Any]] = Field(default_factory=list)
    droppedClusterPaths: list[dict[str, Any]] = Field(default_factory=list)
    ruleFallbackUsed: bool = False


class SearchResponse(BaseModel):
    queryId: str
    query: str
    loadingSteps: list[LoadingStep] = Field(default_factory=list)
    analysis: Analysis
    paths: list[PathItem]
    people: list[Person]
    debug: DebugInfo
