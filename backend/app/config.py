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


def _env_str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    zhihu_app_key: str = _env_str("ZHIHU_APP_KEY")
    zhihu_app_secret: str = _env_str("ZHIHU_APP_SECRET")
    zhihu_base_url: str = _env_str("ZHIHU_BASE_URL", "https://openapi.zhihu.com/")
    openai_api_key: str = _env_str("OPENAI_API_KEY")
    openai_base_url: str = _env_str("OPENAI_BASE_URL")
    openai_fallback_model: str = _env_str("OPENAI_FALLBACK_MODEL")
    deepseek_api_key: str = _env_str("DEEPSEEK_API_KEY")
    deepseek_base_url: str = _env_str("DEEPSEEK_BASE_URL")
    deepseek_query_model: str = _env_str("DEEPSEEK_QUERY_MODEL")
    deepseek_cluster_model: str = _env_str("DEEPSEEK_CLUSTER_MODEL")
    deepseek_judge_model: str = _env_str("DEEPSEEK_JUDGE_MODEL")
    kimi_api_key: str = _env_str("KIMI_API_KEY")
    kimi_base_url: str = _env_str("KIMI_BASE_URL")
    kimi_extract_model: str = _env_str("KIMI_EXTRACT_MODEL")
    kimi_chat_model: str = _env_str("KIMI_CHAT_MODEL")
    qwen_api_key: str = _env_str("QWEN_API_KEY")
    qwen_base_url: str = _env_str("QWEN_BASE_URL")
    qwen_query_model: str = _env_str("QWEN_QUERY_MODEL")
    qwen_extract_model: str = _env_str("QWEN_EXTRACT_MODEL")
    qwen_chat_model: str = _env_str("QWEN_CHAT_MODEL")
    qwen_cluster_model: str = _env_str("QWEN_CLUSTER_MODEL")
    qwen_judge_model: str = _env_str("QWEN_JUDGE_MODEL")
    llm_api_key: str = _env_str("LLM_API_KEY")
    llm_base_url: str = _env_str("LLM_BASE_URL")
    llm_model: str = _env_str("LLM_MODEL")
    llm_default_provider: str = _env_str("LLM_DEFAULT_PROVIDER", "deepseek")
    llm_enable_fallback: bool = _env_bool("LLM_ENABLE_FALLBACK", True)
    llm_timeout_seconds: float = _env_float("LLM_TIMEOUT_SECONDS", 20.0)
    llm_request_timeout_seconds: float = _env_float(
        "LLM_REQUEST_TIMEOUT_SECONDS",
        llm_timeout_seconds,
    )
    llm_task_experience_extraction_provider: str = _env_str(
        "LLM_TASK_EXPERIENCE_EXTRACTION_PROVIDER"
    )
    llm_task_entry_fields_provider: str = _env_str("LLM_TASK_ENTRY_FIELDS_PROVIDER")
    llm_task_persona_chat_provider: str = _env_str("LLM_TASK_PERSONA_CHAT_PROVIDER")
    llm_task_path_clustering_provider: str = _env_str(
        "LLM_TASK_PATH_CLUSTERING_PROVIDER"
    )
    llm_task_query_understanding_provider: str = _env_str(
        "LLM_TASK_QUERY_UNDERSTANDING_PROVIDER"
    )
    llm_task_eval_judge_provider: str = _env_str("LLM_TASK_EVAL_JUDGE_PROVIDER")
    llm_max_concurrency: int = _env_int("LLM_MAX_CONCURRENCY", 3)
    use_mock_fallback: bool = _env_bool("USE_MOCK_FALLBACK", True)
    zhihu_search_url: str = _env_str(
        "ZHIHU_SEARCH_URL",
        "https://developer.zhihu.com/api/v1/content/zhihu_search",
    )
    zhihu_access_secret: str = _env_str("ZHIHU_ACCESS_SECRET")
    zhihu_search_query_param: str = _env_str("ZHIHU_SEARCH_QUERY_PARAM", "Query")
    zhihu_search_count_param: str = _env_str("ZHIHU_SEARCH_COUNT_PARAM", "Count")
    zhihu_timeout_seconds: float = _env_float("ZHIHU_TIMEOUT_SECONDS", 10.0)

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
        return any(
            (
                self.has_deepseek_config,
                self.has_kimi_config,
                self.has_qwen_config,
                self.has_openai_fallback_config,
                self.has_legacy_llm_config,
            )
        )

    @property
    def has_deepseek_config(self) -> bool:
        return bool(
            self.deepseek_api_key
            and self.deepseek_base_url
            and (
                self.deepseek_query_model
                or self.deepseek_cluster_model
                or self.deepseek_judge_model
            )
        )

    @property
    def has_kimi_config(self) -> bool:
        return bool(
            self.kimi_api_key
            and self.kimi_base_url
            and (self.kimi_extract_model or self.kimi_chat_model)
        )

    @property
    def has_qwen_config(self) -> bool:
        return bool(
            self.qwen_api_key
            and self.qwen_base_url
            and (
                self.qwen_query_model
                or self.qwen_extract_model
                or self.qwen_chat_model
                or self.qwen_cluster_model
                or self.qwen_judge_model
            )
        )

    @property
    def has_openai_fallback_config(self) -> bool:
        return bool(
            self.openai_api_key
            and self.openai_base_url
            and self.openai_fallback_model
        )

    @property
    def has_legacy_llm_config(self) -> bool:
        return bool(self.llm_api_key and self.llm_base_url and self.llm_model)


settings = Settings()
