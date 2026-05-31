from __future__ import annotations

import re
from typing import Any


ROLE_MARKERS = (
    ("HR", "HR"),
    ("人事", "人事"),
    ("工程岗", "工程岗"),
    ("工程师", "工程岗"),
    ("自由职业", "自由职业者"),
    ("大厂", "大厂员工"),
    ("国企", "国企员工"),
    ("产品经理", "产品经理"),
    ("待业", "裸辞待业者"),
    ("裸辞", "裸辞经历者"),
)

CHOICE_MARKERS = (
    "裸辞",
    "考公",
    "考编",
    "找工作",
    "投简历",
    "降薪去小公司",
    "去小公司",
    "自由职业",
    "副业",
    "回老家",
    "继续待业",
    "重回职场",
    "离职",
    "辞职",
)

OUTCOME_MARKERS = (
    ("没有上岸", ("没有上岸", "没上岸")),
    ("重回职场", ("重回职场", "回职场", "找到工作")),
    ("继续自由职业", ("继续自由职业", "自由职业3年")),
    ("放弃某些副业", ("放弃", "亏损")),
    ("仍在找工作", ("仍在找工作", "找不到工作")),
    ("上岸", ("上岸",)),
    ("收入不稳定", ("收入不稳定", "钱不稳定")),
)

CONSTRAINT_MARKERS = (
    ("现金流压力", ("现金流", "存款", "房租", "收入", "钱", "首付")),
    ("年龄压力", ("30岁", "三十", "32岁", "33岁", "年龄")),
    ("家人压力", ("家人", "父母", "家庭")),
    ("找工作困难", ("找工作", "投简历", "面试", "岗位", "找不到工作")),
    ("行业缩招", ("缩招", "裁员", "就业市场")),
    ("收入不稳定", ("收入不稳定", "钱不稳定", "接单")),
    ("社交圈萎缩", ("社交圈", "圈子变小")),
    ("健康/精神内耗", ("焦虑", "内耗", "失眠", "精神", "健康", "抑郁")),
)

TIMELINE_MARKERS = (
    ("裸辞前", ("离职前", "裸辞前", "辞职前")),
    ("裸辞后", ("裸辞后", "辞职后", "离职后")),
    ("第一个月", ("第一个月", "裸辞后的第一个月")),
    ("三个月后", ("三个月后", "3个月后")),
    ("半年后", ("半年后", "6个月后")),
    ("第5个月", ("第5个月", "第五个月")),
    ("去年", ("去年",)),
    ("今年", ("今年",)),
    ("后来", ("后来",)),
    ("最终", ("最终", "最后")),
    ("10.16更", ("10.16更",)),
)

MARKETING_MARKERS = (
    "半年赚了50万",
    "半年赚50万",
    "月入10万",
    "暴富",
    "逆袭",
)

AGE_PATTERNS = (
    r"\d{2}\s*岁(?:左右|前后)?",
    r"\d{2}\+",
    r"三十岁(?:左右|前后)?",
    r"年近四十",
)

STATUS_MARKERS = (
    ("裸辞后待业6个月", ("裸辞待业6个月", "待业6个月")),
    ("裸辞14个月后仍在试各种出路", ("裸辞14个月",)),
    ("裸辞后空窗3个月", ("空窗3个月",)),
    ("做了3年自由职业", ("自由职业3年",)),
    ("考公没有上岸", ("考公未上岸", "没有上岸", "没上岸")),
    ("裸辞后还没找到稳定工作", ("找不到工作", "找不到合适的工作")),
    ("裸辞后收入不稳定", ("收入不稳定",)),
    ("裸辞后社交圈变小", ("社交圈萎缩",)),
    ("裸辞后待业", ("待业",)),
)

SITUATION_MARKERS = (
    ("投简历", "投简历"),
    ("面试", "面试"),
    ("找不到合适工作", "找不到合适的工作"),
    ("找不到稳定工作", "找不到工作"),
    ("现金流压力", "现金流"),
    ("存款压力", "存款"),
    ("家人压力", "家人"),
    ("父母压力", "父母"),
    ("收入波动", "收入不稳定"),
    ("社交圈变小", "社交圈萎缩"),
    ("反复焦虑", "焦虑"),
    ("精神内耗", "内耗"),
    ("失眠", "失眠"),
    ("课程学习", "课程学习"),
    ("降低预期", "降预期"),
)


