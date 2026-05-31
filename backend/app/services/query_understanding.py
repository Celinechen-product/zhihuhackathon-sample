from __future__ import annotations

import re
from typing import Any


EXPLICIT_CONTEXT_KEYWORDS = (
    "裸辞",
    "转行",
    "辞职",
    "工作",
    "异地恋",
    "父母",
    "结婚",
    "分手",
    "读研",
    "考研",
    "留学",
    "新西兰",
    "移民",
    "城市",
    "回老家",
    "挣钱",
    "买房",
    "存钱",
    "创业",
)

ABSTRACT_QUERY_PATTERNS = (
    "我很焦虑怎么办",
    "我现在很迷茫",
    "我不知道自己要什么",
    "我想换一种生活",
    "我该怎么办",
    "人生好难",
    "不知道怎么选",
)

CLARIFICATION_QUESTION = "你更想看哪类真实经历？"
CLARIFICATION_OPTIONS = [
    "工作选择",
    "关系困扰",
    "家庭压力",
    "换城市/换国家生活",
]

QUESTION_TYPES = (
    "career",
    "relationship",
    "family",
    "money",
    "education",
    "migration",
    "health_life",
    "self_growth",
    "other",
)

TYPE_KEYWORDS = {
    "career": (
        "工作",
        "辞职",
        "裸辞",
        "转行",
        "失业",
        "找工作",
        "职场",
        "上班",
        "职业",
        "离职",
        "跳槽",
        "offer",
        "裁员",
    ),
    "relationship": (
        "异地恋",
        "恋爱",
        "分手",
        "结婚",
        "相亲",
        "婚姻",
        "男朋友",
        "女朋友",
        "伴侣",
    ),
    "family": (
        "父母",
        "原生家庭",
        "控制欲",
        "家庭",
        "亲戚",
        "家里人",
        "养老",
    ),
    "money": (
        "挣钱",
        "赚钱",
        "存款",
        "买房",
        "现金流",
        "负债",
        "收入",
        "副业",
    ),
    "education": (
        "读研",
        "考研",
        "留学",
        "考公",
        "学历",
        "学校",
        "专业",
        "转专业",
    ),
    "migration": (
        "新西兰",
        "移民",
        "出国",
        "回老家",
        "城市",
        "沪漂",
        "北漂",
        "换城市",
        "旅居",
    ),
    "health_life": (
        "焦虑",
        "抑郁",
        "身体",
        "健康",
        "睡眠",
        "倦怠",
        "压力",
    ),
    "self_growth": (
        "迷茫",
        "人生",
        "意义",
        "失败",
        "成就",
        "虚无",
        "不知道自己要什么",
    ),
}

TYPE_PRIORITY = (
    "career",
    "relationship",
    "family",
    "migration",
    "money",
    "education",
    "health_life",
    "self_growth",
)

CLARIFICATION_TYPE_MAP = {
    "工作选择": "career",
    "关系困扰": "relationship",
    "家庭压力": "family",
    "换城市/换国家生活": "migration",
}


def normalize_query(query: str) -> str:
    return re.sub(r"\s+", "", (query or "").strip())


