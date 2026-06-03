from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import settings


SUPPORTED_PROVIDERS = {"deepseek", "kimi", "qwen", "openai", "legacy"}


@dataclass(frozen=True)
class LLMTaskRoute:
    task: str
    provider: str
    model_env: str
    model_setting: str
    default_temperature: float
    requires_json: bool = True


@dataclass(frozen=True)
class LLMResolvedConfig:
    task: str
    provider: str
    api_key_env: str
    base_url_env: str
    model_env: str
    api_key: str
    base_url: str
    model: str
    is_fallback: bool = False

    @property
    def missing(self) -> list[str]:
        missing: list[str] = []
        if not self.api_key:
            missing.append(self.api_key_env)
        if not self.base_url:
            missing.append(self.base_url_env)
        if not self.model:
            missing.append(self.model_env)
        return missing

    @property
    def fallback_reason(self) -> str:
        missing = set(self.missing)
        if self.api_key_env in missing:
            return "missing_api_key"
        if self.model_env in missing:
            return "missing_model"
        if self.base_url_env in missing:
            return "missing_base_url"
        return ""

    @property
    def chat_completions_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"


TASK_ROUTES: dict[str, LLMTaskRoute] = {
    "query_understanding": LLMTaskRoute(
        task="query_understanding",
        provider="deepseek",
        model_env="DEEPSEEK_QUERY_MODEL",
        model_setting="deepseek_query_model",
        default_temperature=0.15,
    ),
    "clarification": LLMTaskRoute(
        task="clarification",
        provider="deepseek",
        model_env="DEEPSEEK_QUERY_MODEL",
        model_setting="deepseek_query_model",
        default_temperature=0.15,
    ),
    "loading_steps": LLMTaskRoute(
        task="loading_steps",
        provider="deepseek",
        model_env="DEEPSEEK_QUERY_MODEL",
        model_setting="deepseek_query_model",
        default_temperature=0.2,
    ),
    "search_keywords": LLMTaskRoute(
        task="search_keywords",
        provider="deepseek",
        model_env="DEEPSEEK_QUERY_MODEL",
        model_setting="deepseek_query_model",
        default_temperature=0.3,
    ),
    "experience_extraction": LLMTaskRoute(
        task="experience_extraction",
        provider="kimi",
        model_env="KIMI_EXTRACT_MODEL",
        model_setting="kimi_extract_model",
        default_temperature=0.2,
    ),
    "entry_fields": LLMTaskRoute(
        task="entry_fields",
        provider="kimi",
        model_env="KIMI_EXTRACT_MODEL",
        model_setting="kimi_extract_model",
        default_temperature=0.2,
    ),
    "path_clustering": LLMTaskRoute(
        task="path_clustering",
        provider="deepseek",
        model_env="DEEPSEEK_CLUSTER_MODEL",
        model_setting="deepseek_cluster_model",
        default_temperature=0.2,
    ),
    "path_validation": LLMTaskRoute(
        task="path_validation",
        provider="deepseek",
        model_env="DEEPSEEK_CLUSTER_MODEL",
        model_setting="deepseek_cluster_model",
        default_temperature=0.1,
    ),
    "persona_chat": LLMTaskRoute(
        task="persona_chat",
        provider="kimi",
        model_env="KIMI_CHAT_MODEL",
        model_setting="kimi_chat_model",
        default_temperature=0.5,
    ),
    "eval_judge": LLMTaskRoute(
        task="eval_judge",
        provider="deepseek",
        model_env="DEEPSEEK_JUDGE_MODEL",
        model_setting="deepseek_judge_model",
        default_temperature=0.0,
    ),
}


PROVIDER_ENVS: dict[str, tuple[str, str, str, str]] = {
    "deepseek": (
        "DEEPSEEK_API_KEY",
        "deepseek_api_key",
        "DEEPSEEK_BASE_URL",
        "deepseek_base_url",
    ),
    "kimi": (
        "KIMI_API_KEY",
        "kimi_api_key",
        "KIMI_BASE_URL",
        "kimi_base_url",
    ),
    "qwen": (
        "QWEN_API_KEY",
        "qwen_api_key",
        "QWEN_BASE_URL",
        "qwen_base_url",
    ),
}

TASK_PROVIDER_OVERRIDE_SETTINGS: dict[str, str] = {
    "query_understanding": "llm_task_query_understanding_provider",
    "clarification": "llm_task_query_understanding_provider",
    "loading_steps": "llm_task_query_understanding_provider",
    "search_keywords": "llm_task_query_understanding_provider",
    "experience_extraction": "llm_task_experience_extraction_provider",
    "entry_fields": "llm_task_entry_fields_provider",
    "path_clustering": "llm_task_path_clustering_provider",
    "path_validation": "llm_task_path_clustering_provider",
    "persona_chat": "llm_task_persona_chat_provider",
    "eval_judge": "llm_task_eval_judge_provider",
}