def extract_people_draft(
    candidates: list[dict[str, Any]],
    query: str,
    understanding: dict[str, Any],
) -> list[dict[str, Any]]:
    drafts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not _should_extract(candidate):
            continue
        draft = extract_one_person_draft(candidate, query=query, understanding=understanding)
        source_url = draft.get("source", {}).get("url", "")
        if not source_url:
            continue
        key = draft.get("id") or source_url
        if key in seen:
            continue
        seen.add(key)
        drafts.append(draft)
    return drafts


def extract_one_person_draft(
    candidate: dict[str, Any],
    query: str,
    understanding: dict[str, Any],
) -> dict[str, Any]:
    source = candidate.get("source") if isinstance(candidate.get("source"), dict) else {}
    author = candidate.get("author") if isinstance(candidate.get("author"), dict) else {}
    raw_id = _text(candidate.get("raw_id")) or _slug(source.get("url"))
    title = _text(source.get("title"))
    source_url = _text(source.get("url"))
    content_type = _text(source.get("content_type"))
    sample_type = _text(candidate.get("sample_type"))
    key_experience = _text(candidate.get("key_experience"))
    source_excerpt = _source_excerpt(source.get("excerpt") or key_experience)
    text = f"{title}\n{source_excerpt}\n{key_experience}"
    compact_text = _compact(text)

    role = _extract_role(compact_text)
    choice_action = _extract_choice_action(compact_text, candidate)
    outcome = _extract_outcome(compact_text, candidate)
    constraints = _extract_constraints(compact_text, candidate, understanding)
    timeline = _extract_timeline(compact_text, sample_type)
    confidence = _adjust_confidence(_text(candidate.get("confidence")), compact_text)
    suggested_cluster = _suggest_cluster(choice_action, outcome, constraints, candidate)

    return {
        "id": f"person_{raw_id}" if raw_id else f"person_{_slug(source_url) or 'unknown'}",
        "sample_type": sample_type,
        "name": _text(author.get("name")) or "知乎用户",
        "role": role,
        "badge": _build_badge(title, choice_action, outcome, constraints),
        "oneLine": _build_one_line(
            role,
            choice_action,
            outcome,
            title,
            source_excerpt,
        ),
        "who": _build_who(role, choice_action, constraints, title, source_excerpt),
        "matchReasons": _build_match_reasons(
            compact_text,
            constraints,
            choice_action,
            outcome,
            suggested_cluster,
        ),
        "timeline": timeline,
        "keyExperience": _build_key_experience(choice_action, outcome, constraints, key_experience),
        "choice_action": choice_action,
        "outcome": outcome,
        "constraints": constraints,
        "suggested_cluster": suggested_cluster,
        "sourceExcerpt": source_excerpt,
        "sourceTitle": title,
        "sourceUrl": source_url,
        "source": {
            "title": title,
            "url": source_url,
            "content_type": content_type,
            "author_name": _text(author.get("name")),
            "author_avatar": _text(author.get("avatar")),
            "excerpt": source_excerpt,
        },
        "confidence": confidence,
        "extraction_notes": _build_extraction_notes(candidate, timeline, outcome),
    }


def _should_extract(candidate: dict[str, Any]) -> bool:
    source = candidate.get("source") if isinstance(candidate.get("source"), dict) else {}
    title = _text(source.get("title"))
    if not _text(source.get("url")):
        return False
    if candidate.get("sample_type") == "opinion_only":
        return False
    if not candidate.get("has_real_experience"):
        return False
    if any(marker in title for marker in MARKETING_MARKERS):
        return False
    return True


def _extract_role(text: str) -> str:
    for marker, role in ROLE_MARKERS:
        if marker in text:
            return role
    return "知乎用户"


def _extract_choice_action(text: str, candidate: dict[str, Any]) -> str:
    existing = _text(candidate.get("choice_action"))
    if existing:
        return _normalize_choice(existing, text)
    for marker in CHOICE_MARKERS:
        if marker in text:
            return _normalize_choice(marker, text)
    return ""


