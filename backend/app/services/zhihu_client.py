from __future__ import annotations

import time
from typing import Any

import httpx

from app.config import settings


class ZhihuClientError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        error_type: str = "zhihu_error",
        status_code: int = 0,
    ) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.status_code = status_code


class ZhihuClient:
    def __init__(
        self,
        search_url: str | None = None,
        access_secret: str | None = None,
        query_param: str | None = None,
        count_param: str | None = None,
    ) -> None:
        self.search_url = search_url if search_url is not None else settings.zhihu_search_url
        self.access_secret = (
            access_secret if access_secret is not None else settings.zhihu_access_secret
        )
        self.query_param = query_param or settings.zhihu_search_query_param or "Query"
        self.count_param = count_param or settings.zhihu_search_count_param or "Count"

    async def search(self, keyword: str, count: int = 10) -> list[dict[str, Any]]:
        clean_keyword = (keyword or "").strip()
        if not clean_keyword:
            return []
        if not self.access_secret:
            raise ZhihuClientError(
                "Zhihu access secret is not configured",
                error_type="env_missing",
            )
        if not self.search_url:
            raise ZhihuClientError(
                "Zhihu search URL is not configured",
                error_type="env_missing",
            )

        safe_count = max(1, min(int(count), 10))
        params = {
            self.query_param: clean_keyword,
            self.count_param: safe_count,
        }
        headers = {
            "Authorization": f"Bearer {self.access_secret}",
            "X-Request-Timestamp": str(int(time.time())),
            "Content-Type": "application/json",
        }

        print(f"[zhihu.search] keyword={clean_keyword!r}")

        async with httpx.AsyncClient(timeout=settings.zhihu_timeout_seconds) as client:
            try:
                response = await client.get(
                    self.search_url,
                    params=params,
                    headers=headers,
                )
            except httpx.TimeoutException as exc:
                raise ZhihuClientError(
                    f"Zhihu search request timed out: keyword={clean_keyword!r}",
                    error_type="timeout",
                ) from exc
            except httpx.HTTPError as exc:
                raise ZhihuClientError(
                    f"Zhihu search request failed: keyword={clean_keyword!r}, error={type(exc).__name__}",
                    error_type="network_error",
                ) from exc

        print(f"[zhihu.search] status={response.status_code}")

        if response.status_code != 200:
            raise ZhihuClientError(
                "Zhihu search HTTP failed: "
                f"status={response.status_code}, body={_safe_excerpt(response.text)}",
                error_type=_http_error_type(response.status_code),
                status_code=response.status_code,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ZhihuClientError(
                "Zhihu search returned non-JSON response: "
                f"status={response.status_code}, body={_safe_excerpt(response.text)}",
                error_type="non_json_response",
                status_code=response.status_code,
            ) from exc

        code = payload.get("Code")
        if code != 0:
            message = payload.get("Message", "")
            reason = _zhihu_error_reason(code)
            suffix = f", reason={reason}" if reason else ""
            raise ZhihuClientError(
                f"Zhihu search API failed: code={code}, message={_safe_excerpt(message)}{suffix}",
                error_type="api_error",
                status_code=response.status_code,
            )

        results = normalize_zhihu_search_response(payload)
        print(f"[zhihu.search] result_count={len(results)}")
        return results[:safe_count]


def normalize_zhihu_search_response(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    items = payload.get("Data", {}).get("Items", [])
    if not isinstance(items, list):
        return []

    return [_normalize_search_item(item) for item in items if isinstance(item, dict)]


def _normalize_search_item(item: dict[str, Any]) -> dict[str, Any]:
    content_id = _text(item.get("ContentID"))
    content_type = _text(item.get("ContentType"))
    return {
        "id": content_id,
        "title": _text(item.get("Title")),
        "url": _text(item.get("Url")),
        "type": content_type,
        "excerpt": _text(item.get("ContentText")),
        "author": {
            "id": "",
            "name": _text(item.get("AuthorName")),
            "avatar": _text(item.get("AuthorAvatar")),
            "url": "",
        },
        "stats": {
            "commentCount": _int(item.get("CommentCount")),
            "voteUpCount": _int(item.get("VoteUpCount")),
            "rankingScore": _number(item.get("RankingScore")),
        },
        "meta": {
            "contentId": content_id,
            "contentType": content_type,
            "editTime": item.get("EditTime"),
            "authorityLevel": _text(item.get("AuthorityLevel")),
            "authorBadge": _text(item.get("AuthorBadge")),
            "authorBadgeText": _text(item.get("AuthorBadgeText")),
        },
        "raw": item,
    }


def _zhihu_error_reason(code: Any) -> str:
    return {
        10001: "参数错误",
        20001: "鉴权失败",
        30001: "频率限制",
        90001: "内部错误",
    }.get(code, "")


def _http_error_type(status_code: int) -> str:
    if status_code in {401, 403}:
        return "auth_error"
    if status_code == 404:
        return "not_found"
    if status_code == 429:
        return "rate_limited"
    if 500 <= status_code <= 599:
        return "upstream_error"
    return "http_error"


def _safe_excerpt(value: Any, limit: int = 180) -> str:
    text = str(value or "").replace("\n", "\\n")
    return text if len(text) <= limit else f"{text[:limit]}..."


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _number(value: Any) -> int | float:
    if value is None:
        return 0
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0
    return int(number) if number.is_integer() else number