DEEPSEEK_TASK_MODELS: dict[str, tuple[str, str]] = {
    "query_understanding": ("DEEPSEEK_QUERY_MODEL", "deepseek_query_model"),
    "clarification": ("DEEPSEEK_QUERY_MODEL", "deepseek_query_model"),
    "loading_steps": ("DEEPSEEK_QUERY_MODEL", "deepseek_query_model"),
    "search_keywords": ("DEEPSEEK_QUERY_MODEL", "deepseek_query_model"),
    "path_clustering": ("DEEPSEEK_CLUSTER_MODEL", "deepseek_cluster_model"),
    "path_validation": ("DEEPSEEK_CLUSTER_MODEL", "deepseek_cluster_model"),
    "eval_judge": ("DEEPSEEK_JUDGE_MODEL", "deepseek_judge_model"),
}

KIMI_TASK_MODELS: dict[str, tuple[str, str]] = {
    "experience_extraction": ("KIMI_EXTRACT_MODEL", "kimi_extract_model"),
    "entry_fields": ("KIMI_EXTRACT_MODEL", "kimi_extract_model"),
    "persona_chat": ("KIMI_CHAT_MODEL", "kimi_chat_model"),
}

QWEN_TASK_MODELS: dict[str, tuple[str, str]] = {
    "query_understanding": ("QWEN_QUERY_MODEL", "qwen_query_model"),
    "clarification": ("QWEN_QUERY_MODEL", "qwen_query_model"),
    "loading_steps": ("QWEN_QUERY_MODEL", "qwen_query_model"),
    "search_keywords": ("QWEN_QUERY_MODEL", "qwen_query_model"),
    "experience_extraction": ("QWEN_EXTRACT_MODEL", "qwen_extract_model"),
    "entry_fields": ("QWEN_EXTRACT_MODEL", "qwen_extract_model"),
    "path_clustering": ("QWEN_CLUSTER_MODEL", "qwen_cluster_model"),
    "path_validation": ("QWEN_CLUSTER_MODEL", "qwen_cluster_model"),
    "persona_chat": ("QWEN_CHAT_MODEL", "qwen_chat_model"),
    "eval_judge": ("QWEN_JUDGE_MODEL", "qwen_judge_model"),
}


def get_task_route(task: str) -> LLMTaskRoute:
    clean_task = _normalize_task(task)
    route = TASK_ROUTES.get(clean_task)
    if route:
        return route

    default_provider = (settings.llm_default_provider or "deepseek").strip().lower()
    if default_provider == "kimi":
        return LLMTaskRoute(
            task=clean_task,
            provider="kimi",
            model_env="KIMI_CHAT_MODEL",
            model_setting="kimi_chat_model",
            default_temperature=0.2,
        )
    if default_provider == "qwen":
        return LLMTaskRoute(
            task=clean_task,
            provider="qwen",
            model_env="QWEN_QUERY_MODEL",
            model_setting="qwen_query_model",
            default_temperature=0.2,
        )
    return LLMTaskRoute(
        task=clean_task,
        provider="deepseek",
        model_env="DEEPSEEK_QUERY_MODEL",
        model_setting="deepseek_query_model",
        default_temperature=0.2,
    )


def resolve_primary_config(task: str) -> LLMResolvedConfig:
    route = get_task_route(task)
    provider = _resolved_provider(route)
    return resolve_provider_config(route.task, provider, is_fallback=False)


def resolve_provider_config(
    task: str,
    provider: str,
    *,
    is_fallback: bool = False,
) -> LLMResolvedConfig:
    route = get_task_route(task)
    clean_provider = provider.strip().lower()
    if clean_provider == "openai":
        return _openai_config(route.task, is_fallback=is_fallback)
    if clean_provider == "legacy":
        return _legacy_config(route.task, is_fallback=is_fallback)

    if clean_provider not in PROVIDER_ENVS:
        clean_provider = route.provider

    api_key_env, api_key_setting, base_url_env, base_url_setting = PROVIDER_ENVS[clean_provider]
    model_env, model_setting = _model_for_provider_task(clean_provider, route)
    return LLMResolvedConfig(
        task=route.task,
        provider=clean_provider,
        api_key_env=api_key_env,
        base_url_env=base_url_env,
        model_env=model_env,
        api_key=getattr(settings, api_key_setting),
        base_url=getattr(settings, base_url_setting),
        model=getattr(settings, model_setting),
        is_fallback=is_fallback,
    )