def _normalize_choice(choice: str, text: str) -> str:
    if "考公" in text:
        return "考公"
    if "自由职业" in text:
        return "自由职业"
    if "副业" in text:
        return "副业试错"
    if "重回职场" in text or "回职场" in text:
        return "重新回职场"
    if "找工作" in text or "投简历" in text:
        return "找工作"
    if "裸辞" in text:
        return "裸辞"
    return choice


def _extract_outcome(text: str, candidate: dict[str, Any]) -> str:
    existing = _text(candidate.get("outcome"))
    for outcome, markers in OUTCOME_MARKERS:
        if any(marker in text for marker in markers):
            return outcome
    if existing:
        return _normalize_outcome(existing, text)
    return "原文未明确提到后续结果"


def _normalize_outcome(outcome: str, text: str) -> str:
    if outcome in {"没上岸"}:
        return "没有上岸"
    if outcome in {"回职场", "找到工作"}:
        return "重回职场"
    if outcome == "亏损":
        return "收入不稳定"
    if outcome == "收入" and ("收入不稳定" in text or "现金流" in text):
        return "收入不稳定"
    if outcome in {"收入", "继续", "改变"}:
        return "原文未明确提到后续结果"
    return outcome


def _extract_constraints(
    text: str,
    candidate: dict[str, Any],
    understanding: dict[str, Any],
) -> list[str]:
    constraints: list[str] = []
    for label, markers in CONSTRAINT_MARKERS:
        if any(marker in text for marker in markers):
            _append_unique(constraints, label)
    for item in candidate.get("constraints") or []:
        _append_unique(constraints, _normalize_constraint(str(item)))
    for item in understanding.get("constraints") or []:
        if len(constraints) >= 5:
            break
        _append_unique(constraints, _normalize_constraint(str(item)))
    return [item for item in constraints if item][:5]


def _normalize_constraint(value: str) -> str:
    if value in {"现金流", "收入压力"}:
        return "现金流压力"
    if value == "工作匹配度":
        return "找工作困难"
    if value == "情绪压力":
        return "健康/精神内耗"
    return value


def _extract_timeline(text: str, sample_type: str) -> list[list[str]]:
    if sample_type != "full_story":
        return []
    timeline: list[list[str]] = []
    for label, markers in TIMELINE_MARKERS:
        if any(marker in text for marker in markers):
            event = _timeline_event(label, text)
            if event:
                timeline.append([label, event])
    return timeline[:5]


def _timeline_event(label: str, text: str) -> str:
    if label in {"裸辞前", "去年", "今年"}:
        if "内耗" in text or "压力" in text:
            return "原文提到当时处在职场内耗或工作压力中"
        return "原文提到这一阶段出现了职业选择变化"
    if label == "裸辞后":
        return "开始面对待业、找工作或下一步方向的不确定"
    if label in {"第一个月", "三个月后", "半年后", "第5个月"}:
        return "原文出现阶段性时间线，描述了裸辞后的尝试和压力"
    if label == "后来":
        return "原文提到后续尝试、调整或阶段性变化"
    if label == "最终":
        return "原文提到阶段性结果"
    if label == "10.16更":
        return "原文有后续更新"
    return ""


def _build_badge(title: str, choice_action: str, outcome: str, constraints: list[str]) -> str:
    cleaned_title = re.sub(r"\s*-\s*知乎$", "", _text(title)).strip()
    if cleaned_title and len(cleaned_title) <= 34:
        return cleaned_title
    if "自由职业" in cleaned_title:
        return "裸辞后，自由职业试错"
    if "待业6个月" in cleaned_title or "待业" in cleaned_title:
        return "裸辞后，待业再重回职场"
    if "考公" in cleaned_title:
        return "裸辞考公后的阶段复盘"
    if choice_action and outcome and outcome != "原文未明确提到后续结果":
        return f"{choice_action}后，{outcome}"
    if choice_action:
        return f"{choice_action}后的真实经历"
    if constraints:
        return f"经历过{constraints[0]}"
    return "知乎真实经历候选"


