from __future__ import annotations

import re
from typing import Any


FIRST_PERSON_MARKERS = (
    "我",
    "本人",
    "自己",
    "亲身",
    "我的",
    "我们",
)

PERSONAL_NARRATIVE_MARKERS = (
    "我是",
    "我也",
    "我在",
    "我从",
    "我当时",
    "我曾",
    "我的",
    "本人",
    "亲身",
    "我靠",
    "我做",
    "我裸辞",
    "我辞职",
    "我离职",
    "我投",
    "我找",
    "我经历",
    "我攒",
    "我尝试",
    "我开始",
)

EXPERIENCE_MARKERS = (
    "经历",
    "裸辞后",
    "辞职后",
    "离职后",
    "待业",
    "找工作",
    "投简历",
    "面试",
    "存款",
    "后来",
    "当时",
    "那段时间",
    "第一个月",
    "几个月后",
    "去年",
    "今年",
)

TIMELINE_MARKERS = (
    "去年",
    "今年",
    "几个月",
    "个月后",
    "后来",
    "当时",
    "第一个月",
    "第5个月",
    "第一个星期",
    "那段时间",
    "一开始",
)

CHOICE_ACTION_MARKERS = (
    "裸辞",
    "离职",
    "辞职",
    "转行",
    "考公",
    "找工作",
    "投简历",
    "面试",
    "做副业",
    "回老家",
    "自由职业",
    "待业",
    "创业",
)

OUTCOME_MARKERS = (
    "找到工作",
    "上岸",
    "失败",
    "放弃",
    "回职场",
    "继续",
    "收入",
    "亏损",
    "改变",
    "回去了",
    "留下来",
    "没上岸",
    "重回职场",
)

ADVICE_MARKERS = (
    "建议你",
    "应该",
    "赶紧",
    "抓紧",
    "可以考虑",
    "最好",
    "不建议",
    "不要",
    "先找",
    "再找份工作",
)

MARKETING_MARKERS = (
    "半年赚",
    "月入",
    "年入",
    "赚了",
    "暴富",
    "副业项目",
    "普通人翻身",
    "躺赚",
    "轻松赚钱",
    "秘诀",
    "稳赚",
    "百万",
    "50万",
    "几十万",
)

OBSERVED_OTHER_MARKERS = (
    "我朋友",
    "我同事",
    "我认识",
    "身边人",
    "身边有",
    "朋友",
    "同事",
)

ADVISOR_MARKERS = (
    "作为",
    "从业",
    "做了",
    "年经验",
    "HR",
    "面试官",
    "职业规划",
    "咨询师",
    "自由职业者",
)

QUESTION_TYPE_TERMS = {
    "career": ("裸辞", "工作", "找工作", "待业", "面试", "投简历", "职业", "转行", "离职"),
    "relationship": ("恋爱", "分手", "结婚", "异地恋", "关系", "伴侣", "相亲"),
    "family": ("父母", "家庭", "家里人", "原生家庭", "亲戚", "养老"),
    "money": ("收入", "现金流", "存款", "买房", "负债", "副业", "赚钱"),
    "education": ("考研", "读研", "留学", "考公", "学历", "学校", "专业"),
    "migration": ("新西兰", "移民", "出国", "旅居", "换城市", "回老家", "生活"),
    "health_life": ("焦虑", "抑郁", "压力", "健康", "睡眠", "倦怠"),
    "self_growth": ("迷茫", "人生", "意义", "失败", "虚无", "选择"),
}

SOURCE_TYPE_MAP = {
    "answer": "Answer",
    "article": "Article",
    "pin": "Pin",
}

SAMPLE_TYPE_PRIORITY = {
    "full_story": 0,
    "partial_experience": 1,
    "opinion_with_experience": 2,
    "opinion_only": 3,
}

CONFIDENCE_PRIORITY = {
    "high": 0,
    "medium": 1,
    "low": 2,
}


