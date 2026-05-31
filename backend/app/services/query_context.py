from __future__ import annotations

from typing import Any


RELATIONSHIP_TOPICS = [
    "关系困扰",
    "亲密关系",
    "感情迷茫",
    "分手",
    "沟通",
    "修复",
    "恋爱",
    "婚恋",
    "异地恋",
]

FAMILY_MONEY_PARENT_SUPPORT_TOPICS = [
    "父母要钱",
    "家庭经济支持",
    "边界压力",
    "给父母钱",
]

FAMILY_MONEY_PARENT_EARNING_TOPICS = [
    "父母50多岁",
    "赚钱",
    "家庭经济",
    "父母再就业",
]

GAOKAO_MAJOR_TOPICS = [
    "高考志愿",
    "理科",
    "专业选择",
    "分数",
]

POSTGRAD_SWITCH_TOPICS = [
    "本科专业不喜欢",
    "跨专业",
    "考研",
    "读研",
]

CAREER_EXCLUDE_TOPICS = [
    "裸辞",
    "找工作",
    "考公",
    "考编",
    "职业重启",
    "失业",
    "转行",
]

NEW_ZEALAND_TOPICS = [
    "新西兰生活",
    "WHV",
    "旅居",
    "打工度假",
    "留学转工签",
    "留学",
    "工签",
    "移民",
    "远程工作",
    "奥克兰",
    "基督城",
]

NEW_ZEALAND_EXCLUDE_TOPICS = [
    "考公",
    "考编",
    "公务员",
    "体制内",
    "普通找工作",
    "国内职业重启",
]