def _build_one_line(
    role: str,
    choice_action: str,
    outcome: str,
    title: str,
    source_excerpt: str,
) -> str:
    text = f"{title}\n{source_excerpt}"
    subject = "TA "
    status = _extract_status(text)
    details = _extract_situations(text, limit=3)
    detail_text = _join_natural(details)
    if status and detail_text:
        return _limit(f"{subject}{status}，经历了{detail_text}。", 88)
    if choice_action and detail_text:
        return _limit(f"{subject}{_choice_sentence(choice_action)}，随后经历了{detail_text}。", 88)
    if choice_action and outcome and outcome != "原文未明确提到后续结果":
        return _limit(f"{subject}{_choice_sentence(choice_action)}，最后能看到的阶段性结果是{outcome}。", 88)
    if choice_action:
        return _limit(f"{subject}{_choice_sentence(choice_action)}，但后续结果还不完整。", 88)
    return _limit("TA 分享了一段裸辞后的真实片段，能看到离开工作后的不确定感。", 88)


def _build_who(
    role: str,
    choice_action: str,
    constraints: list[str],
    title: str,
    source_excerpt: str,
) -> str:
    text = f"{title}\n{source_excerpt}"
    age = _extract_age(text)
    status = _extract_status(text)
    situations = _extract_situations(text, limit=2)
    if not situations:
        situations = [_normalize_constraint(item) for item in constraints[:2] if item]
    situation_text = _join_natural(situations)
    identity = _human_identity(role)
    lead_parts = [item for item in (age, identity, status) if item]
    lead = "，".join(lead_parts)
    if lead and situation_text:
        return _limit(f"{lead}，{display_choice_or_state(choice_action)}，同时面对{situation_text}。", 96)
    if lead:
        return _limit(f"{lead}，处在裸辞后的下一步选择阶段。", 96)
    if situation_text:
        return _limit(f"这位知友分享了裸辞后的真实片段，重点是{situation_text}。", 96)
    return "这位知友分享了裸辞后的真实片段，重点是离开工作后的不确定感。"


def _build_match_reasons(
    text: str,
    constraints: list[str],
    choice_action: str,
    outcome: str,
    suggested_cluster: str,
) -> list[str]:
    reasons: list[str] = []
    situations = _extract_situations(text, limit=3)
    situation_text = _join_natural(situations)
    similar = _similar_context_reason(text, choice_action)
    if similar:
        _append_unique(reasons, similar)
    if situation_text:
        _append_unique(reasons, f"原文把{situation_text}这些细节写出来了，不只是讲道理。")
    elif constraints:
        _append_unique(reasons, f"TA 写到的现实压力包括{_join_natural(constraints[:2])}，能看到裸辞后的具体代价。")
    value = _reference_value_reason(suggested_cluster, outcome)
    if value:
        _append_unique(reasons, value)
    return reasons[:3] or ["TA 的经历能补上一段真实处境，而不是只给抽象建议。"]


def _similar_context_reason(text: str, choice_action: str) -> str:
    if "30岁" in text or "三十" in text or "30+" in text:
        if "找工作" in text or "投简历" in text or "面试" in text:
            return "TA 同样面对30岁前后的职业重启和重新求职。"
        return "TA 也处在30岁前后的裸辞选择阶段。"
    if "找不到工作" in text or "找不到合适" in text:
        return "TA 也经历了裸辞后找不到稳定方向的阶段。"
    if choice_action:
        return f"TA 也走到了裸辞后要不要{choice_action}的选择点。"
    return "TA 也在裸辞后寻找下一步，不是旁观式建议。"


def _reference_value_reason(suggested_cluster: str, outcome: str) -> str:
    if "重新找工作" in suggested_cluster:
        return "这段经历能帮你看到重新找工作这条路的真实压力点。"
    if "自由职业" in suggested_cluster:
        return "这段经历能作为自由职业试错路径的阶段性样本。"
    if "考公" in suggested_cluster:
        return "这段经历能帮你看到把考公考编当出口时的不确定性。"
    if "休整" in suggested_cluster:
        return "这段经历能帮你区分短暂休整和长期停滞的边界。"
    if outcome and outcome != "原文未明确提到后续结果":
        return f"它至少给出了一个阶段性结果：{outcome}。"
    return "这段经历适合作为裸辞后继续观察下一步的真实样本。"


