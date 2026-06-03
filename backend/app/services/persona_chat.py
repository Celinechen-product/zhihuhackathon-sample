from __future__ import annotations

import json
import re

from app.schemas import PersonaChatPerson, PersonaChatRequest, PersonaChatResponse
from app.services.llm_client import LLMClientError, call_llm_json
from app.services.llm_prompts import PERSONA_QA_PROMPT


INSUFFICIENT_PUBLIC_CONTENT_MESSAGE = "这位样本的公开内容不足，暂时不能继续追问。"
MISSING_PUBLIC_INFO_MESSAGE = "TA 的公开内容里没有提到这一点。"
GREETING_MESSAGE = "你好，我可以基于这段公开经历回答你想了解的问题。"


async def answer_persona_chat(payload: PersonaChatRequest) -> PersonaChatResponse:
    person = payload.person
    source_url = _clean(person.source.url)
    public_text = _public_context_text(person)

    if not source_url or len(_compact(public_text)) < 30:
        return PersonaChatResponse(
            answer=INSUFFICIENT_PUBLIC_CONTENT_MESSAGE,
            sourceUrl=source_url,
            insufficientContext=True,
        )

    question = _clean(payload.question)
    if not question:
        return PersonaChatResponse(
            answer="可以继续围绕这段公开经历提问，我会只根据 TA 已经公开写到的内容回答。",
            sourceUrl=source_url,
            insufficientContext=False,
        )
    if _is_greeting_or_generic(question):
        return PersonaChatResponse(
            answer=GREETING_MESSAGE,
            sourceUrl=source_url,
            insufficientContext=False,
        )

    try:
        answer = await _answer_with_llm(payload, public_text)
    except LLMClientError:
        answer = ""

    if not answer:
        answer = _fallback_answer(payload, public_text)

    return PersonaChatResponse(
        answer=_sanitize_answer(answer),
        sourceUrl=source_url,
        insufficientContext=False,
    )


async def _answer_with_llm(payload: PersonaChatRequest, public_text: str) -> str:
    messages = [
        {"role": "system", "content": PERSONA_QA_PROMPT},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "query": payload.query,
                    "question": payload.question,
                    "person": payload.person.dict(),
                    "publicContext": public_text,
                },
                ensure_ascii=False,
            ),
        },
    ]
    result = await call_llm_json(
        messages,
        task="persona_chat",
        temperature=0.15,
    )
    if result.get("insufficientContext"):
        return MISSING_PUBLIC_INFO_MESSAGE
    return _clean(result.get("answer"))


def _fallback_answer(payload: PersonaChatRequest, public_text: str) -> str:
    question = _clean(payload.question)
    person = payload.person

    if _is_greeting_or_generic(question):
        return GREETING_MESSAGE

    if _asks_for_unmentioned_fact(question, public_text):
        return MISSING_PUBLIC_INFO_MESSAGE

    relevant = _relevant_public_points(question, person)
    if not relevant:
        return MISSING_PUBLIC_INFO_MESSAGE

    return f"从 TA 的公开分享看，{_join_sentences(relevant, limit=4)}"


def _public_context_text(person: PersonaChatPerson) -> str:
    parts = [
        person.name,
        person.situation,
        person.actionSummary,
        person.currentStatus,
        person.entrySituation,
        person.entryStatus,
        person.source.title,
        person.source.excerpt,
        *person.realDetails,
        *person.key_fragments,
    ]
    return "\n".join(_clean(part) for part in parts if _clean(part))


def _relevant_public_points(question: str, person: PersonaChatPerson) -> list[str]:
    question_tokens = _keyword_tokens(question)
    candidates = [
        person.situation,
        person.actionSummary,
        person.currentStatus,
        person.entrySituation,
        person.entryStatus,
        person.source.excerpt,
        *person.realDetails,
        *person.key_fragments,
    ]
    cleaned = [_clean(item) for item in candidates if _clean(item)]
    if not question_tokens:
        return cleaned[:3]

    scored: list[tuple[int, int, str]] = []
    for index, item in enumerate(cleaned):
        score = sum(1 for token in question_tokens if token in item)
        if score:
            scored.append((score, -index, item))

    if not scored and re.search(r"压力|难|现实|困难|挑战|问题", question):
        scored = [
            (1, -index, item)
            for index, item in enumerate(cleaned)
            if re.search(r"难|压力|差|面试|找工作|薪资|待业|裸辞|离职|接受|适应", item)
        ]

    if not scored:
        return cleaned[:3]

    return [item for _, _, item in sorted(scored, reverse=True)[:4]]


def _asks_for_unmentioned_fact(question: str, public_text: str) -> bool:
    topic_groups = [
        (r"存款|积蓄|储蓄", r"存款|积蓄|储蓄|攒了|攒下"),
        (r"收入|薪资|工资|月薪|年薪|多少钱|多少(万|块|元)", r"收入|薪资|工资|月薪|年薪|万|元|块|钱"),
        (r"城市|哪里|哪座城|在哪", r"城市|北京|上海|广州|深圳|杭州|成都|郑州|奥克兰|基督城|惠灵顿"),
        (r"父母|家庭|家人|伴侣|对象|结婚|孩子", r"父母|家庭|家人|伴侣|对象|结婚|孩子"),
        (r"后来|最后|现在|后续|结果", r"后来|最后|现在|目前|当前|接受|拿到|开始|已|尚未"),
    ]
    compact_text = _compact(public_text)
    for question_pattern, public_pattern in topic_groups:
        if re.search(question_pattern, question) and not re.search(public_pattern, compact_text):
            return True
    return False


def _keyword_tokens(text: str) -> list[str]:
    tokens = re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]{2,}", text)
    stopwords = {
        "什么",
        "怎么",
        "有没有",
        "是否",
        "可以",
        "时候",
        "当时",
        "后来",
        "公开",
        "内容",
        "提到",
        "这一点",
    }
    return [token for token in tokens if token not in stopwords]


def _is_greeting_or_generic(question: str) -> bool:
    compact = _compact(question)
    if compact in {"你好", "您好", "hi", "hello", "嗨", "在吗", "哈喽"}:
        return True
    return len(compact) <= 6 and re.search(r"你好|您好|嗨|在吗|哈喽|hi|hello", compact, re.IGNORECASE) is not None


def _sanitize_answer(answer: str) -> str:
    cleaned = _clean(answer)
    cleaned = re.sub(r"我是\s*TA[，,。]?", "", cleaned)
    cleaned = cleaned.replace("TA 正在回答你", "这段公开内容显示")
    cleaned = cleaned.replace("TA正在回答你", "这段公开内容显示")
    return cleaned or MISSING_PUBLIC_INFO_MESSAGE


def _join_sentences(items: list[str] | tuple[str, ...], limit: int = 3) -> str:
    cleaned = [_clean(item).rstrip("。；;") for item in items if _clean(item)]
    return "；".join(cleaned[:limit]) + "。"


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", _clean(text))


def _clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()