def classify_experience_item(
    item: dict[str, Any],
    query: str,
    understanding: dict[str, Any],
) -> dict[str, Any]:
    title = _text(item.get("title"))
    url = _text(item.get("url"))
    source_type = _normalize_content_type(item.get("type") or item.get("meta", {}).get("contentType"))
    excerpt = _text(item.get("excerpt"))
    raw = item.get("raw") if isinstance(item.get("raw"), dict) else {}
    content_text = excerpt or _text(raw.get("ContentText"))
    text = f"{title}\n{content_text}"
    compact_text = _compact(text)
    author = item.get("author") if isinstance(item.get("author"), dict) else {}

    base = {
        "raw_id": _text(item.get("id") or item.get("meta", {}).get("contentId") or raw.get("ContentID")),
        "source": {
            "title": title,
            "url": url,
            "content_type": source_type,
            "excerpt": content_text,
        },
        "author": {
            "name": _text(author.get("name") or raw.get("AuthorName")),
            "avatar": _text(author.get("avatar") or raw.get("AuthorAvatar")),
        },
        "is_relevant": False,
        "has_real_experience": False,
        "sample_type": "opinion_only",
        "actor_type": "unknown",
        "choice_action": "",
        "outcome": "",
        "constraints": [],
        "key_experience": "",
        "suggested_cluster": "",
        "reason": "",
        "confidence": "low",
    }

    if not url:
        base["reason"] = "source.url 为空，无法作为可追溯来源"
        return base

    content_length = _chinese_length(content_text)
    if content_length < 80:
        base["reason"] = "ContentText 过短，无法判断真实经历"
        return base

    marketing_score = _count_markers(compact_text, MARKETING_MARKERS)
    if marketing_score >= 1:
        base["reason"] = "标题或正文含夸张赚钱/营销表达，可信度不足"
        return base

    relevance_score = _relevance_score(compact_text, query, understanding)
    if relevance_score <= 0:
        base["reason"] = "与 query 只有弱关键词重合，缺少相似处境"
        return base

    first_person_score = _count_markers(compact_text, FIRST_PERSON_MARKERS)
    personal_narrative_score = _count_markers(compact_text, PERSONAL_NARRATIVE_MARKERS)
    experience_score = _count_markers(compact_text, EXPERIENCE_MARKERS)
    timeline_score = _count_markers(compact_text, TIMELINE_MARKERS)
    action_score = _count_markers(compact_text, CHOICE_ACTION_MARKERS)
    outcome_score = _count_markers(compact_text, OUTCOME_MARKERS)
    advice_score = _count_markers(compact_text, ADVICE_MARKERS)
    observed_score = _count_markers(compact_text, OBSERVED_OTHER_MARKERS)
    advisor_score = _count_markers(compact_text, ADVISOR_MARKERS)

    actor_type = _infer_actor_type(personal_narrative_score, observed_score, advisor_score)
    if advice_score > 0 and personal_narrative_score == 0 and observed_score == 0 and advisor_score == 0:
        base["reason"] = "主要是建议语气，缺少可判断的亲历或观察经历"
        return base

    has_real_experience = (
        personal_narrative_score > 0 and (experience_score > 0 or action_score > 0 or timeline_score > 0)
    ) or observed_score > 0 or (
        advisor_score > 0 and (experience_score > 0 or advice_score > 0 or action_score > 0)
    )

    if not has_real_experience:
        if advice_score > 0:
            base["reason"] = "主要是建议语气，缺少可判断的亲历或观察经历"
        else:
            base["reason"] = "无法判断作者是否亲历"
        return base

    sample_type = _infer_sample_type(
        content_length=content_length,
        first_person_score=personal_narrative_score,
        observed_score=observed_score,
        timeline_score=timeline_score,
        action_score=action_score,
        outcome_score=outcome_score,
        advice_score=advice_score,
        advisor_score=advisor_score,
    )

    if sample_type == "opinion_only":
        base["reason"] = "纯观点或泛泛建议，不进入真实经历候选"
        return base

    choice_action = _first_marker(compact_text, CHOICE_ACTION_MARKERS)
    outcome = _first_marker(compact_text, OUTCOME_MARKERS)
    constraints = _infer_constraints(compact_text, understanding)
    confidence = _infer_confidence(
        sample_type=sample_type,
        content_length=content_length,
        relevance_score=relevance_score,
        timeline_score=timeline_score,
        action_score=action_score,
        outcome_score=outcome_score,
    )

    base.update(
        {
            "is_relevant": True,
            "has_real_experience": True,
            "sample_type": sample_type,
            "actor_type": actor_type,
            "choice_action": choice_action,
            "outcome": outcome,
            "constraints": constraints,
            "key_experience": _summarize_key_experience(content_text),
            "suggested_cluster": _suggest_cluster(sample_type, choice_action, outcome, constraints),
            "reason": _build_reason(sample_type, confidence, content_length, actor_type),
            "confidence": confidence,
        }
    )
    return base