def _build_key_experience(
    choice_action: str,
    outcome: str,
    constraints: list[str],
    key_experience: str,
) -> str:
    if constraints:
        text = f"这段经历里最明确的是：{choice_action or '做出选择'}之后，{ '、'.join(constraints[:3]) }会同时出现压力。"
        if outcome and outcome != "原文未明确提到后续结果":
            text += f" 原文提到的阶段性结果是「{outcome}」。"
        return text
    return _limit(key_experience, 120)


def _suggest_cluster(
    choice_action: str,
    outcome: str,
    constraints: list[str],
    candidate: dict[str, Any],
) -> str:
    existing = _text(candidate.get("suggested_cluster"))
    if "考公" in choice_action or "上岸" in outcome:
        return "裸辞后考公/考编"
    if "自由职业" in choice_action or "副业" in choice_action or "收入不稳定" in constraints:
        return "裸辞后自由职业试错"
    if "找工作" in choice_action or "重回职场" in outcome or "找工作困难" in constraints:
        return "裸辞后重新找工作"
    if "健康/精神内耗" in constraints:
        return "裸辞后先休整再重启"
    return existing or "裸辞后先休整再重启"


def _adjust_confidence(confidence: str, text: str) -> str:
    if any(marker in text for marker in MARKETING_MARKERS):
        return "low"
    return confidence if confidence in {"high", "medium", "low"} else "low"


def _build_extraction_notes(
    candidate: dict[str, Any],
    timeline: list[list[str]],
    outcome: str,
) -> str:
    notes = [f"基于规则从 {candidate.get('sample_type', '')} candidate 抽取"]
    if not timeline:
        notes.append("未抽到明确 timeline")
    if outcome == "原文未明确提到后续结果":
        notes.append("未抽到明确 outcome")
    return "；".join(notes)


def _extract_age(text: str) -> str:
    for pattern in AGE_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return re.sub(r"\s+", "", match.group(0))
    return ""


def _extract_status(text: str) -> str:
    for label, markers in STATUS_MARKERS:
        if any(marker in text for marker in markers):
            return label
    return ""


def _extract_situations(text: str, limit: int = 3) -> list[str]:
    hits: list[str] = []
    for label, marker in SITUATION_MARKERS:
        if marker in text:
            _append_unique(hits, label)
        if len(hits) >= limit:
            break
    return hits


def _join_natural(values: list[str]) -> str:
    clean = [item for item in values if item]
    if not clean:
        return ""
    if len(clean) == 1:
        return clean[0]
    return "、".join(clean)


def _human_identity(role: str) -> str:
    if role in {"知乎用户", "裸辞经历者"}:
        return ""
    return role


def _choice_sentence(choice_action: str) -> str:
    return {
        "找工作": "裸辞后继续找工作",
        "投简历": "裸辞后继续投简历",
        "重新回职场": "裸辞后重新回到职场",
        "自由职业": "裸辞后尝试自由职业",
        "副业试错": "裸辞后尝试副业",
        "考公": "裸辞后转向考公",
        "考编": "裸辞后转向考编",
        "裸辞": "裸辞后寻找下一步",
    }.get(choice_action, choice_action)


def display_choice_or_state(choice_action: str) -> str:
    return _choice_sentence(choice_action) if choice_action else "下一步选择"


def _source_excerpt(value: Any) -> str:
    text = re.sub(r"\s+", " ", _text(value)).strip()
    if not text:
        return ""
    if len(text) <= 260:
        return text
    cut = text[:260]
    for mark in ("。", "；", "，"):
        index = cut.rfind(mark, 160)
        if index >= 160:
            return cut[: index + 1]
    return f"{text[:257]}..."


def _slug(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", text).strip("_")[:80]


def _limit(value: str, max_len: int) -> str:
    value = _text(value)
    return value if len(value) <= max_len else f"{value[:max_len]}..."


def _append_unique(values: list[str], value: str) -> None:
    value = _text(value)
    if value and value not in values:
        values.append(value)


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", _text(value))


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
