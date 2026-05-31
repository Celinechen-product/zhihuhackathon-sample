from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    zhihu_app_key: str = os.getenv("ZHIHU_APP_KEY", "").strip()
    zhihu_app_secret: str = os.getenv("ZHIHU_APP_SECRET", "").strip()
    zhihu_base_url: str = os.getenv("ZHIHU_BASE_URL", "https://openapi.zhihu.com/").strip()
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "").strip()
    llm_api_key: str = os.getenv("LLM_API_KEY", "").strip()
    llm_base_url: str = os.getenv("LLM_BASE_URL", "").strip()
    llm_model: str = os.getenv("LLM_MODEL", "").strip()
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "20"))
    llm_max_concurrency: int = int(os.getenv("LLM_MAX_CONCURRENCY", "3"))
    use_mock_fallback: bool = _env_bool("USE_MOCK_FALLBACK", True)
    zhihu_search_url: str = os.getenv(
        "ZHIHU_SEARCH_URL",
        "https://developer.zhihu.com/api/v1/content/zhihu_search",
    ).strip()
    zhihu_access_secret: str = os.getenv("ZHIHU_ACCESS_SECRET", "").strip()
    zhihu_search_query_param: str = os.getenv("ZHIHU_SEARCH_QUERY_PARAM", "Query").strip()
    zhihu_search_count_param: str = os.getenv("ZHIHU_SEARCH_COUNT_PARAM", "Count").strip()
    zhihu_timeout_seconds: float = float(os.getenv("ZHIHU_TIMEOUT_SECONDS", "10"))

    @property
    def has_zhihu_credentials(self) -> bool:
        return bool(self.zhihu_app_key and self.zhihu_app_secret)

    @property
    def has_zhihu_access_secret(self) -> bool:
        return bool(self.zhihu_access_secret)

    @property
    def has_zhihu_search_url(self) -> bool:
        return bool(self.zhihu_search_url)

    @property
    def has_llm_config(self) -> bool:
        return bool(self.llm_api_key and self.llm_base_url and self.llm_model)


settings = Settings()