def filter_experience_candidates(
    raw_results: list[dict[str, Any]],
    query: str,
    understanding: dict[str, Any],
) -> list[dict[str, Any]]:
    pairs = [
        (classify_experience_item(item, query=query, understanding=understanding), item)
        for item in raw_results
    ]
    candidates = [
        pair
        for pair in pairs
        if pair[0]["is_relevant"]
        and pair[0]["has_real_experience"]
        and pair[0]["sample_type"] != "opinion_only"
    ]
    return [candidate for candidate, _ in sorted(candidates, key=_candidate_sort_key)]


def _candidate_sort_key(pair: tuple[dict[str, Any], dict[str, Any]]) -> tuple[Any, ...]:
    item, raw_result = pair
    raw = raw_result.get("raw") if isinstance(raw_result.get("raw"), dict) else {}
    stats = raw_result.get("stats") if isinstance(raw_result.get("stats"), dict) else {}
    comment_count = _number(stats.get("commentCount") or raw.get("CommentCount"))
    vote_count = _number(stats.get("voteUpCount") or raw.get("VoteUpCount"))
    excerpt_len = _chinese_length(item.get("key_experience", ""))
    return (
        SAMPLE_TYPE_PRIORITY.get(item.get("sample_type"), 9),
        CONFIDENCE_PRIORITY.get(item.get("confidence"), 9),
        0 if item.get("author", {}).get("name") else 1,
        -vote_count,
        -comment_count,
        abs(excerpt_len - 180),
    )


def _infer_sample_type(
    *,
    content_length: int,
    first_person_score: int,
    observed_score: int,
    timeline_score: int,
    action_score: int,
    outcome_score: int,
    advice_score: int,
    advisor_score: int,
) -> str:
    if (
        content_length >= 500
        and (first_person_score > 0 or observed_score > 0)
        and timeline_score > 0
        and action_score > 0
        and outcome_score > 0
    ):
        return "full_story"
    if (
        content_length >= 260
        and (first_person_score > 0 or observed_score > 0)
        and action_score > 0
        and (timeline_score > 0 or outcome_score > 0)
    ):
        return "full_story"
    if advisor_score > 0 and advice_score > 0:
        return "opinion_with_experience"
    if (first_person_score > 0 or observed_score > 0) and content_length >= 100:
        return "partial_experience"
    return "opinion_only"


def _infer_actor_type(first_person_score: int, observed_score: int, advisor_score: int) -> str:
    if first_person_score > 0:
        return "self"
    if observed_score > 0:
        return "observed_other"
    if advisor_score > 0:
        return "advisor"
    return "unknown"


def _infer_confidence(
    *,
    sample_type: str,
    content_length: int,
    relevance_score: int,
    timeline_score: int,
    action_score: int,
    outcome_score: int,
) -> str:
    if sample_type == "full_story" and relevance_score >= 2 and action_score > 0 and outcome_score > 0:
        return "high"
    if sample_type == "full_story" and content_length >= 260 and timeline_score > 0:
        return "medium"
    if sample_type == "partial_experience" and relevance_score >= 2 and action_score > 0:
        return "medium"
    if sample_type == "opinion_with_experience":
        return "medium"
    return "low"