def count_chinese_chars(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", text or ""))


def has_explicit_context(query: str) -> bool:
    normalized = normalize_query(query)
    return any(keyword in normalized for keyword in EXPLICIT_CONTEXT_KEYWORDS)


def is_abstract_query(query: str) -> bool:
    normalized = normalize_query(query)
    if not normalized:
        return True
    if any(pattern in normalized for pattern in ABSTRACT_QUERY_PATTERNS):
        return True
    return count_chinese_chars(normalized) < 8 and not has_explicit_context(normalized)


def need_clarification(query: str) -> bool:
    if has_explicit_context(query):
        return False
    return is_abstract_query(query)


def build_combined_query(query: str, clarification: str | None = None) -> str:
    clean_query = (query or "").strip()
    clean_clarification = (clarification or "").strip()
    if not clean_clarification:
        return clean_query
    return f"{clean_query} {clean_clarification}".strip()


def understand_query(query: str, clarification: str | None = None) -> dict[str, Any]:
    clean_query = (query or "").strip()
    clean_clarification = (clarification or "").strip()
    combined_text = build_combined_query(clean_query, clean_clarification)
    compact_text = normalize_query(combined_text)

    scores = _score_question_types(compact_text)
    primary_type = _primary_type(scores, clean_clarification)
    secondary_types = _secondary_types(
        primary_type=primary_type,
        scores=scores,
        query=compact_text,
        clarification=clean_clarification,
    )

    understanding = _empty_understanding()
    understanding["question_type"] = primary_type
    understanding["secondary_types"] = secondary_types
    understanding["actors"] = ["用户本人"] if clean_query else []

    _apply_common_tags(understanding, compact_text, clean_clarification)
    _apply_type_understanding(understanding, compact_text, clean_clarification)
    _ensure_type_defaults(understanding, clean_query, clean_clarification)
    _dedupe_schema_lists(understanding)
    understanding["search_keywords"] = _seed_search_keywords(clean_query, clean_clarification, understanding)

    return understanding


def build_search_keywords(
    query: str,
    clarification: str | None,
    understanding: dict[str, Any],
    query_context: dict[str, Any] | None = None,
) -> list[str]:
    context = query_context or understanding.get("query_context") or {}
    query_type = _clean_keyword(str(context.get("query_type") or ""))
    effective_query = _clean_keyword(
        str(context.get("effective_query") or build_combined_query(query, clarification))
    )
    compact = normalize_query(effective_query)

    if query_type == "relationship":
        candidates = ["关系困扰", "感情迷茫", "分手经历", "亲密关系"]
        if "异地" in compact:
            candidates.insert(2, "异地恋")
        return _dedupe_keywords(candidates, max_count=6)

    if query_type == "family_money":
        if _looks_like_parent_earning(compact):
            return _dedupe_keywords(
                ["父母50岁赚钱", "父母再就业", "中年赚钱经历", "家庭经济"],
                max_count=6,
            )
        return _dedupe_keywords(
            ["父母要钱", "给父母钱", "家庭经济压力", "边界压力"],
            max_count=6,
        )

    if query_type == "education_gaokao_major":
        candidates = ["高考志愿", "专业选择"]
        if "理科" in compact:
            candidates.insert(1, "理科专业选择")
        elif "文科" in compact:
            candidates.insert(1, "文科专业选择")
        if "广东" in compact:
            candidates.insert(2, "广东高考")
        return _dedupe_keywords(candidates, max_count=6)

    if query_type == "education_postgrad_switch":
        return _dedupe_keywords(
            ["跨专业考研", "专业不喜欢", "考研转专业", "本科转专业"],
            max_count=6,
        )

    if query_type == "migration_new_zealand":
        return _dedupe_keywords(
            [
                "新西兰生活",
                "新西兰 WHV",
                "新西兰 打工度假",
                "新西兰 留学转工签",
                "新西兰 旅居",
                "奥克兰 生活",
                "基督城 生活",
            ],
            max_count=7,
        )

    if query_type == "career_restart":
        candidates = ["职业重启", "失业找工作", "转行经历", "现金流"]
        if "裸辞" in compact:
            candidates.insert(0, "裸辞")
        if "30岁" in compact or "三十" in compact:
            candidates.insert(0, "30岁裸辞" if "裸辞" in compact else "30岁职业")
        return _dedupe_keywords(candidates, max_count=6)

    if query_type == "generic_confusion":
        return _dedupe_keywords(["人生迷茫", "方向不清", "真实经历"], max_count=6)

    return _dedupe_keywords(_fallback_short_keywords(understanding, effective_query), max_count=6)


def _empty_understanding() -> dict[str, Any]:
    return {
        "question_type": "other",
        "secondary_types": [],
        "topic_tags": [],
        "core_question": "",
        "actors": [],
        "user_state": "",
        "goal": "",
        "constraints": [],
        "conflict": "",
        "decision_objects": [],
        "search_keywords": [],
        "classification_axes": [],
        "focus_tags": [],
    }


def _score_question_types(text: str) -> dict[str, int]:
    scores = {question_type: 0 for question_type in QUESTION_TYPES if question_type != "other"}
    for question_type, keywords in TYPE_KEYWORDS.items():
        for keyword in keywords:
            if keyword and keyword in text:
                scores[question_type] += 2 if len(keyword) >= 3 else 1

    if "找不到" in text and "工作" in text:
        scores["career"] += 3
        scores["money"] += 1
        scores["self_growth"] += 1
    if any(marker in text for marker in ("父母要钱", "给父母钱", "给他们钱", "打钱", "赡养", "家庭经济")):
        scores["family"] += 4
        scores["money"] += 3
    if "父母" in text and any(marker in text for marker in ("挣钱", "赚钱", "收入", "再就业", "50多岁")):
        scores["family"] += 4
        scores["money"] += 3
    if any(marker in text for marker in ("高考", "志愿", "填报")):
        scores["education"] += 5
    if any(marker in text for marker in ("跨专业", "本科专业", "专业不喜欢")) and any(marker in text for marker in ("考研", "读研")):
        scores["education"] += 5
    if "不工作" in text or "裸辞" in text or "失业" in text:
        scores["career"] += 2
        scores["money"] += 1
    if any(word in text for word in ("逃离", "不知道怎么选", "不知道该怎么办", "适合")):
        scores["self_growth"] += 1
    if "新西兰" in text or "换城市" in text or "出国" in text:
        scores["migration"] += 3
    return scores


def _primary_type(scores: dict[str, int], clarification: str) -> str:
    clarified_type = CLARIFICATION_TYPE_MAP.get(clarification)
    if clarified_type:
        return clarified_type

    best_type = "other"
    best_score = 0
    for question_type in TYPE_PRIORITY:
        score = scores.get(question_type, 0)
        if score > best_score:
            best_type = question_type
            best_score = score
    return best_type if best_score > 0 else "other"


def _secondary_types(
    *,
    primary_type: str,
    scores: dict[str, int],
    query: str,
    clarification: str,
) -> list[str]:
    secondary: list[str] = []
    for question_type in TYPE_PRIORITY:
        if question_type != primary_type and scores.get(question_type, 0) > 0:
            secondary.append(question_type)

    if clarification and primary_type != "self_growth" and scores.get("self_growth", 0) > 0:
        _append_unique(secondary, "self_growth")
    if primary_type == "career" and any(word in query for word in ("裸辞", "失业", "找不到工作")):
        _append_unique(secondary, "money")
        _append_unique(secondary, "self_growth")
    if primary_type == "migration":
        if any(word in query for word in ("不工作", "工作", "辞职", "裸辞")):
            _append_unique(secondary, "career")
        if any(word in query for word in ("逃离", "迷茫", "适合", "判断")):
            _append_unique(secondary, "self_growth")
    return secondary[:4]


def _apply_common_tags(
    understanding: dict[str, Any],
    text: str,
    clarification: str,
) -> None:
    age_tags = re.findall(r"\d{2}岁", text)
    for tag in age_tags:
        _append_unique(understanding["topic_tags"], tag)
        _append_unique(understanding["focus_tags"], tag)

    if clarification:
        _append_unique(understanding["topic_tags"], clarification)
        if clarification == "工作选择":
            _append_unique(understanding["topic_tags"], "职业方向")
        elif clarification == "关系困扰":
            _append_unique(understanding["topic_tags"], "亲密关系")
        elif clarification == "家庭压力":
            _append_unique(understanding["topic_tags"], "家庭关系")
        elif clarification == "换城市/换国家生活":
            _append_unique(understanding["topic_tags"], "迁移生活")


def _apply_type_understanding(
    understanding: dict[str, Any],
    text: str,
    clarification: str,
) -> None:
    question_type = understanding["question_type"]
    if question_type == "career":
        _apply_career_understanding(understanding, text, clarification)
    elif question_type == "relationship":
        _apply_relationship_understanding(understanding, text, clarification)
    elif question_type == "family":
        _apply_family_understanding(understanding, text, clarification)
    elif question_type == "money":
        _apply_money_understanding(understanding, text)
    elif question_type == "education":
        _apply_education_understanding(understanding, text)
    elif question_type == "migration":
        _apply_migration_understanding(understanding, text, clarification)
    elif question_type == "health_life":
        _apply_health_life_understanding(understanding, text)
    elif question_type == "self_growth":
        _apply_self_growth_understanding(understanding, text)


def _apply_career_understanding(
    understanding: dict[str, Any],
    text: str,
    clarification: str,
) -> None:
    if "迷茫" in text:
        _append_unique(understanding["topic_tags"], "迷茫")
    if "裸辞" in text:
        _append_unique(understanding["topic_tags"], "裸辞")
        _append_unique(understanding["focus_tags"], "裸辞")
    if "找工作" in text or ("找不到" in text and "工作" in text):
        _append_unique(understanding["topic_tags"], "找工作")
    if "转行" in text:
        _append_unique(understanding["topic_tags"], "转行")

    _append_unique(understanding["topic_tags"], "职业重启" if "裸辞" in text else "职业方向")
    _append_unique(understanding["focus_tags"], "职业重启" if "裸辞" in text else "职业方向")
    _append_unique(understanding["focus_tags"], "现金流")
    if re.search(r"\d{2}岁", text):
        _append_unique(understanding["focus_tags"], "年龄压力")

    if "迷茫" in text and clarification:
        understanding["core_question"] = "用户处在迷茫状态，想优先参考工作选择相关的真实经历"
        understanding["user_state"] = "对工作选择和职业方向感到不确定"
    elif "裸辞" in text and ("找不到" in text or "找工作" in text):
        understanding["core_question"] = "裸辞后找不到合适工作，想参考相似经历中的选择和结果"
        understanding["user_state"] = "裸辞后处在职业不确定状态"
    else:
        understanding["core_question"] = "用户想参考工作和职业选择相关的真实经历"
        understanding["user_state"] = "处在职业选择或工作状态变化中"

    understanding["goal"] = "找到下一步职业选择的真实参考"
    understanding["constraints"] = ["年龄压力", "收入压力", "工作匹配度不确定"]
    understanding["conflict"] = "想重新开始，但担心选择结果、工作匹配度和现金流压力"
    understanding["decision_objects"] = ["继续找同类工作", "转行", "降低预期先就业", "休整后再出发"]
    understanding["classification_axes"] = ["后续选择", "现金流压力", "是否转行", "结果走向"]


def _apply_relationship_understanding(
    understanding: dict[str, Any],
    text: str,
    clarification: str,
) -> None:
    if "迷茫" in text:
        _append_unique(understanding["topic_tags"], "迷茫")
    _append_unique(understanding["topic_tags"], "关系困扰")
    _append_unique(understanding["topic_tags"], "亲密关系")
    _append_unique(understanding["focus_tags"], "关系选择")
    _append_unique(understanding["focus_tags"], "亲密关系")
    understanding["core_question"] = "用户处在迷茫状态，想优先参考关系困扰相关的真实经历"
    understanding["user_state"] = "对亲密关系中的选择和边界感到不确定"
    understanding["goal"] = "找到关系选择中的真实参考和结果样本"
    understanding["constraints"] = ["情感投入", "沟通成本", "未来预期不一致"]
    understanding["conflict"] = "想维持关系或做出选择，但担心长期结果和情绪消耗"
    understanding["decision_objects"] = ["继续沟通", "设定边界", "暂缓决定", "结束关系"]
    understanding["classification_axes"] = ["关系阶段", "冲突来源", "沟通方式", "结果走向"]


def _apply_family_understanding(
    understanding: dict[str, Any],
    text: str,
    clarification: str,
) -> None:
    if "迷茫" in text:
        _append_unique(understanding["topic_tags"], "迷茫")
    if any(marker in text for marker in ("要钱", "给父母钱", "给他们钱", "打钱")):
        _append_unique(understanding["topic_tags"], "父母要钱")
        _append_unique(understanding["topic_tags"], "家庭经济支持")
        _append_unique(understanding["focus_tags"], "边界压力")
    if "父母" in text and any(marker in text for marker in ("挣钱", "赚钱", "50多岁", "再就业")):
        _append_unique(understanding["topic_tags"], "父母50多岁")
        _append_unique(understanding["topic_tags"], "赚钱")
        _append_unique(understanding["focus_tags"], "家庭经济")
    _append_unique(understanding["topic_tags"], "家庭压力")
    _append_unique(understanding["topic_tags"], "家庭关系")
    _append_unique(understanding["focus_tags"], "家庭压力")
    _append_unique(understanding["focus_tags"], "边界")
    understanding["core_question"] = "用户想优先参考家庭压力相关的真实经历"
    understanding["user_state"] = "在家庭期待、边界和个人选择之间承压"
    understanding["goal"] = "找到处理家庭压力和个人边界的真实参考"
    understanding["constraints"] = ["亲情压力", "沟通成本", "经济或照护责任"]
    understanding["conflict"] = "想保留个人选择，但又担心家庭关系和责任压力"
    understanding["decision_objects"] = ["直接沟通", "设定边界", "部分妥协", "拉开距离"]
    understanding["classification_axes"] = ["压力来源", "边界强度", "经济责任", "结果走向"]


def _apply_money_understanding(understanding: dict[str, Any], text: str) -> None:
    _append_unique(understanding["topic_tags"], "收入压力")
    _append_unique(understanding["focus_tags"], "现金流")
    _append_unique(understanding["focus_tags"], "收入")
    understanding["core_question"] = "用户想参考金钱和现金流压力下的真实选择经历"
    understanding["user_state"] = "面临收入、存款或负债相关压力"
    understanding["goal"] = "找到改善现金流或降低财务风险的真实参考"
    understanding["constraints"] = ["收入不确定", "支出压力", "风险承受能力有限"]
    understanding["conflict"] = "想改善财务状态，但不确定该优先稳定还是尝试新机会"
    understanding["decision_objects"] = ["稳定收入", "发展副业", "降低支出", "推迟大额决策"]
    understanding["classification_axes"] = ["现金流压力", "风险承受", "收入来源", "结果走向"]


def _apply_education_understanding(understanding: dict[str, Any], text: str) -> None:
    _append_unique(understanding["topic_tags"], "教育选择")
    _append_unique(understanding["focus_tags"], "学历")
    _append_unique(understanding["focus_tags"], "长期回报")
    understanding["core_question"] = "用户想参考教育和长期发展选择中的真实经历"
    understanding["user_state"] = "在读研、考研、留学或专业选择中不确定"
    understanding["goal"] = "找到教育选择对后续生活和职业的真实影响"
    understanding["constraints"] = ["时间成本", "经济成本", "长期回报不确定"]
    understanding["conflict"] = "想提升选择空间，但担心投入和结果不匹配"
    understanding["decision_objects"] = ["继续读书", "直接就业", "换专业", "考公或留学"]
    understanding["classification_axes"] = ["投入成本", "专业方向", "结果走向", "长期回报"]


def _apply_migration_understanding(
    understanding: dict[str, Any],
    text: str,
    clarification: str,
) -> None:
    if "新西兰" in text:
        _append_unique(understanding["topic_tags"], "新西兰")
        _append_unique(understanding["focus_tags"], "新西兰")
    if "旅居" in text or "生活" in text:
        _append_unique(understanding["topic_tags"], "旅居生活")
    if "不工作" in text or "裸辞" in text:
        _append_unique(understanding["topic_tags"], "不工作")
    _append_unique(understanding["topic_tags"], "迁移生活")
    _append_unique(understanding["focus_tags"], "现金流")
    _append_unique(understanding["focus_tags"], "身份")
    _append_unique(understanding["focus_tags"], "适配度")

    if "新西兰" in text and ("逃离" in text or "适合" in text):
        understanding["core_question"] = "想去新西兰生活，但需要判断这是适合自己的迁移选择，还是对当下生活的逃离"
        understanding["user_state"] = "对不工作后的生活地点和长期适配度感到不确定"
    else:
        understanding["core_question"] = "用户想参考换城市或换国家生活相关的真实经历"
        understanding["user_state"] = "在迁移生活和原有生活之间评估可能性"
    understanding["goal"] = "找到迁移生活的真实参考，包括现金流、身份和长期适配度"
    understanding["constraints"] = ["现金流压力", "身份周期", "语言和社交成本", "长期适配度不确定"]
    understanding["conflict"] = "想换一种生活，但不确定远方是否真的解决问题"
    understanding["decision_objects"] = ["短期旅居", "长期移居", "先休整再决定", "留在原城市调整生活"]
    understanding["classification_axes"] = ["迁移方式", "现金流压力", "身份路径", "是否回流"]


def _apply_health_life_understanding(understanding: dict[str, Any], text: str) -> None:
    _append_unique(understanding["topic_tags"], "身心状态")
    _append_unique(understanding["focus_tags"], "压力")
    _append_unique(understanding["focus_tags"], "生活节奏")
    understanding["core_question"] = "用户想参考身心压力和生活状态调整相关的真实经历"
    understanding["user_state"] = "处在焦虑、压力、睡眠或倦怠相关困扰中"
    understanding["goal"] = "找到改善生活状态和压力来源的真实参考"
    understanding["constraints"] = ["精力有限", "环境压力", "恢复周期不确定"]
    understanding["conflict"] = "想恢复状态，但不确定应该改变工作、生活节奏还是外部环境"
    understanding["decision_objects"] = ["休整", "调整工作", "改变生活节奏", "寻求支持"]
    understanding["classification_axes"] = ["压力来源", "恢复方式", "环境变化", "结果走向"]


def _apply_self_growth_understanding(understanding: dict[str, Any], text: str) -> None:
    _append_unique(understanding["topic_tags"], "迷茫")
    _append_unique(understanding["topic_tags"], "人生选择")
    _append_unique(understanding["focus_tags"], "迷茫")
    _append_unique(understanding["focus_tags"], "方向感")
    understanding["core_question"] = "用户处在迷茫状态，想参考相似人生选择中的真实经历"
    understanding["user_state"] = "不确定自己想要什么或下一步怎么选"
    understanding["goal"] = "找到相似迷茫阶段中的真实选择和结果"
    understanding["constraints"] = ["目标不清晰", "选择标准不稳定", "结果不确定"]
    understanding["conflict"] = "想改变现状，但不知道该把问题落到哪个具体方向"
    understanding["decision_objects"] = ["继续探索", "先选一个方向尝试", "暂停休整", "寻求外部反馈"]
    understanding["classification_axes"] = ["迷茫来源", "尝试方式", "选择标准", "结果走向"]


def _ensure_type_defaults(
    understanding: dict[str, Any],
    query: str,
    clarification: str,
) -> None:
    if understanding["core_question"]:
        return

    combined_query = build_combined_query(query, clarification)
    understanding["core_question"] = combined_query or "用户想参考相似真实经历"
    understanding["user_state"] = ""
    understanding["goal"] = "找到相似真实经历作为参考"
    understanding["classification_axes"] = ["问题类型", "选择路径", "结果走向"]


def _seed_search_keywords(
    query: str,
    clarification: str,
    understanding: dict[str, Any],
) -> list[str]:
    question_type = understanding["question_type"]
    combined_query = _clean_keyword(build_combined_query(query, clarification))
    seeds = [combined_query]

    if question_type == "career":
        if "裸辞" in combined_query:
            seeds.extend(["30岁裸辞 找不到工作 真实经历", "裸辞后重新找工作 知乎", "30岁转行 失业 经历"])
        else:
            seeds.extend(["工作迷茫 真实经历 知乎", "职业方向迷茫 后来怎么样", "工作选择 后悔 知乎"])
    elif question_type == "relationship":
        seeds.extend(["关系困扰 真实经历 知乎", "恋爱迷茫 后来怎么样", "亲密关系 亲身经历"])
    elif question_type == "family":
        seeds.extend(["家庭压力 真实经历 知乎", "父母压力 后来怎么样", "原生家庭 控制欲 亲身经历"])
    elif question_type == "migration":
        if "新西兰" in combined_query:
            seeds.extend(["裸辞 去新西兰 真实经历", "新西兰 旅居 亲身经历 知乎", "新西兰 长期生活 现金流 身份"])
        else:
            seeds.extend(["换城市生活 真实经历 知乎", "旅居 亲身经历 知乎", "出国生活 后来怎么样"])
    elif question_type == "self_growth":
        seeds.extend(["人生迷茫 真实经历 知乎", "不知道自己要什么 后来怎么样", "迷茫 后悔 知乎"])

    return _dedupe_keywords(seeds, max_count=5)


def _looks_like_parent_earning(compact_text: str) -> bool:
    return any(marker in compact_text for marker in ("父母50", "爸妈50", "父母五十", "爸妈五十", "50多岁")) and any(
        marker in compact_text for marker in ("挣钱", "赚钱", "收入", "再就业")
    )


def _fallback_short_keywords(understanding: dict[str, Any], effective_query: str) -> list[str]:
    tags = [
        str(item).strip()
        for item in (understanding.get("topic_tags") or []) + (understanding.get("focus_tags") or [])
        if str(item).strip()
    ]
    if tags:
        return tags[:4]

    compact_query = normalize_query(effective_query)
    if "父母" in compact_query:
        return ["父母关系", "家庭压力", "边界"]
    if "专业" in compact_query:
        return ["专业选择", "教育选择"]
    if "工作" in compact_query:
        return ["工作选择", "职业方向"]
    return ["真实经历", "人生选择"]


def _primary_topic(understanding: dict[str, Any], combined_query: str) -> str:
    for field in ("topic_tags", "focus_tags"):
        values = understanding.get(field) or []
        if values:
            return str(values[0])
    return combined_query or "人生选择"


def _dedupe_schema_lists(understanding: dict[str, Any]) -> None:
    for key, value in list(understanding.items()):
        if isinstance(value, list):
            understanding[key] = _dedupe_strings(value)


def _dedupe_strings(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value).strip()
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result


def _dedupe_keywords(candidates: list[str], max_count: int = 8) -> list[str]:
    keywords: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        keyword = _clean_keyword(candidate)
        if not keyword or keyword in seen:
            continue
        keywords.append(keyword)
        seen.add(keyword)
        if len(keywords) >= max_count:
            break
    return keywords


def _clean_keyword(value: str) -> str:
    value = (value or "").strip()
    value = re.sub(r"[，。！？、；：,.!?;:]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)
