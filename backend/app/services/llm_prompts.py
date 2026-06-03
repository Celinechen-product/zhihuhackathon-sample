from __future__ import annotations

from functools import lru_cache
from pathlib import Path


PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


@lru_cache(maxsize=None)
def load_prompt(task: str) -> str:
    """Load a task-level prompt template by task name."""
    safe_task = task.strip().replace("/", "_")
    if not safe_task:
        raise ValueError("prompt task name must not be empty")
    path = PROMPTS_DIR / f"{safe_task}.md"
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise ValueError(f"prompt template not found for task: {safe_task}") from exc


QUERY_UNDERSTANDING_PROMPT = load_prompt("query_understanding")
EXTRACT_PERSON_EXPERIENCE_PROMPT = load_prompt("experience_extraction")
ENTRY_FIELDS_PROMPT = load_prompt("entry_fields")
CLUSTER_PATHS_PROMPT = load_prompt("path_clustering")
PATH_VALIDATION_PROMPT = load_prompt("path_validation")
PERSONA_QA_PROMPT = load_prompt("persona_qa")
EVAL_JUDGE_PROMPT = load_prompt("eval_judge")