def _relevance_score(text: str, query: str, understanding: dict[str, Any]) -> int:
    score = 0
    terms = []
    terms.extend(understanding.get("topic_tags") or [])
    terms.extend(understanding.get("focus_tags") or [])
    question_type = understanding.get("question_type") or "other"
    terms.extend(QUESTION_TYPE_TERMS.get(question_type, ()))
    terms.extend(_query_terms(query))
    for term in terms:
        clean = _compact(str(term))
        if clean and clean in text:
            score += 1
    if question_type == "career" and ("裸辞" in text or "找工作" in text or "待业" in text):
        score += 2
    if question_type == "migration" and ("新西兰" in text or "旅居" in text or "换城市" in text):
        score += 2
    return score


def _query_terms(query: str) -> list[str]:
    compact = _compact(query)
    terms = []
    for term in ("裸辞", "辞职", "工作", "找工作", "迷茫", "新西兰", "关系", "父母", "考研", "赚钱"):
        if term in compact:
            terms.append(term)
    age_matches = re.findall(r"\d{2}岁", compact)
    terms.extend(age_matches)
    if "30岁" in compact:
        terms.append("三十")
    return terms


def _infer_constraints(text: str, understanding: dict[str, Any]) -> list[str]:
    constraints = []
    checks = (
        ("现金流", ("现金流", "收入", "存款", "钱")),
        ("年龄压力", ("30岁", "三十", "年龄")),
        ("工作匹配度", ("找工作", "面试", "投简历", "岗位")),
        ("身份周期", ("身份", "签证", "移民")),
        ("情绪压力", ("焦虑", "迷茫", "内耗", "压力")),
    )
    for label, markers in checks:
        if any(marker in text for marker in markers):
            constraints.append(label)
    for item in understanding.get("constraints") or []:
        if len(constraints) >= 4:
            break
        if item not in constraints:
            constraints.append(str(item))
    return constraints[:4]


def _suggest_cluster(sample_type: str, choice_action: str, outcome: str, constraints: list[str]) -> str:
    if "考公" in choice_action or "上岸" in outcome:
        return "裸辞后转向考试/体制路径"
    if "自由职业" in choice_action or "做副业" in choice_action:
        return "裸辞后尝试自由职业/副业"
    if "找工作" in choice_action or "投简历" in choice_action or "重回职场" in outcome:
        return "裸辞后重回职场"
    if "现金流" in constraints:
        return "先处理现金流压力"
    if sample_type == "full_story":
        return "完整经历复盘"
    return "真实经历片段"


def _build_reason(sample_type: str, confidence: str, content_length: int, actor_type: str) -> str:
    if sample_type == "full_story":
        return f"包含亲历主体、选择动作和阶段性结果，文本长度约 {content_length} 字，适合作为完整故事候选"
    if sample_type == "partial_experience":
        return f"包含{_actor_label(actor_type)}经历片段，但过程或结果不完整，适合作为片段候选"
    return f"主要是观点，但包含{_actor_label(actor_type)}经历依据，可信度 {confidence}"


def _actor_label(actor_type: str) -> str:
    return {
        "self": "第一人称",
        "observed_other": "观察到的他人",
        "advisor": "专业/身份",
    }.get(actor_type, "可判断的")


def _summarize_key_experience(text: str) -> str:
    clean = re.sub(r"\s+", " ", _text(text)).strip()
    if len(clean) <= 220:
        return clean
    return f"{clean[:220]}..."


def _first_marker(text: str, markers: tuple[str, ...]) -> str:
    for marker in markers:
        if marker in text:
            return marker
    return ""


def _count_markers(text: str, markers: tuple[str, ...]) -> int:
    return sum(1 for marker in markers if marker and marker in text)


def _normalize_content_type(value: Any) -> str:
    raw = _text(value)
    return SOURCE_TYPE_MAP.get(raw.lower(), raw if raw in {"Answer", "Article", "Pin"} else "Unknown")


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", _text(value))


def _chinese_length(value: Any) -> int:
    return len(_compact(_text(value)))


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
