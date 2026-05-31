from __future__ import annotations

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from app.schemas import ClarifyRequest, ClarifyResponse, SearchResponse
from app.services.clarification import build_clarification
from app.services.search_pipeline import search_life_samples


app = FastAPI(title="人生样本库 MVP Backend", version="0.1.0")

# Development-only CORS list for local frontend/backend integration.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/query/clarify", response_model=ClarifyResponse)
async def clarify_query(payload: ClarifyRequest) -> ClarifyResponse:
    return build_clarification(payload.query, payload.clarification)


@app.get("/api/search", response_model=SearchResponse)
async def search(
    query: str = Query(..., min_length=1),
    clarification: str = Query("", description="Optional one-time clarification answer."),
    count: int = Query(20, ge=1, le=50),
) -> dict:
    return await search_life_samples(
        query=query,
        clarification=clarification,
        count=count,
    )