def build_query_context(
    query: str,
    clarification: str | None = None,
    understanding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clean_query = _text(query)
    clean_clarification = _text(clarification)
    effective_query = f"{clean_query} {clean_clarification}".strip()
    compact = _compact(effective_query)
    query_type = _infer_query_type(compact, clean_clarification, understanding or {})
    must_include_topics, must_exclude_topics = _topic_constraints(query_type, compact)
    return {
        "original_query": clean_query,
        "clarification": clean_clarification,
        "effective_query": effective_query,
        "query_type": query_type,
        "must_include_topics": must_include_topics,
        "must_exclude_topics": must_exclude_topics,
    }


def _infer_query_type(
    compact_text: str,
    clarification: str,
    understanding: dict[str, Any],
) -> str:
    if clarification == "关系困扰":
        return "relationship"
    if clarification == "工作选择":
        return "career_restart"
    if clarification == "家庭压力" and _is_family_money(compact_text):
        return "family_money"
    if clarification == "家庭压力":
        return "family"
    if clarification == "换城市/换国家生活" and "新西兰" in compact_text:
        return "migration_new_zealand"
    if clarification == "换城市/换国家生活":
        return "generic_confusion"

    if "新西兰" in compact_text:
        return "migration_new_zealand"
    if any(marker in compact_text for marker in ("恋爱", "分手", "结婚", "异地恋", "亲密关系", "伴侣", "感情", "关系困扰")):
        return "relationship"
    if _is_family_money(compact_text):
        return "family_money"
    if _is_gaokao_major(compact_text):
        return "education_gaokao_major"
    if _is_postgrad_switch(compact_text):
        return "education_postgrad_switch"
    if any(marker in compact_text for marker in ("裸辞", "辞职", "离职", "找工作", "失业", "转行", "职场", "职业重启")):
        return "career_restart"
    if any(marker in compact_text for marker in ("考研", "读研", "留学", "学历", "学校", "专业")):
        return "education_postgrad_switch" if any(marker in compact_text for marker in ("考研", "读研", "跨专业", "转专业")) else "education"
    if any(marker in compact_text for marker in ("父母", "家庭", "家里人", "原生家庭")):
        return "family"
    if any(marker in compact_text for marker in ("收入", "存款", "负债", "赚钱", "现金流", "买房")):
        return "money"
    if any(marker in compact_text for marker in ("迷茫", "不知道", "怎么选", "怎么办")):
        return "generic_confusion"

    legacy_type = _text(understanding.get("question_type"))
    return {
        "career": "career_restart",
        "relationship": "relationship",
        "family": "family",
        "money": "money",
        "education": "education",
        "migration": "generic_confusion",
        "self_growth": "generic_confusion",
    }.get(legacy_type, "unknown")


def _topic_constraints(query_type: str, compact_text: str) -> tuple[list[str], list[str]]:
    if query_type == "relationship":
        return RELATIONSHIP_TOPICS[:], CAREER_EXCLUDE_TOPICS[:]
    if query_type == "family_money":
        if _is_parent_earning_query(compact_text):
            return FAMILY_MONEY_PARENT_EARNING_TOPICS[:], ["职业选择", "找工作", "裸辞", "考研", "高考志愿"]
        return FAMILY_MONEY_PARENT_SUPPORT_TOPICS[:], ["职业选择", "找工作", "裸辞", "考研", "高考志愿"]
    if query_type == "education_gaokao_major":
        topics = GAOKAO_MAJOR_TOPICS[:]
        if "文科" in compact_text:
            topics[1] = "文科"
        return topics, ["考研", "读研", "跨专业", "转专业", "裸辞职业重启"]
    if query_type == "education_postgrad_switch":
        return POSTGRAD_SWITCH_TOPICS[:], ["高考志愿", "高考分数", "理科志愿", "文科志愿", "裸辞职业重启"]
    if query_type == "migration_new_zealand":
        return NEW_ZEALAND_TOPICS[:], NEW_ZEALAND_EXCLUDE_TOPICS[:]
    if query_type == "career_restart":
        include = ["职业选择", "职业重启", "工作", "找工作", "裸辞", "转行", "现金流"]
        if "裸辞" not in compact_text:
            include = ["职业选择", "工作", "找工作", "转行", "现金流"]
        return include, ["亲密关系", "分手", "婚恋", "新西兰移民政策攻略"]
    if query_type == "education":
        return ["教育选择", "考研", "读研", "留学", "学历", "专业"], ["裸辞职业重启", "情感鸡汤"]
    if query_type == "family":
        return ["家庭压力", "父母", "家庭关系", "边界", "沟通"], ["裸辞职业重启", "考公考编"]
    if query_type == "money":
        return ["收入", "现金流", "存款", "负债", "赚钱"], ["情感鸡汤", "移民中介"]
    if query_type == "generic_confusion":
        return [], ["营销", "纯观点", "鸡汤"]
    return ["真实经历", "人生选择"], ["营销", "纯观点", "鸡汤"]


def _is_family_money(compact_text: str) -> bool:
    has_family = any(marker in compact_text for marker in ("父母", "爸妈", "家里", "家庭"))
    has_money = any(
        marker in compact_text
        for marker in (
            "要钱",
            "给钱",
            "给他们钱",
            "打钱",
            "生活费",
            "赡养",
            "经济支持",
            "家庭经济",
            "挣钱",
            "赚钱",
            "收入",
            "再就业",
        )
    )
    return has_family and has_money


def _is_parent_earning_query(compact_text: str) -> bool:
    return any(marker in compact_text for marker in ("父母50", "爸妈50", "父母五十", "爸妈五十", "50多岁")) and any(
        marker in compact_text for marker in ("挣钱", "赚钱", "收入", "再就业")
    )


def _is_gaokao_major(compact_text: str) -> bool:
    return any(marker in compact_text for marker in ("高考", "志愿", "填报", "分数")) and any(
        marker in compact_text for marker in ("专业", "理科", "文科", "志愿", "填报")
    )


def _is_postgrad_switch(compact_text: str) -> bool:
    return any(marker in compact_text for marker in ("考研", "读研", "研究生")) and any(
        marker in compact_text for marker in ("本科专业", "专业不喜欢", "跨专业", "转专业")
    )


def _compact(value: Any) -> str:
    return "".join(_text(value).split())


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