def resolve_fallback_config(task: str) -> LLMResolvedConfig:
    if settings.has_openai_fallback_config:
        return _openai_config(task, is_fallback=True)
    return _legacy_config(task, is_fallback=True)


def iter_task_routes() -> list[LLMTaskRoute]:
    return list(TASK_ROUTES.values())


def task_requires_json(task: str) -> bool:
    route = get_task_route(task)
    return route.requires_json


def default_temperature_for_task(task: str) -> float:
    return get_task_route(task).default_temperature


def router_dry_run() -> dict[str, Any]:
    fallback_config = resolve_fallback_config("fallback")
    return {
        "fallbackEnabled": settings.llm_enable_fallback,
        "timeout": {
            "requestVariable": "LLM_REQUEST_TIMEOUT_SECONDS",
            "legacyCompatibleVariable": "LLM_TIMEOUT_SECONDS",
            "seconds": settings.llm_request_timeout_seconds,
            "defaultSeconds": 20.0,
        },
        "tasks": [
            _task_snapshot(route)
            for route in iter_task_routes()
        ],
        "providerChecks": {
            "qwen": [
                _provider_task_snapshot(route, "qwen")
                for route in iter_task_routes()
            ],
        },
        "fallback": _config_snapshot(fallback_config),
    }


def _task_snapshot(route: LLMTaskRoute) -> dict[str, Any]:
    config = resolve_primary_config(route.task)
    override_provider = _provider_override(route.task)
    return {
        "task": route.task,
        "defaultProvider": route.provider,
        "overrideProvider": override_provider,
        "provider": config.provider,
        "resolvedProvider": config.provider,
        "modelEnv": config.model_env,
        "model": config.model or "",
        "modelConfigured": bool(config.model),
        "missing": config.missing,
        "defaultTemperature": route.default_temperature,
        "requiresJson": route.requires_json,
    }


def _config_snapshot(config: LLMResolvedConfig) -> dict[str, Any]:
    return {
        "provider": config.provider,
        "modelEnv": config.model_env,
        "model": config.model or "",
        "modelConfigured": bool(config.model),
        "missing": config.missing,
    }


def _provider_task_snapshot(route: LLMTaskRoute, provider: str) -> dict[str, Any]:
    config = resolve_provider_config(route.task, provider, is_fallback=False)
    return {
        "task": route.task,
        "provider": config.provider,
        "modelEnv": config.model_env,
        "model": config.model or "",
        "modelConfigured": bool(config.model),
        "missing": config.missing,
    }


def _normalize_task(task: str) -> str:
    return str(task or "").strip()


def _resolved_provider(route: LLMTaskRoute) -> str:
    return _provider_override(route.task) or route.provider


def _provider_override(task: str) -> str:
    setting_name = TASK_PROVIDER_OVERRIDE_SETTINGS.get(task, "")
    if not setting_name:
        return ""
    provider = str(getattr(settings, setting_name, "") or "").strip().lower()
    return provider if provider in SUPPORTED_PROVIDERS else ""


def _model_for_provider_task(provider: str, route: LLMTaskRoute) -> tuple[str, str]:
    if provider == route.provider:
        return route.model_env, route.model_setting
    if provider == "deepseek":
        return DEEPSEEK_TASK_MODELS.get(
            route.task,
            ("DEEPSEEK_QUERY_MODEL", "deepseek_query_model"),
        )
    if provider == "kimi":
        return KIMI_TASK_MODELS.get(
            route.task,
            ("KIMI_CHAT_MODEL", "kimi_chat_model"),
        )
    if provider == "qwen":
        return QWEN_TASK_MODELS.get(
            route.task,
            ("QWEN_QUERY_MODEL", "qwen_query_model"),
        )
    return route.model_env, route.model_setting


def _openai_config(task: str, *, is_fallback: bool) -> LLMResolvedConfig:
    return LLMResolvedConfig(
        task=task,
        provider="openai",
        api_key_env="OPENAI_API_KEY",
        base_url_env="OPENAI_BASE_URL",
        model_env="OPENAI_FALLBACK_MODEL",
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.openai_fallback_model,
        is_fallback=is_fallback,
    )


def _legacy_config(task: str, *, is_fallback: bool) -> LLMResolvedConfig:
    return LLMResolvedConfig(
        task=task,
        provider="legacy",
        api_key_env="LLM_API_KEY",
        base_url_env="LLM_BASE_URL",
        model_env="LLM_MODEL",
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model=settings.llm_model,
        is_fallback=is_fallback,
    )
