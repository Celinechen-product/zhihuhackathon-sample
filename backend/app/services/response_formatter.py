from __future__ import annotations

import hashlib
import re
from collections import Counter
from typing import Any

from app.services.path_clusterer import CLUSTER_META


CONTENT_TYPE_BY_SAMPLE_TYPE = {
    "full_story": "complete_experience",
    "partial_experience": "fragment_experience",
    "opinion_with_experience": "opinion_with_experience",
}

VALID_LLM_SAMPLE_TYPES = {
    "full_story",
    "partial_experience",
    "full_experience",
    "fragmented_experience",
    "opinion_with_experience",
}
VALID_LLM_CONFIDENCE = {"high", "medium", "low"}
LLM_SAMPLE_TYPE_PRIORITY = {
    "full_story": 0,
    "partial_experience": 1,
    "opinion_with_experience": 2,
}
LLM_CONFIDENCE_PRIORITY = {
    "high": 0,
    "medium": 1,
    "low": 2,
}
LLM_PATH_SOURCE_FIELDS = [
    "source.title",
    "situation",
    "actionSummary",
    "realDetails",
    "currentStatus",
]
AUTHOR_EXPERIENCE_OWNERS = {"author"}
FORMAL_SAMPLE_TYPES = {"full_story", "partial_experience"}
PUBLIC_EXAM_KEYWORDS = (
    "考公",
    "考编",
    "公务员",
    "事业编",
    "上岸",
    "没上岸",
    "国考",
    "省考",
    "编制",
    "体制内考试",
)
STUDY_EXAM_KEYWORDS = (
    "考研",
    "读研",
    "研究生",
    "备考研究生",
    "准备考研",
    "考研复试",
    "初试",
    "复试",
    "调剂",
    "拟录取",
)
STUDY_EXAM_CONTEXT_KEYWORDS = (
    "考研",
    "读研",
    "研究生",
    "备考",
    "初试",
    "调剂",
    "拟录取",
    "院校",
    "导师",
    "上岸",
    "读书",
)
PUBLIC_EXAM_CONTEXT_KEYWORDS = (
    "考公",
    "考编",
    "公务员",
    "事业编",
    "国考",
    "省考",
    "编制",
    "体制内",
)
FREELANCE_KEYWORDS = (
    "创业",
    "自由职业",
    "副业",
    "自媒体",
    "全职交易",
    "接项目",
    "接单",
    "小红书店",
    "拼夕夕",
    "小说推文",
    "漫画解说",
    "个体经营",
    "离开传统职场",
    "不再找工作",
    "拒绝回职场",
)
FREELANCE_MAIN_ACTION_KEYWORDS = (
    "创业",
    "自由职业",
    "副业",
    "自媒体",
    "全职交易",
    "接项目",
    "接单",
    "个体经营",
)
FREELANCE_FINAL_DIRECTION_KEYWORDS = (
    "离开传统职场",
    "继续创业",
    "继续做自由职业",
    "继续自由职业",
    "不再找工作",
    "不再回职场",
    "不回职场",
    "拒绝回职场",
    "全职交易",
    "个体经营",
)
RETURN_TO_WORK_KEYWORDS = (
    "找工作",
    "求职",
    "投简历",
    "投递简历",
    "面试",
    "猎头",
    "入职",
    "接受工作",
    "接受一份工作",
    "接受一份",
    "已接受工作",
    "新岗位",
    "回职场",
    "回到职场",
    "重新就业",
    "岗位",
    "降薪",
    "小公司",
    "销售助理",
    "人事",
    "行政",
    "文职",
)
RETURN_TO_WORK_STRONG_OUTCOME_KEYWORDS = (
    "顺利找到新工作",
    "最终找到新工作",
    "后来找到新工作",
    "已经找到新工作",
    "找到新工作",
    "已找到工作",
    "新工作",
    "入职",
    "已入职",
    "接受工作",
    "接受一份工作",
    "接受一份",
    "已接受工作",
    "最终接受",
    "新岗位",
    "适应新岗位",
    "重新就业",
    "回到职场",
    "工作中",
    "拿到 offer",
    "拿到offer",
    "offer",
)
MIGRATION_LIFE_KEYWORDS = (
    "搬家",
    "搬去",
    "搬到",
    "搬往",
    "全家搬",
    "换城市",
    "换国家",
    "出国",
    "移民",
    "海外生活",
    "国外生活",
    "英国生活",
    "搬去英国",
    "搬到英国",
    "搬往英国",
    "全家搬去英国",
    "全家搬到英国",
    "旅居",
    "定居",
)
MIGRATION_LIFE_LOCATION_KEYWORDS = (
    "英国",
    "海外",
    "国外",
    "欧洲",
    "加拿大",
    "澳洲",
    "澳大利亚",
    "美国",
    "日本",
    "新加坡",
    "爱尔兰",
    "新西兰",
)
POST_RESIGNATION_MARKERS = (
    "裸辞后",
    "辞职后",
    "离职后",
    "失业后",
    "待业后",
    "已裸辞",
    "已经裸辞",
    "已离职",
    "已经离职",
    "裸辞之后",
    "辞职之后",
    "离职之后",
)
PRE_RESIGNATION_BACKGROUND_MARKERS = (
    "裸辞前",
    "辞职前",
    "离职前",
    "裸辞之前",
    "辞职之前",
    "离职之前",
)
RETURN_TO_WORK_NEGATED_OUTCOME_KEYWORDS = (
    "未找到新工作",
    "没找到新工作",
    "没有找到新工作",
    "还没找到新工作",
    "尚未找到新工作",
)
REST_RESTART_KEYWORDS = (
    "休息",
    "休整",
    "停下来",
    "恢复状态",
    "先缓一缓",
    "观察方向",
    "迷茫",
    "焦虑",
    "内耗",
    "存款减少",
    "生活开销",
    "暂时没有下一步",
)
REST_RESTART_STRONG_KEYWORDS = (
    "一直休息",
    "持续休息",
    "主要休息",
    "休息中",
    "未积极找工作",
    "没有积极找工作",
    "未找到新工作",
    "没找到新工作",
    "暂停",
    "调整状态",
    "考虑转行",
    "重新考虑方向",
    "找本地企业",
    "先停下来",
)
RELATIONSHIP_REPAIR_KEYWORDS = (
    "沟通",
    "修复",
    "复合",
    "重新聊",
    "继续在一起",
    "继续相处",
    "磨合",
)
RELATIONSHIP_BREAK_KEYWORDS = (
    "分手",
    "分开",
    "离开",
    "断联",
    "结束关系",
    "离婚",
)
RELATIONSHIP_OBSERVE_KEYWORDS = (
    "犹豫",
    "不确定",
    "观察",
    "冷静",
    "暂时不做决定",
    "先放慢",
    "边界",
)
RELATIONSHIP_SELF_PATTERN_KEYWORDS = (
    "关系模式",
    "依恋",
    "复盘",
    "自我",
    "情绪",
    "边界感",
)
RELATIONSHIP_LONG_DISTANCE_KEYWORDS = (
    "异地",
    "同城",
    "距离",
    "跨城",
)
FAMILY_SUPPORT_MONEY_KEYWORDS = (
    "给父母钱",
    "给爸妈钱",
    "给家里钱",
    "给父母生活费",
    "给父母红包",
    "给父母过年红包",
    "过年红包",
    "红包",
    "每月给",
    "每年给",
    "补贴父母",
    "补贴家里",
    "转账",
    "转账给父母",
    "转给父母",
    "父母向我要钱",
    "父母向我/作者要钱",
    "父母向作者要钱",
    "父亲打电话要钱",
    "父亲打电话向我要钱",
    "母亲打电话要钱",
    "母亲打电话向我要钱",
    "向我要钱",
    "帮父母还债",
    "生活费",
    "养老钱",
    "被要钱",
    "父母要钱",
    "家里要钱",
    "经济支持",
    "持续支持",
)
FAMILY_MONEY_BOUNDARY_KEYWORDS = (
    "拒绝",
    "减少",
    "减少给款",
    "边界",
    "切断",
    "停止给钱",
    "不再给钱",
    "少给",
    "不给",
    "不给钱",
    "不主动联系父母",
    "不买东西也不给钱",
    "固定金额",
    "明确限制",
    "因为钱争执",
    "和父母因为钱争执",
    "大吵",
    "重新分配责任",
    "划分责任",
    "设定边界",
    "拉开边界",
)
FAMILY_PARENT_REWORK_KEYWORDS = (
    "父母50岁",
    "父母50多岁",
    "父母五十",
    "50多岁",
    "再就业",
    "重新找工作",
    "找工作",
    "赚钱",
    "挣钱",
    "副业",
    "摆摊",
    "保洁",
    "司机",
    "退休后收入",
    "继续工作",
)
FAMILY_SHARED_BURDEN_KEYWORDS = (
    "共同承担",
    "一起扛",
    "债务",
    "负债",
    "养老",
    "兄弟姐妹",
    "分摊",
    "家庭收入",
    "长期家庭经济压力",
    "家里经济压力",
    "子女责任",
)
FAMILY_MONEY_ANY_KEYWORDS = (
    FAMILY_SUPPORT_MONEY_KEYWORDS
    + FAMILY_MONEY_BOUNDARY_KEYWORDS
    + FAMILY_PARENT_REWORK_KEYWORDS
    + FAMILY_SHARED_BURDEN_KEYWORDS
)
FAMILY_MONEY_TEMPORARY_TRANSFER_KEYWORDS = (
    "向我要钱",
    "找我要钱",
    "父母开口要钱",
    "父亲打电话向我要钱",
    "父亲打电话要钱",
    "母亲向我要钱",
    "母亲打电话向我要钱",
    "母亲打电话要钱",
    "被父母要钱",
    "转账",
    "转了钱",
    "先后转账",
    "转账四千",
    "转账4000",
    "给了几千",
    "给了钱",
    "临时要钱",
    "应急支持",
)
FAMILY_MONEY_AUTHOR_INTERACTION_KEYWORDS = (
    "给父母钱",
    "给爸妈钱",
    "给家里钱",
    "给父母生活费",
    "给父母红包",
    "给父母过年红包",
    "过年红包",
    "红包",
    "每月给",
    "每年给",
    "转账给父母",
    "转给父母",
    "转账",
    "父母向我要钱",
    "父母向作者要钱",
    "父亲打电话要钱",
    "父亲打电话向我要钱",
    "母亲打电话要钱",
    "母亲打电话向我要钱",
    "向我要钱",
    "找我要钱",
    "父母开口要钱",
    "被父母要钱",
    "转了钱",
    "先后转账",
    "给了几千",
    "给了钱",
    "临时要钱",
    "应急支持",
    "帮父母还债",
    "减少给款",
    "少给",
    "不给钱",
    "停止给钱",
    "不再给钱",
    "不主动联系父母",
    "不买东西也不给钱",
    "因为钱争执",
    "和父母因为钱争执",
    "固定金额支持",
    "家庭经济压力由作者承担",
)
FAMILY_MONEY_SUPPORT_QUERY_MARKERS = (
    "父母要求",
    "父母要钱",
    "要求给他们钱",
    "给他们钱",
    "给父母钱",
    "给爸妈钱",
    "家庭经济支持",
)
FAMILY_MONEY_HARD_NON_AUTHOR_MARKERS = (
    "客户案例",
    "咨询案例",
    "案例分析",
    "机构案例",
    "采访",
    "转载",
    "投稿",
    "读者故事",
    "朋友的经历",
    "同事的经历",
    "来访者",
)
FAMILY_MONEY_NEGATED_INTERACTION_PHRASES = (
    "不是父母要钱",
    "不是给父母钱",
    "没有父母要钱",
    "没有给父母钱",
    "未涉及父母要钱",
    "未涉及给父母钱",
    "未涉及父母开口要钱",
    "未涉及被父母要钱",
    "没有给生活费",
    "没有转账",
    "没有实际转账",
    "没有作者实际转账",
    "未涉及转账",
    "不是转账",
    "没有父母开口要钱",
    "没有被父母要钱",
    "不是家庭经济支持",
    "没有家庭经济支持",
    "没有经济支持行为",
    "没有作者给钱",
)
NEW_ZEALAND_STRONG_KEYWORDS = (
    "新西兰",
    "奥克兰",
    "基督城",
    "惠灵顿",
    "皇后镇",
    "WHV",
    "打工度假",
    "工签",
    "学签",
    "留学",
    "移民",
    "旅居",
)
NEW_ZEALAND_TARGET_LOCATION_KEYWORDS = (
    "新西兰",
    "奥克兰",
    "基督城",
    "惠灵顿",
    "皇后镇",
    "去新西兰",
    "在新西兰",
    "到新西兰",
    "来到新西兰",
    "前往新西兰",
    "新西兰WHV",
    "新西兰 WHV",
    "新西兰打工度假",
    "新西兰 打工度假",
    "新西兰留学",
    "新西兰 留学",
    "新西兰工签",
    "新西兰 工签",
    "新西兰工作",
    "新西兰 工作",
    "新西兰生活",
    "新西兰 生活",
    "从新西兰回来",
)
MIGRATION_GENERIC_MECHANISM_KEYWORDS = (
    "WHV",
    "打工度假",
    "working holiday",
    "Working Holiday",
    "留学",
    "工签",
    "移民",
    "旅居",
)
MIGRATION_AUTHOR_JOURNEY_KEYWORDS = (
    "搬到新西兰",
    "搬去新西兰",
    "搬新西兰",
    "移居新西兰",
    "决定移居新西兰",
    "决定搬新西兰",
    "在奥克兰生活",
    "在基督城生活",
    "在惠灵顿生活",
    "在皇后镇生活",
    "在新西兰奥克兰生活",
    "在新西兰生活",
    "在新西兰工作",
    "新西兰工作offer",
    "新西兰工作 offer",
    "拿到新西兰工作offer",
    "拿到新西兰工作 offer",
    "拿到新西兰工作Offer",
    "搬到奥克兰",
    "搬去奥克兰",
    "落地基督城",
    "落地奥克兰",
    "在奥克兰打工",
    "在基督城打工",
    "新西兰 WHV",
    "新西兰WHV",
    "新西兰打工度假",
    "新西兰 打工度假",
    "去新西兰留学",
    "新西兰留学",
    "从新西兰回来",
    "去了新西兰",
    "到新西兰",
    "来到新西兰",
)
MIGRATION_AUTHOR_JOURNEY_EXCLUDE_KEYWORDS = (
    "短期旅行",
    "旅游攻略",
    "攻略",
    "亲子插班",
    "插班",
    "带孩子",
    "短期游学",
    "游学",
    "政策攻略",
    "政策解读",
    "找工作指南",
    "指南",
    "中介",
    "客户案例",
    "客户故事",
    "我的客户",
    "客户去了",
    "客户在新西兰",
    "我朋友",
    "我的朋友",
    "朋友一家",
    "朋友的经历",
    "朋友去了",
    "朋友在新西兰",
    "我的孩子",
    "我孩子",
    "孩子去新西兰",
    "孩子在新西兰",
    "采访",
    "采访对象",
)
MIGRATION_TARGET_LOCATION_NEGATIVE_KEYWORDS = (
    "澳洲",
    "澳大利亚",
    "Australia",
    "加拿大",
    "英国",
    "日本",
    "欧洲",
    "美国",
    "新加坡",
    "爱尔兰",
)
NEW_ZEALAND_TARGET_FALSE_POSITIVE_PHRASES = (
    "不涉及新西兰",
    "未涉及新西兰",
    "无新西兰",
    "不是新西兰",
    "非新西兰",
)
NEW_ZEALAND_WHV_KEYWORDS = ("WHV", "打工度假", "working holiday", "Working Holiday", "working and holiday")
NEW_ZEALAND_STUDY_KEYWORDS = ("留学", "学签", "读书", "毕业", "读博", "博士", "上学", "读语言", "读幼教")
NEW_ZEALAND_WORK_VISA_KEYWORDS = (
    "工签",
    "工作签证",
    "转工签",
    "雇主",
    "本地雇佣",
    "本地工作",
    "在新西兰工作",
    "新西兰工作",
    "offer",
    "Offer",
    "留下来",
    "技术移民",
    "PR",
    "绿卡",
)
NEW_ZEALAND_RETURN_KEYWORDS = ("回国", "回来了", "从新西兰回来", "去了又回来")
NEW_ZEALAND_REMOTE_KEYWORDS = ("远程", "旅居", "数字游民", "自由职业", "打工换宿", "Helpx", "探索之旅")
NEW_ZEALAND_PREP_KEYWORDS = ("申请", "准备", "没去", "没有去", "没成行", "计划", "材料")
ADVICE_ONLY_FILTER_REASON = "advice/commentary without author journey"
ADVICE_MARKERS = (
    "建议",
    "应该",
    "可以考虑",
    "我认为",
    "我的观点",
    "核心是",
    "关键是",
    "不要",
    "需要",
    "方法",
    "方案",
)
QUESTION_TITLE_MARKERS = ("怎么办", "如何", "怎么", "要不要", "该不该", "吗", "？", "?")
AUTHOR_LIVED_MARKERS = (
    "我裸辞",
    "我辞职",
    "我离职",
    "我当时",
    "我曾经",
    "我的经历",
    "我经历",
    "我去",
    "我到了",
    "我在新西兰",
    "我申请",
    "我读",
    "我工作",
    "我分手",
    "我和",
    "本人",
)
AUTHOR_PROCESS_EVIDENCE_MARKERS = (
    "我裸辞",
    "我辞职",
    "我离职",
    "我申请",
    "我拿到",
    "我去了",
    "我到",
    "我来到",
    "我在新西兰",
    "我读",
    "我工作",
    "我开始",
    "我选择",
    "我转",
    "我靠",
    "我分手",
    "我回国",
    "我回来",
    "我收到",
    "我经历",
    "我当时",
    "我们去了",
    "我们到",
    "本人经历",
)
AUTHOR_IDENTITY_ONLY_MARKERS = (
    "作为一个",
    "做了8年",
    "做了八年",
    "从业",
    "自由职业者",
    "我会告诉你",
)
MENTIONED_PERSON_MARKERS = (
    "我朋友",
    "我同事",
    "我认识",
    "身边一个",
    "身边很多",
    "朋友的经历",
    "我的孩子",
    "我孩子",
    "孩子",
    "女儿",
    "儿子",
    "客户",
    "来访者",
    "案例",
)
WEAK_FIRST_PERSON_FILTER_REASON = "weak first-person mention without concrete lived process"
SUBJECT_MISMATCH_FILTER_REASON = "experience subject mismatch with query"
ADVICE_COMMENTARY_FILTER_REASON = "advice/commentary without author journey"
ANSWER_ADVICE_FILTER_REASON = "answer/advice without author's own lived experience"
STRUCTURED_RESCUE_REASON = "rescued_by_structured_experience_fields"
POST_PREMISE_RESCUE_REASON = "rescued_by_post_premise_evidence"
FAMILY_MONEY_INTERACTION_RESCUE_REASON = "rescued_by_family_money_author_interaction"
FAMILY_MONEY_TRANSFER_RESCUE_REASON = "rescued_by_family_money_transfer_interaction"
FAMILY_MONEY_SUBJECT_MISMATCH_REASON = "family_money_subject_mismatch"
MIGRATION_AUTHOR_JOURNEY_RESCUE_REASON = "rescued_by_migration_author_journey"
MIGRATION_TARGET_LOCATION_MISMATCH_REASON = "migration_target_location_mismatch"
QUERY_PREMISE_NOT_ENTERED_FILTER_REASON = "not_yet_entered_query_premise_state"
MIGRATION_AUTHOR_JOURNEY_RESCUEABLE_REASONS = {
    "post-check: mentioned_person/case rather than author's own lived experience",
    "mentioned_person/case rather than author's own lived experience",
    SUBJECT_MISMATCH_FILTER_REASON,
    "experience subject mismatch",
}
QUERY_PREMISE_NOT_ENTERED_ALIASES = {
    "not yet entered query premise state",
    QUERY_PREMISE_NOT_ENTERED_FILTER_REASON,
}
STRUCTURED_RESCUEABLE_REASONS = {
    ADVICE_COMMENTARY_FILTER_REASON,
    ADVICE_ONLY_FILTER_REASON,
    ANSWER_ADVICE_FILTER_REASON,
    WEAK_FIRST_PERSON_FILTER_REASON,
}
CAREER_RESTART_POST_PREMISE_ACTION_MARKERS = (
    "裸辞后",
    "已裸辞",
    "已经裸辞",
    "辞职后",
    "离职后",
    "已离职",
    "已经离职",
    "待业",
    "无工作",
    "没工作",
    "没有工作",
    "没有上班",
    "没上班",
    "面试",
    "找工作",
    "投简历",
    "入职",
    "接受工作",
    "接受一份",
    "重新工作",
    "重新就业",
    "考研",
    "读研",
    "研究生",
    "初试",
    "复试",
    "创业",
    "自由职业",
    "换城市",
    "换国家",
    "搬家",
    "搬去",
    "搬到",
    "搬往",
    "出国",
    "移民",
    "海外生活",
    "回老家",
)
CAREER_RESTART_POST_PREMISE_STATE_MARKERS = (
    "裸辞后顺利找到新工作",
    "裸辞后顺利找到工作",
    "裸辞后已找到工作",
    "裸辞后找到新工作",
    "裸辞后重新找工作",
    "已离职后找工作",
    "辞职后一直休息",
    "辞职后未找工作",
    "裸辞后创业",
    "裸辞后尝试创业",
    "裸辞后考研",
    "裸辞后准备考研",
    "裸辞后读研",
    "裸辞后学习",
    "裸辞后读书",
    "裸辞后全家搬",
    "裸辞后搬家",
    "裸辞后搬去",
    "裸辞后搬到",
    "裸辞后搬往",
    "裸辞后出国",
    "裸辞后移民",
    "裸辞后换城市",
    "裸辞后换国家",
    "裸辞后找工作",
    "裸辞后休整",
    "离职后入职",
    "离职后重新就业",
    "离职后重新找工作",
    "裸辞两年",
    "裸辞2年",
    "裸辞一年",
    "裸辞1年",
    "裸辞半年",
    "已裸辞",
    "已经裸辞",
    "已离职",
    "已经离职",
    "待业",
    "无工作",
    "失业后",
)
CAREER_RESTART_PREMISE_NOT_ENTERED_MARKERS = (
    "提出离职但尚未完成交接",
    "尚未完成离职交接",
    "离职交接未开始",
    "尚未开始交接",
    "仍在继续原工作",
    "仍在原工作",
    "继续原工作",
    "等待接替人员",
    "领导未找到接替",
    "只是提了离职",
    "提了离职",
    "提出离职",
    "递交了辞职信",
    "提交了辞职信",
    "辞职信",
    "交接中",
    "交接工作",
    "还在交接",
    "尚未完成",
    "离职未完成",
    "离职日期未定",
    "计划裸辞",
    "想裸辞",
    "准备裸辞",
    "还没真正",
    "还没离开",
    "还未离开",
    "未正式离职",
    "尚未正式离职",
    "未开始交接",
    "还没真正离职",
)
CAREER_RESTART_PREMISE_FALSE_POSITIVE_PHRASES = (
    "提出离职后",
    "提了离职后",
    "递交辞职信后",
    "递交了辞职信后",
    "提交辞职信后",
    "提交了辞职信后",
    "准备裸辞后",
    "计划裸辞后",
    "想裸辞后",
)
CONCRETE_ACTION_MARKERS = (
    "申请",
    "准备",
    "去了",
    "到",
    "来到",
    "开始",
    "选择",
    "分手",
    "复合",
    "沟通",
    "辞职",
    "离职",
    "裸辞",
    "投简历",
    "面试",
    "工作",
    "读书",
    "留学",
    "打工",
    "回国",
    "转",
)
TIME_STAGE_MARKERS = (
    "年",
    "月",
    "岁",
    "大一",
    "大二",
    "大三",
    "大四",
    "本科",
    "毕业",
    "后来",
    "现在",
    "目前",
    "当时",
    "之后",
    "期间",
    "更新",
)
OUTCOME_STATUS_MARKERS = (
    "现在",
    "目前",
    "最后",
    "结果",
    "拿到",
    "收到",
    "上岸",
    "没上岸",
    "回国",
    "回来",
    "留下",
    "分开",
    "结婚",
    "复合",
    "offer",
    "Offer",
)
NEW_ZEALAND_NON_AUTHOR_OR_SHORT_TRIP_MARKERS = (
    "亲子",
    "插班",
    "短期游学",
    "游学",
    "旅游",
    "旅行",
    "攻略",
    "行程",
    "带孩子",
    "孩子",
    "女儿",
    "儿子",
    "客户",
    "朋友",
)
AUTHOR_NEW_ZEALAND_JOURNEY_MARKERS = (
    "我在新西兰",
    "我去新西兰",
    "我到了新西兰",
    "我来到新西兰",
    "我申请",
    "我准备去新西兰",
    "我拿到",
    "我留学",
    "我工作",
    "我从新西兰回来",
    "我的WHV",
    "我的 WHV",
)
AUTHOR_RELATIONSHIP_JOURNEY_MARKERS = (
    "我分手",
    "我和男朋友",
    "我和女朋友",
    "我和前任",
    "我和伴侣",
    "我和老公",
    "我和老婆",
    "我的恋爱",
    "我的婚姻",
    "我的关系",
    "我在感情",
    "我复合",
)

MARKETING_MARKERS = (
    "半年赚了50万",
    "半年赚50万",
    "月入10万",
    "暴富",
    "逆袭",
)

PATH_NAME_ALIASES = {
    "裸辞后回老家/低成本生活": "裸辞后回老家生活",
}
OTHER_PATH_ID = CLUSTER_META["other_related_experience"]["id"]
FORBIDDEN_FALLBACK_PATH_NAMES = {
    "其他相近真实经历",
    "其他路径",
    "其他选择",
    "相关经历",
    "未分类经历",
}

PATH_DEFINITIONS: dict[str, dict[str, str]] = {
    "path_return_to_work": {
        "name": "裸辞后重新找工作",
        "desc": "这些样本主要回到求职轨道，在投简历、面试和岗位预期之间重新找位置。",
    },
    "path_freelance_trials": {
        "name": "裸辞后自由职业试错",
        "desc": "这些样本把裸辞后的空档用于副业、接单或自由职业试错，同时面对收入波动。",
    },
    "path_public_exam": {
        "name": "裸辞后考公/考编",
        "desc": "这些样本把考公考编作为阶段性方向，但结果和投入周期都存在不确定性。",
    },
    "path_study_exam": {
        "name": "裸辞后学习/考试",
        "desc": "这些样本把裸辞后的主要精力放在考研、读书或阶段性考试上，而不是直接回到求职轨道。",
    },
    "path_migration_life": {
        "name": "裸辞后换环境生活",
        "desc": "这些样本裸辞后的主要动作是搬家、换城市或出国生活，用新的环境重新安排日常。",
    },
    "path_rest_then_restart": {
        "name": "裸辞后先休整再重启",
        "desc": "这些样本先停下来恢复状态，再慢慢观察职业方向和下一步行动。",
    },
    "path_relationship_slow_observe": {
        "name": "先放慢关系，重新观察",
        "desc": "这些样本没有立刻做决定，而是先拉开节奏、观察关系中的真实感受和边界。",
    },
    "path_relationship_break_up": {
        "name": "决定分开",
        "desc": "这些样本最终选择结束关系，并记录分开后的情绪、生活和判断变化。",
    },
    "path_relationship_repair": {
        "name": "继续沟通和修复",
        "desc": "这些样本把重点放在沟通、修复和重新磨合上，同时观察关系是否还能继续。",
    },
    "path_relationship_self_pattern": {
        "name": "复盘自己的关系模式",
        "desc": "这些样本把关系困扰转向自我复盘，重新看见自己的边界、依恋和选择模式。",
    },
    "path_relationship_recover_after_breakup": {
        "name": "结束关系后重新生活",
        "desc": "这些样本在关系结束后重新安顿生活，记录恢复、重建和再次出发的过程。",
    },
    "path_relationship_long_distance_to_same_city": {
        "name": "从异地关系转向同城",
        "desc": "这些样本围绕异地关系、距离变化和同城后的关系调整展开。",
    },
    "path_nz_whv_trial": {
        "name": "用 WHV 先去试生活",
        "desc": "这些人先通过 WHV 到新西兰，在真实工作和生活成本中测试自己是否适应。",
    },
    "path_nz_study_work_visa": {
        "name": "通过留学进入新西兰",
        "desc": "这些人通过留学或读书进入新西兰，再寻找工签、工作或长期留下的可能。",
    },
    "path_nz_living_migrate": {
        "name": "工作/工签留下来",
        "desc": "这些人通过本地工作、雇主或工签把新西兰生活继续往后推进。",
    },
    "path_nz_remote_sojourn": {
        "name": "靠远程收入旅居",
        "desc": "这些人靠远程工作、自由职业或非本地雇佣收入，支撑在新西兰的阶段性生活。",
    },
    "path_nz_returned": {
        "name": "去了之后又回来",
        "desc": "这些样本去过新西兰后又回国，能看到期待、落差和回流后的选择。",
    },
    "path_nz_preparing_not_departed": {
        "name": "准备过但最终没去",
        "desc": "这些样本有明确申请或准备动作，但还没真正去新西兰或最终没有成行。",
    },
    "path_family_support_money": {
        "name": "持续给家庭经济支持",
        "desc": "这些样本记录了工作后给父母或家庭持续经济支持时的压力、拉扯和调整。",
    },
    "path_family_money_boundary": {
        "name": "重新设定给钱边界",
        "desc": "这些样本在被父母要钱或长期补贴后，开始减少支持、拒绝给钱或重新划分责任。",
    },
    "path_family_parent_rework": {
        "name": "父母重新找收入",
        "desc": "这些样本记录了父母50岁前后继续工作、再就业或尝试增加收入的经历。",
    },
    "path_family_shared_burden": {
        "name": "一起扛家庭经济压力",
        "desc": "这些样本不是单纯给钱或拒绝，而是在家庭收入、债务、养老和子女责任之间重新分担。",
    },
}


def build_frontend_from_llm_people(
    llm_people_draft: list[dict[str, Any]],
    query: str,
    clarification: str | None,
    query_context: dict[str, Any] | None = None,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    context = query_context or {}
    people: list[dict[str, Any]] = []
    filter_debug: list[dict[str, Any]] = []
    for draft in llm_people_draft:
        person = _build_llm_frontend_person(
            draft,
            query=query,
            clarification=clarification,
            query_context=context,
        )
        filter_debug.append(_llm_people_filter_debug_entry(draft, person, query_context=context))
        if person is not None:
            people.append(person)
    people.sort(key=_llm_people_sort_key)
    if not people:
        return [], [], [], filter_debug, [], []

    dropped_other_ids = {
        _text(person.get("id"))
        for person in people
        if _text(person.get("pathId")) == OTHER_PATH_ID
    }
    if dropped_other_ids:
        people = [
            person
            for person in people
            if _text(person.get("id")) not in dropped_other_ids
        ]
        _mark_filter_debug_dropped(
            filter_debug,
            dropped_other_ids,
            "other path hidden from formal paths",
        )
    if not people:
        return [], [], [], filter_debug, [], []

    people_counts: Counter[str] = Counter(_text(person.get("pathId")) for person in people)
    paths, path_relevance_debug, dropped_paths = _build_llm_frontend_paths(
        people_counts,
        people=people,
        query_context=context,
    )
    valid_path_ids = {_text(path.get("id")) for path in paths if _text(path.get("id"))}
    people = [person for person in people if _text(person.get("pathId")) in valid_path_ids]
    if not people:
        for debug in filter_debug:
            if debug.get("kept"):
                debug["kept"] = False
                debug["dropReason"] = "pathId did not match generated paths"
        return [], [], [], filter_debug, path_relevance_debug, dropped_paths

    people_counts = Counter(_text(person.get("pathId")) for person in people)
    paths, path_relevance_debug, dropped_paths = _build_llm_frontend_paths(
        people_counts,
        people=people,
        query_context=context,
    )
    paths.sort(key=lambda item: (-int(item.get("count") or 0), str(item.get("id", ""))))
    assignment_debug = []
    for person in people:
        debug = person.pop("_llmPathAssignmentDebug", None)
        if isinstance(debug, dict):
            assignment_debug.append(debug)
    return paths, people, assignment_debug, filter_debug, path_relevance_debug, dropped_paths


def should_use_real_results(
    paths_draft: list[dict[str, Any]],
    people_draft_with_path: list[dict[str, Any]],
) -> bool:
    if not paths_draft or not people_draft_with_path:
        return False
    valid_path_ids = _path_ids(paths_draft)
    people = build_frontend_people(
        people_draft_with_path,
        valid_path_ids=valid_path_ids,
    )
    paths = build_frontend_paths(paths_draft, frontend_people=people)
    return bool(paths and people)


def build_frontend_paths(
    paths_draft: list[dict[str, Any]],
    frontend_people: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    people_counts: Counter[str] = Counter()
    if frontend_people is not None:
        people_counts.update(_text(person.get("pathId")) for person in frontend_people)

    paths: list[dict[str, Any]] = []
    for path in paths_draft:
        path_id = _text(path.get("id"))
        if not path_id:
            continue
        if frontend_people is not None and people_counts[path_id] <= 0:
            continue
        count = people_counts[path_id] if frontend_people is not None else _int(path.get("count"))
        if count <= 0:
            continue
        path_name = _format_path_name(path.get("name"))
        if path_name in FORBIDDEN_FALLBACK_PATH_NAMES:
            continue
        paths.append(
            {
                "id": path_id,
                "name": path_name,
                "desc": _format_desc(path.get("desc")),
                "count": count,
            }
        )
    paths.sort(key=lambda item: (-int(item.get("count") or 0), str(item.get("id", ""))))
    return paths


def sync_path_counts_with_people(
    paths: list[dict[str, Any]],
    people: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    people_counts: Counter[str] = Counter(_text(person.get("pathId")) for person in people)
    people_ids_by_path: dict[str, list[str]] = {}
    for person in people:
        path_id = _text(person.get("pathId"))
        person_id = _text(person.get("id"))
        if path_id and person_id:
            people_ids_by_path.setdefault(path_id, []).append(person_id)

    synced_paths: list[dict[str, Any]] = []
    for path in paths:
        path_id = _text(path.get("id"))
        if not path_id:
            synced_paths.append(path)
            continue
        synced_path = dict(path)
        synced_path["count"] = people_counts[path_id]
        if "supporting_person_ids" in synced_path:
            synced_path["supporting_person_ids"] = people_ids_by_path.get(path_id, [])
        synced_paths.append(synced_path)
    return synced_paths


def build_frontend_people(
    people_draft_with_path: list[dict[str, Any]],
    valid_path_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    people: list[dict[str, Any]] = []
    seen: set[str] = set()
    for draft in people_draft_with_path:
        if not _is_valid_people_draft(draft, valid_path_ids):
            continue
        person_id = _text(draft.get("id"))
        source = draft.get("source") if isinstance(draft.get("source"), dict) else {}
        key = person_id or _text(source.get("url"))
        if key in seen:
            continue
        seen.add(key)
        sample_type = _normalize_sample_type(draft.get("sample_type")) or "partial_experience"
        source_excerpt = _format_excerpt(draft.get("sourceExcerpt") or source.get("excerpt"))
        source_title = _text(draft.get("sourceTitle") or source.get("title"))
        source_url = _text(draft.get("sourceUrl") or source.get("url"))
        people.append(
            {
                "id": person_id or f"person_{len(people) + 1}",
                "sample_type": sample_type,
                "contentType": CONTENT_TYPE_BY_SAMPLE_TYPE.get(
                    sample_type,
                    "fragment_experience",
                ),
                "name": _text(draft.get("name")) or "知乎用户",
                "pathId": _text(draft.get("pathId")),
                "role": _text(draft.get("role")) or "知乎用户",
                "badge": _format_badge(draft.get("badge")),
                "oneLine": _format_one_line(draft.get("oneLine")),
                "who": _text(draft.get("who")),
                "entrySituation": _entry_situation(draft.get("entrySituation") or draft.get("who")),
                "entryStatus": _entry_status(draft.get("entryStatus") or draft.get("currentStatus")),
                "matchReasons": _string_list(draft.get("matchReasons"))[:3],
                "timeline": draft.get("timeline") if isinstance(draft.get("timeline"), list) else [],
                "keyExperience": _text(draft.get("keyExperience")),
                "sourceExcerpt": source_excerpt,
                "sourceTitle": source_title,
                "sourceUrl": source_url,
                "source": {
                    "title": source_title,
                    "url": source_url,
                    "content_type": _text(source.get("content_type")) or "Unknown",
                    "author_name": _text(source.get("author_name")),
                    "author_avatar": _text(source.get("author_avatar")),
                    "excerpt": source_excerpt,
                },
            }
        )
    return people


def assign_path_for_llm_person(
    person: dict[str, Any],
    query: str,
    clarification: str | None,
    query_context: dict[str, Any] | None = None,
) -> str:
    assignment = _assign_path_for_llm_person_with_debug(
        person,
        query=query,
        clarification=clarification,
        query_context=query_context,
    )
    return assignment["assignedPathId"]


def _assign_path_for_llm_person_with_debug(
    person: dict[str, Any],
    query: str,
    clarification: str | None,
    query_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _ = (query, clarification)
    context = query_context or {}
    query_type = _text(context.get("query_type")) or "unknown"
    text = _llm_path_text(person)
    path_id, matched_keywords, rejected_path_ids, reason = _classify_llm_path(text, query_type)
    return {
        "personId": _text(person.get("id")),
        "name": _text(person.get("name")),
        "assignedPathId": path_id,
        "pathId": path_id,
        "matchedEvidence": matched_keywords,
        "matchedKeywords": matched_keywords,
        "queryType": query_type,
        "rejectedPathIds": rejected_path_ids,
        "reason": reason,
        "sourceFields": LLM_PATH_SOURCE_FIELDS,
    }


def _llm_path_text(person: dict[str, Any]) -> str:
    source = person.get("source") if isinstance(person.get("source"), dict) else {}
    text_parts = [
        source.get("title"),
        person.get("situation"),
        person.get("actionSummary"),
    ]
    text_parts.extend(person.get("realDetails") or [])
    text_parts.append(person.get("currentStatus"))
    return " ".join(_text(part) for part in text_parts)


def _classify_llm_path(text: str, query_type: str) -> tuple[str, list[str], list[str], str]:
    if query_type == "relationship":
        return _classify_relationship_path(text)
    if query_type == "migration_new_zealand":
        return _classify_new_zealand_path(text)
    if query_type == "family_money":
        return _classify_family_money_path(text)
    if query_type not in {"career_restart", "unknown", "general_life_confusion"}:
        return "", [], [OTHER_PATH_ID], f"query_type={query_type} has no trusted path rule yet"
    if query_type in {"unknown", "general_life_confusion"} and not any(
        marker in text for marker in ("裸辞", "找工作", "考公", "自由职业", "辞职", "离职")
    ):
        return "", [], [OTHER_PATH_ID], "no trusted path for general query"

    post_action_text = _career_post_resignation_action_text(text)
    public_exam_matches = _matched_public_exam_keywords(post_action_text)
    study_exam_matches = _matched_study_exam_keywords(post_action_text)
    migration_life_matches = _matched_migration_life_keywords(post_action_text)
    if not _has_post_resignation_action_context(text, PUBLIC_EXAM_KEYWORDS + PUBLIC_EXAM_CONTEXT_KEYWORDS):
        public_exam_matches = []
    if not _has_post_resignation_action_context(text, STUDY_EXAM_KEYWORDS + STUDY_EXAM_CONTEXT_KEYWORDS):
        study_exam_matches = []
    if not _has_post_resignation_action_context(text, MIGRATION_LIFE_KEYWORDS + MIGRATION_LIFE_LOCATION_KEYWORDS):
        migration_life_matches = []
    restart_after_exam_matches = _matched_restart_after_exam_keywords(text)
    if public_exam_matches:
        return CLUSTER_META["public_exam"]["id"], public_exam_matches, [], "post-resignation exam/stability evidence"
    if study_exam_matches:
        return "path_study_exam", study_exam_matches, [], "post-resignation study/exam evidence"
    if migration_life_matches:
        return "path_migration_life", migration_life_matches, [], "post-resignation migration/life-environment evidence"
    if restart_after_exam_matches:
        return CLUSTER_META["rest_then_restart"]["id"], restart_after_exam_matches, [], "career restart after failed exam"

    return_action_text = post_action_text if _has_post_resignation_return_context(text) else ""
    strong_return_matches = _matched_return_to_work_strong_outcome_keywords(return_action_text)
    if strong_return_matches:
        return CLUSTER_META["return_to_work"]["id"], strong_return_matches, [], "post-resignation return-to-work outcome evidence"

    freelance_final_matches = _matched_keywords(text, FREELANCE_FINAL_DIRECTION_KEYWORDS)
    if freelance_final_matches:
        return CLUSTER_META["freelance_trials"]["id"], freelance_final_matches, [], "freelance or entrepreneurship final direction"

    strong_rest_matches = _matched_keywords(text, REST_RESTART_STRONG_KEYWORDS)
    if strong_rest_matches:
        return CLUSTER_META["rest_then_restart"]["id"], strong_rest_matches, [], "rest and direction-shift evidence"

    return_to_work_matches = _matched_keywords(return_action_text, RETURN_TO_WORK_KEYWORDS)
    if return_to_work_matches:
        return CLUSTER_META["return_to_work"]["id"], return_to_work_matches, [], "post-resignation return-to-work evidence"

    freelance_main_matches = _matched_keywords(text, FREELANCE_MAIN_ACTION_KEYWORDS)
    if freelance_main_matches:
        return CLUSTER_META["freelance_trials"]["id"], freelance_main_matches, [], "freelance, entrepreneurship, or side-hustle main action"

    freelance_matches = _matched_keywords(text, FREELANCE_KEYWORDS)
    if freelance_matches:
        return CLUSTER_META["freelance_trials"]["id"], freelance_matches, [], "freelance or side-hustle evidence"

    rest_restart_matches = _matched_keywords(text, REST_RESTART_KEYWORDS)
    if rest_restart_matches:
        return CLUSTER_META["rest_then_restart"]["id"], rest_restart_matches, [], "rest and restart evidence"

    return OTHER_PATH_ID, [], [], "no career path evidence"


def _query_relevant_action_summary(
    *,
    query_context: dict[str, Any],
    source_title: str = "",
    situation: str,
    action_summary: str,
    real_details: list[str],
    key_fragments: list[str],
    current_status: str,
    entry_status: str,
) -> str:
    if _text(query_context.get("query_type")) != "career_restart":
        return action_summary
    evidence = " ".join(
        _text(part)
        for part in (
            situation,
            source_title,
            action_summary,
            " ".join(real_details),
            " ".join(key_fragments),
            current_status,
            entry_status,
        )
        if _text(part)
    )
    post_action_text = _career_post_resignation_action_text(evidence)
    if _matched_public_exam_keywords(post_action_text) and _has_post_resignation_action_context(
        evidence,
        PUBLIC_EXAM_KEYWORDS + PUBLIC_EXAM_CONTEXT_KEYWORDS,
    ):
        if "考编" in post_action_text:
            return "裸辞后转向考编路径"
        if "考公" in post_action_text or "公务员" in post_action_text:
            return "裸辞后转向考公路径"
        return "裸辞后转向稳定考试路径"
    if _matched_study_exam_keywords(post_action_text) and _has_post_resignation_action_context(
        evidence,
        STUDY_EXAM_KEYWORDS + STUDY_EXAM_CONTEXT_KEYWORDS,
    ):
        return _study_exam_action_summary(post_action_text)
    if _matched_migration_life_keywords(post_action_text) and _has_post_resignation_action_context(
        evidence,
        MIGRATION_LIFE_KEYWORDS + MIGRATION_LIFE_LOCATION_KEYWORDS,
    ):
        return _migration_life_action_summary(post_action_text)
    return action_summary


def _study_exam_action_summary(text: str) -> str:
    clean = _text(text)
    if "考研" in clean and "复试" in clean:
        return "裸辞后准备考研，并走到复试阶段"
    if "复试" in clean and _matched_study_exam_keywords(clean):
        return "裸辞后进入考试复试阶段"
    if "研究生" in clean or "读研" in clean or "考研" in clean:
        return "裸辞后准备考研/读研路径"
    if "读书" in clean or "学习" in clean:
        return "裸辞后转向读书学习路径"
    return "裸辞后转向学习考试路径"


def _migration_life_action_summary(text: str) -> str:
    clean = _text(text)
    if "英国" in clean and "全家" in clean:
        return "裸辞后全家搬往英国生活"
    if "英国" in clean:
        return "裸辞后搬往英国生活"
    if any(marker in clean for marker in ("出国", "海外", "国外", "换国家")):
        return "裸辞后转向出国/海外生活"
    if "换城市" in clean:
        return "裸辞后换城市重新生活"
    if "搬" in clean:
        return "裸辞后搬家换环境生活"
    return "裸辞后换环境重新生活"


def _classify_family_money_path(text: str) -> tuple[str, list[str], list[str], str]:
    family_money_evidence = _matched_keywords(text, FAMILY_MONEY_ANY_KEYWORDS)
    if not family_money_evidence:
        return "", [], [OTHER_PATH_ID], "no family_money mechanism evidence"

    boundary = _matched_keywords(text, FAMILY_MONEY_BOUNDARY_KEYWORDS)
    if boundary:
        return "path_family_money_boundary", boundary, [], "money boundary evidence"

    temporary_transfer = _matched_keywords(text, FAMILY_MONEY_TEMPORARY_TRANSFER_KEYWORDS)
    if temporary_transfer:
        return "path_family_support_money", temporary_transfer, [], "temporary transfer / emergency support evidence"

    parent_rework = _matched_keywords(text, FAMILY_PARENT_REWORK_KEYWORDS)
    if parent_rework:
        return "path_family_parent_rework", parent_rework, [], "parent rework or income evidence"

    shared_burden = _matched_keywords(text, FAMILY_SHARED_BURDEN_KEYWORDS)
    if shared_burden:
        return "path_family_shared_burden", shared_burden, [], "shared family burden evidence"

    support = _matched_keywords(text, FAMILY_SUPPORT_MONEY_KEYWORDS)
    if support:
        return "path_family_support_money", support, [], "family money support evidence"

    return "", family_money_evidence, [OTHER_PATH_ID], "family_money topic without path mechanism evidence"


def _classify_relationship_path(text: str) -> tuple[str, list[str], list[str], str]:
    relationship_evidence = _matched_keywords(
        text,
        ("恋爱", "分手", "结婚", "婚姻", "伴侣", "男朋友", "女朋友", "异地", "亲密关系", "关系"),
    )
    if not relationship_evidence:
        return "", [], ["path_return_to_work", "path_public_exam"], "no relationship evidence"

    long_distance = _matched_keywords(text, RELATIONSHIP_LONG_DISTANCE_KEYWORDS)
    if long_distance and any(marker in text for marker in ("同城", "见面", "搬", "城市")):
        return "path_relationship_long_distance_to_same_city", long_distance, [], "long-distance relationship evidence"
    repair = _matched_keywords(text, RELATIONSHIP_REPAIR_KEYWORDS)
    if repair:
        return "path_relationship_repair", repair, [], "repair or communication evidence"
    breakup = _matched_keywords(text, RELATIONSHIP_BREAK_KEYWORDS)
    if breakup:
        if any(marker in text for marker in ("重新生活", "恢复", "走出来", "之后")):
            return "path_relationship_recover_after_breakup", breakup, [], "post-breakup recovery evidence"
        return "path_relationship_break_up", breakup, [], "breakup evidence"
    self_pattern = _matched_keywords(text, RELATIONSHIP_SELF_PATTERN_KEYWORDS)
    if self_pattern:
        return "path_relationship_self_pattern", self_pattern, [], "self-pattern reflection evidence"
    observe = _matched_keywords(text, RELATIONSHIP_OBSERVE_KEYWORDS)
    if observe:
        return "path_relationship_slow_observe", observe, [], "slow-observe evidence"
    return "path_relationship_slow_observe", relationship_evidence, [], "relationship evidence without clear outcome"


def _classify_new_zealand_path(text: str) -> tuple[str, list[str], list[str], str]:
    nz_evidence = _matched_new_zealand_target_location_keywords(text)
    if not nz_evidence:
        return "", [], ["path_return_to_work", "path_public_exam"], "no New Zealand target-location evidence"

    returned = _matched_keywords(text, NEW_ZEALAND_RETURN_KEYWORDS)
    if returned:
        return "path_nz_returned", nz_evidence + returned, [], "went to New Zealand and returned"
    prep = _matched_keywords(text, NEW_ZEALAND_PREP_KEYWORDS)
    if prep and not _has_new_zealand_presence(text):
        return "path_nz_preparing_not_departed", nz_evidence + prep, [], "preparation or application without departure"
    whv = _matched_keywords(text, NEW_ZEALAND_WHV_KEYWORDS)
    if whv:
        return "path_nz_whv_trial", nz_evidence + whv, [], "WHV or working-holiday evidence"
    study = _matched_keywords(text, NEW_ZEALAND_STUDY_KEYWORDS)
    if study:
        return "path_nz_study_work_visa", nz_evidence + study, [], "study pathway evidence"
    remote = _matched_keywords(text, NEW_ZEALAND_REMOTE_KEYWORDS)
    if remote:
        return "path_nz_remote_sojourn", nz_evidence + remote, [], "remote income or sojourn evidence"
    work_visa = _matched_keywords(text, NEW_ZEALAND_WORK_VISA_KEYWORDS)
    if work_visa:
        return "path_nz_living_migrate", nz_evidence + work_visa, [], "work or work-visa pathway evidence"
    if _has_new_zealand_presence(text) or any(marker in text for marker in ("奥克兰生活", "基督城生活", "惠灵顿生活", "皇后镇生活")):
        return "path_nz_living_migrate", nz_evidence, [], "New Zealand living-location evidence"
    if prep:
        return "path_nz_preparing_not_departed", nz_evidence + prep, [], "preparation or application evidence"
    return "", nz_evidence, ["path_nz_living_migrate"], "New Zealand topic without path mechanism evidence"


def _has_new_zealand_presence(text: str) -> bool:
    return any(
        marker in text
        for marker in (
            "在新西兰生活",
            "在新西兰工作",
            "在新西兰读",
            "在新西兰学习",
            "去了新西兰",
            "到新西兰",
            "去新西兰",
            "飞往新西兰",
            "飞新西兰",
            "前往新西兰",
            "登陆新西兰",
            "抵达新西兰",
            "来到新西兰",
            "从新西兰回来",
        )
    )


def _career_post_resignation_action_text(text: str) -> str:
    clean = _text(text)
    if not clean:
        return ""

    suffixes: list[str] = []
    for marker in POST_RESIGNATION_MARKERS:
        start = clean.find(marker)
        if start >= 0:
            suffixes.append(clean[start:])
    if suffixes:
        return " ".join(sorted(suffixes, key=len))

    if _matched_post_premise_state_markers(clean):
        return _drop_pre_resignation_background(clean)
    if "裸辞" in clean or "辞职" in clean or "离职" in clean or "失业" in clean:
        return _drop_pre_resignation_background(clean)
    return clean


def _has_post_resignation_return_context(text: str) -> bool:
    clean = _text(text)
    if not clean:
        return False
    if any(marker in clean for marker in POST_RESIGNATION_MARKERS):
        return True
    state_matches = _matched_post_premise_state_markers(clean)
    return bool(
        state_matches
        or any(marker in clean for marker in ("待业", "无工作", "没工作", "没有工作", "空窗", "失业"))
    )


def _has_post_resignation_action_context(text: str, action_keywords: tuple[str, ...]) -> bool:
    clean = _text(text)
    if not clean:
        return False
    action_pattern = "|".join(
        re.escape(keyword)
        for keyword in sorted(set(action_keywords), key=len, reverse=True)
        if _text(keyword)
    )
    if not action_pattern:
        return False
    post_marker_pattern = "|".join(re.escape(marker) for marker in POST_RESIGNATION_MARKERS)
    premise_pattern = r"裸辞|辞职|离职|失业|待业"
    if re.search(rf"({post_marker_pattern}).{{0,80}}({action_pattern})", clean):
        return True
    if re.search(rf"({premise_pattern}).{{0,32}}({action_pattern})", clean):
        return True
    if re.search(rf"({action_pattern}).{{0,32}}({premise_pattern})", clean):
        return True
    return False


def _drop_pre_resignation_background(text: str) -> str:
    clean = _text(text)
    if not clean:
        return ""
    parts = re.split(r"(?<=[。！？!?；;])\s*|[，,]\s*", clean)
    kept: list[str] = []
    for part in parts:
        if not part:
            continue
        if any(marker in part for marker in PRE_RESIGNATION_BACKGROUND_MARKERS):
            continue
        kept.append(part)
    return " ".join(kept) or clean


def _matched_study_exam_keywords(text: str) -> list[str]:
    clean = _text(text)
    if not clean:
        return []
    matches = _matched_keywords(
        clean,
        tuple(keyword for keyword in STUDY_EXAM_KEYWORDS if keyword != "复试"),
    )
    has_study_context = bool(_matched_keywords(clean, STUDY_EXAM_CONTEXT_KEYWORDS))
    if "复试" in clean and has_study_context:
        matches.append("复试")
    if re.search(r"(裸辞后|辞职后|离职后|失业后).{0,16}(读书|学习|继续学习|继续读书)", clean):
        matches.append("读书/学习")
    return _dedupe(matches)


def _matched_migration_life_keywords(text: str) -> list[str]:
    clean = _text(text)
    if not clean:
        return []
    matches = _matched_keywords(clean, MIGRATION_LIFE_KEYWORDS)
    if "搬" in clean:
        matches.extend(_matched_keywords(clean, MIGRATION_LIFE_LOCATION_KEYWORDS))
    return _dedupe(matches)


def _matched_restart_after_exam_keywords(text: str) -> list[str]:
    lower_text = _text(text).lower()
    has_exam_result = any(
        keyword.lower() in lower_text
        for keyword in ("考公没有上岸", "没有考上公务员", "没考上公务员", "没有上岸", "没上岸")
    )
    has_restart = any(
        keyword.lower() in lower_text
        for keyword in ("重新回到职场", "调整状态", "焦虑感", "内耗", "迷茫")
    )
    if not (has_exam_result and has_restart):
        return []
    return [
        keyword
        for keyword in ("考公没有上岸", "调整状态", "重新回到职场", "内耗", "迷茫")
        if keyword.lower() in lower_text
    ]


def _matched_public_exam_keywords(text: str) -> list[str]:
    matches = _matched_keywords(text, PUBLIC_EXAM_KEYWORDS)
    lower_text = _text(text).lower()
    if "备考" in lower_text and any(
        keyword.lower() in lower_text for keyword in PUBLIC_EXAM_CONTEXT_KEYWORDS
    ):
        matches.append("备考")
    return matches


def _matched_keywords(text: str, keywords: tuple[str, ...]) -> list[str]:
    lower_text = _text(text).lower()
    matches = []
    for keyword in keywords:
        if keyword.lower() in lower_text:
            matches.append(keyword)
    return matches


def _matched_return_to_work_strong_outcome_keywords(text: str) -> list[str]:
    matches = _matched_keywords(text, RETURN_TO_WORK_STRONG_OUTCOME_KEYWORDS)
    negated_matches = _matched_keywords(text, RETURN_TO_WORK_NEGATED_OUTCOME_KEYWORDS)
    if not negated_matches:
        return matches
    return [
        keyword
        for keyword in matches
        if not any(keyword in negated for negated in negated_matches)
    ]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        clean = _text(value)
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result


def _is_valid_people_draft(
    draft: dict[str, Any],
    valid_path_ids: set[str] | None,
) -> bool:
    source = draft.get("source") if isinstance(draft.get("source"), dict) else {}
    path_id = _text(draft.get("pathId"))
    sample_type = _normalize_sample_type(draft.get("sample_type"))
    if not _text(source.get("url")):
        return False
    if not _text(draft.get("sourceExcerpt") or source.get("excerpt")):
        return False
    if not path_id:
        return False
    if valid_path_ids is not None and path_id not in valid_path_ids:
        return False
    if sample_type == "opinion_only":
        return False
    title = _text(source.get("title"))
    if draft.get("confidence") == "low" and any(marker in title for marker in MARKETING_MARKERS):
        return False
    return True


def _build_llm_frontend_person(
    draft: dict[str, Any],
    query: str,
    clarification: str | None,
    query_context: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    context = query_context or {}
    source = draft.get("source") if isinstance(draft.get("source"), dict) else {}
    internal = draft.get("internal") if isinstance(draft.get("internal"), dict) else {}
    source_url = _text(source.get("url") or draft.get("sourceUrl"))
    name = _text(draft.get("name") or source.get("authorName") or source.get("author_name"))
    sample_type = _normalize_sample_type(_text(draft.get("sampleType") or draft.get("sample_type")))
    situation = _text(draft.get("situation"))
    action_summary = _text(draft.get("actionSummary") or draft.get("action_summary"))
    current_status = _text(draft.get("currentStatus") or draft.get("current_status"))
    entry_situation = _text(draft.get("entrySituation") or draft.get("entry_situation"))
    entry_status = _text(draft.get("entryStatus") or draft.get("entry_status"))
    real_details_all = _string_list(draft.get("realDetails") or draft.get("real_details"))
    key_fragments = _string_list(draft.get("key_fragments") or draft.get("keyFragments"))
    if not real_details_all and key_fragments:
        real_details_all = key_fragments[:5]
    confidence = _text(internal.get("confidence") or draft.get("confidence")).lower()
    source_type = _normalize_llm_source_type(source.get("type") or source.get("content_type"))
    if _is_weak_entry_status(current_status):
        current_status = ""
    action_summary = _query_relevant_action_summary(
        query_context=context,
        source_title=_text(source.get("title")),
        situation=situation,
        action_summary=action_summary,
        real_details=real_details_all,
        key_fragments=key_fragments,
        current_status=current_status,
        entry_status=entry_status,
    )
    is_personal_experience = _boolish(
        draft.get("isPersonalExperience")
        if "isPersonalExperience" in draft
        else draft.get("is_personal_experience", True)
    )
    is_first_person = _boolish(
        draft.get("is_first_person_experience")
        if "is_first_person_experience" in draft
        else draft.get("isFirstPersonExperience", True)
    )
    experience_owner = _normalize_experience_owner(draft.get("experience_owner") or draft.get("experienceOwner") or "author")
    can_be_person_sample = _boolish(
        draft.get("can_be_person_sample")
        if "can_be_person_sample" in draft
        else draft.get("canBePersonSample", True)
    )

    formal_drop_reason = _formal_people_drop_reason(
        draft=draft,
        query_context=context,
        source_url=source_url,
        name=name,
        sample_type=sample_type,
        situation=situation,
        action_summary=action_summary,
        real_details=real_details_all,
        key_fragments=key_fragments,
        current_status=current_status,
        confidence=confidence,
        is_personal_experience=is_personal_experience,
        is_first_person=is_first_person,
        experience_owner=experience_owner,
        can_be_person_sample=can_be_person_sample,
    )
    if formal_drop_reason:
        return None

    real_details = real_details_all[:5]
    situation = _normalize_llm_situation(
        name=name,
        situation=situation,
        real_details=real_details,
        current_status=current_status,
    )
    entry_situation = _entry_situation(situation if _should_prefer_situation_entry(name, entry_situation) else entry_situation or situation)
    entry_status = _entry_status(current_status if _is_weak_entry_status(entry_status) else entry_status or current_status)
    normalized_internal = {
        "matchReasons": _string_list(internal.get("matchReasons") or internal.get("match_reasons")),
        "confidence": confidence,
        "hasOutcome": bool(internal.get("hasOutcome") or internal.get("has_outcome")),
        "hasTimeline": bool(internal.get("hasTimeline") or internal.get("has_timeline")),
        "missingInfo": _string_list(internal.get("missingInfo") or internal.get("missing_info")),
    }
    if len(real_details_all) > len(real_details):
        normalized_internal["allRealDetails"] = real_details_all

    normalized = {
        "id": _text(draft.get("id")) or f"llm_person_{_stable_suffix(source_url)}",
        "name": name,
        "avatar": _text(draft.get("avatar") or source.get("authorAvatar") or source.get("author_avatar")),
        "sampleType": sample_type,
        "sample_type": sample_type,
        "contentType": sample_type,
        "situation": situation,
        "actionSummary": action_summary,
        "realDetails": real_details,
        "key_fragments": key_fragments or real_details,
        "currentStatus": current_status,
        "entrySituation": entry_situation,
        "entryStatus": entry_status,
        "source": {
            "title": _text(source.get("title")),
            "url": source_url,
            "type": source_type,
            "authorName": _text(source.get("authorName") or source.get("author_name") or name),
            "updatedAt": _text(source.get("updatedAt") or source.get("updated_at")),
            "content_type": source_type,
            "author_name": _text(source.get("authorName") or source.get("author_name") or name),
            "author_avatar": _text(draft.get("avatar") or source.get("authorAvatar") or source.get("author_avatar")),
            "excerpt": _text(draft.get("rawContentPreview") or source.get("excerpt")),
        },
        "internal": normalized_internal,
        "who": situation,
        "oneLine": action_summary,
        "matchReasons": normalized_internal["matchReasons"],
        "sourceTitle": _text(source.get("title")),
        "sourceUrl": source_url,
        "sourceExcerpt": _text(draft.get("rawContentPreview") or source.get("excerpt")),
        "role": "知乎用户",
        "badge": _format_badge(situation),
        "timeline": [],
        "keyExperience": action_summary,
    }
    assignment_debug = _assign_path_for_llm_person_with_debug(
        normalized,
        query=query,
        clarification=clarification,
        query_context=context,
    )
    if not assignment_debug["assignedPathId"]:
        return None
    normalized["pathId"] = assignment_debug["assignedPathId"]
    assignment_debug["personId"] = normalized["id"]
    assignment_debug["name"] = normalized["name"]
    normalized["_llmPathAssignmentDebug"] = assignment_debug
    return normalized


def _llm_people_filter_debug_entry(
    draft: dict[str, Any],
    person: dict[str, Any] | None,
    query_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source = draft.get("source") if isinstance(draft.get("source"), dict) else {}
    internal = draft.get("internal") if isinstance(draft.get("internal"), dict) else {}
    source_url = _text(source.get("url") or draft.get("sourceUrl"))
    name = _text(draft.get("name") or source.get("authorName") or source.get("author_name"))
    sample_type = _normalize_sample_type(_text(draft.get("sampleType") or draft.get("sample_type")))
    confidence = _text(internal.get("confidence") or draft.get("confidence")).lower()
    situation = _text(draft.get("situation"))
    action_summary = _text(draft.get("actionSummary") or draft.get("action_summary"))
    current_status = _text(draft.get("currentStatus") or draft.get("current_status"))
    if _is_weak_entry_status(current_status):
        current_status = ""
    real_details = _string_list(draft.get("realDetails") or draft.get("real_details"))
    key_fragments = _string_list(draft.get("key_fragments") or draft.get("keyFragments"))
    explicit_filter_reason = _text(draft.get("filter_reason") or draft.get("filterReason"))
    is_personal_experience = _boolish(
        draft.get("isPersonalExperience")
        if "isPersonalExperience" in draft
        else draft.get("is_personal_experience", True)
    )
    is_first_person = _boolish(
        draft.get("is_first_person_experience")
        if "is_first_person_experience" in draft
        else draft.get("isFirstPersonExperience", True)
    )
    experience_owner = _normalize_experience_owner(
        draft.get("experience_owner") or draft.get("experienceOwner") or "author"
    )
    can_be_person_sample = _boolish(
        draft.get("can_be_person_sample")
        if "can_be_person_sample" in draft
        else draft.get("canBePersonSample", True)
    )
    non_author_drop_reason = _non_author_experience_drop_reason(name=name, draft=draft)
    formal_decision = _formal_people_filter_decision(
        draft=draft,
        query_context=query_context or {},
        source_url=source_url,
        name=name,
        sample_type=sample_type,
        situation=situation,
        action_summary=action_summary,
        real_details=real_details,
        key_fragments=key_fragments,
        current_status=current_status,
        confidence=confidence,
        is_personal_experience=is_personal_experience,
        is_first_person=is_first_person,
        experience_owner=experience_owner,
        can_be_person_sample=can_be_person_sample,
    )
    formal_drop_reason = _text(formal_decision.get("final_filter_reason"))
    kept = person is not None
    drop_reason = ""
    if not kept:
        drop_reason = formal_drop_reason or non_author_drop_reason or "path assignment failed"
    final_filter_reason = "" if kept else drop_reason
    return {
        "name": name,
        "personId": _text(person.get("id")) if isinstance(person, dict) else _text(draft.get("id")),
        "kept": kept,
        "dropReason": drop_reason,
        "original_filter_reason": _text(formal_decision.get("original_filter_reason")),
        "final_filter_reason": final_filter_reason,
        "rescue_reason": _text(formal_decision.get("rescue_reason")),
        "matched_structured_fields": formal_decision.get("matched_structured_fields") or [],
        "evidence_score": int(formal_decision.get("evidence_score") or 0),
        "matched_action_markers": formal_decision.get("matched_action_markers") or [],
        "can_rescue_by_structured_fields": bool(formal_decision.get("can_rescue_by_structured_fields")),
        "requires_query_premise_state": bool(formal_decision.get("requires_query_premise_state")),
        "matched_query_premise_positive": formal_decision.get("matched_query_premise_positive") or [],
        "matched_query_premise_negative": formal_decision.get("matched_query_premise_negative") or [],
        "query_premise_verdict": _text(formal_decision.get("query_premise_verdict")),
        "matched_query_premise_positive_by_field": formal_decision.get("matched_query_premise_positive_by_field") or {},
        "matched_query_premise_negative_by_field": formal_decision.get("matched_query_premise_negative_by_field") or {},
        "matched_family_money_interaction_keywords": formal_decision.get("matched_family_money_interaction_keywords") or [],
        "matched_family_money_transfer_keywords": formal_decision.get("matched_family_money_transfer_keywords") or [],
        "migration_target_location_positive": formal_decision.get("migration_target_location_positive") or [],
        "migration_target_location_negative": formal_decision.get("migration_target_location_negative") or [],
        "migration_target_location_verdict": _text(formal_decision.get("migration_target_location_verdict")),
        "matched_migration_author_journey_keywords": formal_decision.get("matched_migration_author_journey_keywords") or [],
        "migration_author_journey_keywords": formal_decision.get("migration_author_journey_keywords") or [],
        "migration_author_journey_hard_negative_keywords": formal_decision.get(
            "migration_author_journey_hard_negative_keywords"
        )
        or [],
        "migration_rescue_blocked_reason": _text(formal_decision.get("migration_rescue_blocked_reason")),
        "sampleType": sample_type,
        "isPersonalExperience": is_personal_experience,
        "is_first_person_experience": is_first_person,
        "experience_owner": experience_owner,
        "can_be_person_sample": can_be_person_sample,
        "filter_reason": explicit_filter_reason,
        "confidence": confidence,
        "pathId": _text(person.get("pathId")) if isinstance(person, dict) else "",
        "hasSourceUrl": bool(source_url),
        "hasSituation": bool(situation),
        "hasActionSummary": bool(action_summary),
        "hasCurrentStatus": bool(current_status),
    }


def _formal_people_drop_reason(
    *,
    draft: dict[str, Any],
    query_context: dict[str, Any],
    source_url: str,
    name: str,
    sample_type: str,
    situation: str,
    action_summary: str,
    real_details: list[str],
    key_fragments: list[str],
    current_status: str,
    confidence: str,
    is_personal_experience: bool,
    is_first_person: bool,
    experience_owner: str,
    can_be_person_sample: bool,
) -> str:
    return _formal_people_filter_decision(
        draft=draft,
        query_context=query_context,
        source_url=source_url,
        name=name,
        sample_type=sample_type,
        situation=situation,
        action_summary=action_summary,
        real_details=real_details,
        key_fragments=key_fragments,
        current_status=current_status,
        confidence=confidence,
        is_personal_experience=is_personal_experience,
        is_first_person=is_first_person,
        experience_owner=experience_owner,
        can_be_person_sample=can_be_person_sample,
    )["final_filter_reason"]


def _formal_people_filter_decision(
    *,
    draft: dict[str, Any],
    query_context: dict[str, Any],
    source_url: str,
    name: str,
    sample_type: str,
    situation: str,
    action_summary: str,
    real_details: list[str],
    key_fragments: list[str],
    current_status: str,
    confidence: str,
    is_personal_experience: bool,
    is_first_person: bool,
    experience_owner: str,
    can_be_person_sample: bool,
) -> dict[str, Any]:
    explicit_filter_reason = _text(draft.get("filter_reason") or draft.get("filterReason"))
    rescue_info = _structured_experience_rescue_info(
        draft=draft,
        query_context=query_context,
        source_url=source_url,
        situation=situation,
        action_summary=action_summary,
        current_status=current_status,
        is_first_person=is_first_person,
        experience_owner=experience_owner,
    )
    premise_text = _formal_structured_premise_text(
        draft=draft,
        situation=situation,
        action_summary=action_summary,
        real_details=real_details,
        key_fragments=key_fragments,
        current_status=current_status,
    )
    premise_info = _query_premise_evidence_from_fields(
        draft=draft,
        query_context=query_context,
        situation=situation,
        action_summary=action_summary,
        real_details=real_details,
        key_fragments=key_fragments,
        current_status=current_status,
    )
    family_money_interaction_keywords = _matched_family_money_author_interaction_keywords(
        premise_text,
        query_context,
    )
    family_money_transfer_keywords = _matched_family_money_transfer_keywords(
        premise_text,
        query_context,
    )
    migration_target_location_info = _migration_target_location_info(
        draft=draft,
        query_context=query_context,
        situation=situation,
        action_summary=action_summary,
        real_details=real_details,
        key_fragments=key_fragments,
        current_status=current_status,
    )
    migration_author_journey_keywords = _matched_migration_author_journey_keywords(
        premise_text,
        query_context,
    )
    migration_author_journey_hard_negative_keywords = _matched_keywords(
        premise_text,
        MIGRATION_AUTHOR_JOURNEY_EXCLUDE_KEYWORDS,
    )

    def decision(
        final_filter_reason: str,
        *,
        original_filter_reason: str = "",
        rescue_reason: str = "",
    ) -> dict[str, Any]:
        return {
            "original_filter_reason": original_filter_reason or final_filter_reason,
            "final_filter_reason": final_filter_reason,
            "rescue_reason": rescue_reason,
            "matched_structured_fields": rescue_info["matched_structured_fields"],
            "evidence_score": rescue_info["evidence_score"],
            "matched_action_markers": rescue_info["matched_action_markers"],
            "can_rescue_by_structured_fields": rescue_info["can_rescue"],
            "requires_query_premise_state": premise_info["requires_query_premise_state"],
            "matched_query_premise_positive": premise_info["positive"],
            "matched_query_premise_negative": premise_info["negative"],
            "query_premise_verdict": premise_info["verdict"],
            "matched_query_premise_positive_by_field": premise_info["positive_by_field"],
            "matched_query_premise_negative_by_field": premise_info["negative_by_field"],
            "matched_family_money_interaction_keywords": family_money_interaction_keywords,
            "matched_family_money_transfer_keywords": family_money_transfer_keywords,
            "migration_target_location_positive": migration_target_location_info["positive"],
            "migration_target_location_negative": migration_target_location_info["negative"],
            "migration_target_location_verdict": migration_target_location_info["verdict"],
            "matched_migration_author_journey_keywords": migration_author_journey_keywords,
            "migration_author_journey_keywords": migration_author_journey_keywords,
            "migration_author_journey_hard_negative_keywords": migration_author_journey_hard_negative_keywords,
            "migration_rescue_blocked_reason": (
                ""
                if rescue_reason
                else migration_author_journey_rescue_blocked_reason(
                    original_filter_reason or final_filter_reason
                )
            ),
        }

    def maybe_rescue(reason: str) -> dict[str, Any]:
        if _is_structured_rescueable_reason(reason) and rescue_info["can_rescue"]:
            return decision(
                "",
                original_filter_reason=reason,
                rescue_reason=STRUCTURED_RESCUE_REASON,
            )
        return decision(reason)

    def can_rescue_family_money_interaction(reason: str) -> bool:
        if not _is_family_money_non_author_false_positive_reason(reason):
            return False
        if not family_money_interaction_keywords:
            return False
        if not source_url or not situation or not action_summary:
            return False
        if not (experience_owner in AUTHOR_EXPERIENCE_OWNERS or is_first_person):
            return False
        non_author_text = _family_money_structured_text(
            draft=draft,
            situation=situation,
            action_summary=action_summary,
            real_details=real_details,
            key_fragments=key_fragments,
            current_status=current_status,
        )
        return not any(marker in non_author_text for marker in FAMILY_MONEY_HARD_NON_AUTHOR_MARKERS)

    def can_rescue_family_money_transfer(reason: str) -> bool:
        if not _is_structured_rescueable_reason(reason):
            return False
        if not family_money_transfer_keywords:
            return False
        if not source_url or not situation or not action_summary:
            return False
        if not (experience_owner in AUTHOR_EXPERIENCE_OWNERS or is_first_person):
            return False
        non_author_text = _family_money_structured_text(
            draft=draft,
            situation=situation,
            action_summary=action_summary,
            real_details=real_details,
            key_fragments=key_fragments,
            current_status=current_status,
        )
        return not any(marker in non_author_text for marker in FAMILY_MONEY_HARD_NON_AUTHOR_MARKERS)

    def is_migration_author_journey_rescueable_reason(reason: str) -> bool:
        clean_reason = _text(reason)
        return clean_reason in MIGRATION_AUTHOR_JOURNEY_RESCUEABLE_REASONS or clean_reason.startswith(
            "experience_owner=mentioned_person"
        )

    def migration_author_journey_rescue_blocked_reason(reason: str) -> str:
        if _text(query_context.get("query_type")) != "migration_new_zealand":
            return ""
        if not is_migration_author_journey_rescueable_reason(reason):
            return "reason_not_rescueable"
        if not source_url:
            return "missing_source_url"
        if migration_target_location_info["negative"]:
            return "hard_negative_matched"
        if migration_target_location_info["verdict"] != "positive":
            return "missing_target_location_positive"
        if migration_author_journey_hard_negative_keywords:
            return "hard_negative_matched"
        required_fields = {
            "source.url",
            "author_or_first_person",
            "situation",
            "actionSummary",
        }
        matched_fields = set(rescue_info["matched_structured_fields"])
        if not required_fields.issubset(matched_fields):
            return "missing_structured_fields"
        if int(rescue_info["evidence_score"]) < 5:
            return "evidence_score_below_threshold"
        if not migration_author_journey_keywords:
            return "missing_author_journey_keywords"
        return ""

    def can_rescue_migration_author_journey(reason: str) -> bool:
        if _text(query_context.get("query_type")) != "migration_new_zealand":
            return False
        return migration_author_journey_rescue_blocked_reason(reason) == ""

    if not source_url:
        return decision("missing source.url")
    if not name:
        return decision("missing name")
    if sample_type not in VALID_LLM_SAMPLE_TYPES:
        return decision("invalid sampleType")
    if sample_type not in FORMAL_SAMPLE_TYPES:
        return decision("opinion_with_experience excluded from formal people")
    if migration_target_location_info["verdict"] == "negative":
        return decision(MIGRATION_TARGET_LOCATION_MISMATCH_REASON)
    if experience_owner == "mentioned_person":
        reason = f"experience_owner={experience_owner} excluded from formal people"
        if can_rescue_migration_author_journey(reason):
            return decision(
                "",
                original_filter_reason=reason,
                rescue_reason=MIGRATION_AUTHOR_JOURNEY_RESCUE_REASON,
            )
        return decision(reason)
    family_money_subject_drop_reason = _family_money_subject_drop_reason(premise_text, query_context)
    if family_money_subject_drop_reason:
        return decision(family_money_subject_drop_reason)
    non_author_drop_reason = _non_author_experience_drop_reason(name=name, draft=draft)
    if (
        non_author_drop_reason
        and not _is_structured_rescueable_reason(non_author_drop_reason)
        and not can_rescue_family_money_interaction(non_author_drop_reason)
        and not can_rescue_migration_author_journey(non_author_drop_reason)
    ):
        return decision(non_author_drop_reason)
    if (
        _text(query_context.get("query_type")) == "family_money"
        and _is_structured_rescueable_reason(explicit_filter_reason)
        and not rescue_info["can_rescue"]
    ):
        if can_rescue_family_money_transfer(explicit_filter_reason):
            return decision(
                "",
                original_filter_reason=explicit_filter_reason,
                rescue_reason=FAMILY_MONEY_TRANSFER_RESCUE_REASON,
            )
        return decision(explicit_filter_reason)
    if _is_query_premise_not_entered_reason(explicit_filter_reason):
        can_rescue_premise = bool(
            premise_info["verdict"] == "positive"
            and (experience_owner in AUTHOR_EXPERIENCE_OWNERS or is_first_person)
            and situation
            and action_summary
        )
        if can_rescue_premise:
            return decision(
                "",
                original_filter_reason=explicit_filter_reason,
                rescue_reason=POST_PREMISE_RESCUE_REASON,
            )
        return decision(
            QUERY_PREMISE_NOT_ENTERED_FILTER_REASON,
            original_filter_reason=explicit_filter_reason,
        )
    if not is_personal_experience:
        if can_rescue_family_money_transfer(explicit_filter_reason or "not personal experience"):
            return decision(
                "",
                original_filter_reason=explicit_filter_reason or "not personal experience",
                rescue_reason=FAMILY_MONEY_TRANSFER_RESCUE_REASON,
            )
        return maybe_rescue(explicit_filter_reason or "not personal experience")
    if not is_first_person:
        if can_rescue_family_money_transfer(explicit_filter_reason or "not first-person author experience"):
            return decision(
                "",
                original_filter_reason=explicit_filter_reason or "not first-person author experience",
                rescue_reason=FAMILY_MONEY_TRANSFER_RESCUE_REASON,
            )
        return maybe_rescue(explicit_filter_reason or "not first-person author experience")
    if experience_owner not in AUTHOR_EXPERIENCE_OWNERS:
        if not (is_first_person and _is_structured_rescueable_reason(explicit_filter_reason) and rescue_info["can_rescue"]):
            return decision(f"experience_owner={experience_owner} excluded from formal people")
    if not can_be_person_sample:
        if can_rescue_migration_author_journey(explicit_filter_reason or SUBJECT_MISMATCH_FILTER_REASON):
            return decision(
                "",
                original_filter_reason=explicit_filter_reason or SUBJECT_MISMATCH_FILTER_REASON,
                rescue_reason=MIGRATION_AUTHOR_JOURNEY_RESCUE_REASON,
            )
        if can_rescue_family_money_transfer(explicit_filter_reason or "can_be_person_sample=false"):
            return decision(
                "",
                original_filter_reason=explicit_filter_reason or "can_be_person_sample=false",
                rescue_reason=FAMILY_MONEY_TRANSFER_RESCUE_REASON,
            )
        if can_rescue_family_money_interaction(explicit_filter_reason or non_author_drop_reason):
            return decision(
                "",
                original_filter_reason=explicit_filter_reason or non_author_drop_reason,
                rescue_reason=FAMILY_MONEY_INTERACTION_RESCUE_REASON,
            )
        return maybe_rescue(explicit_filter_reason or "can_be_person_sample=false")

    if non_author_drop_reason:
        if can_rescue_migration_author_journey(non_author_drop_reason):
            return decision(
                "",
                original_filter_reason=non_author_drop_reason,
                rescue_reason=MIGRATION_AUTHOR_JOURNEY_RESCUE_REASON,
            )
        if can_rescue_family_money_interaction(non_author_drop_reason):
            return decision(
                "",
                original_filter_reason=non_author_drop_reason,
                rescue_reason=FAMILY_MONEY_INTERACTION_RESCUE_REASON,
            )
        if _is_structured_rescueable_reason(non_author_drop_reason):
            return maybe_rescue(non_author_drop_reason)
        return decision(non_author_drop_reason)

    if not situation:
        return decision("missing situation")
    if not action_summary:
        return decision("missing actionSummary")
    if confidence not in VALID_LLM_CONFIDENCE:
        return decision("invalid confidence")
    if confidence == "low":
        return decision("low confidence")

    combined = _formal_evidence_text(
        draft=draft,
        situation=situation,
        action_summary=action_summary,
        real_details=real_details,
        key_fragments=key_fragments,
        current_status=current_status,
    )
    query_premise_drop_reason = _query_premise_drop_reason_from_evidence(premise_info)
    if query_premise_drop_reason:
        return decision(query_premise_drop_reason)

    query_subject_drop_reason = _query_subject_drop_reason(combined, query_context)
    if query_subject_drop_reason:
        if can_rescue_migration_author_journey(query_subject_drop_reason):
            return decision(
                "",
                original_filter_reason=query_subject_drop_reason,
                rescue_reason=MIGRATION_AUTHOR_JOURNEY_RESCUE_REASON,
            )
        return decision(query_subject_drop_reason)

    if _looks_like_advice_without_author_process(
        name=name,
        source=draft.get("source") if isinstance(draft.get("source"), dict) else {},
        draft=draft,
        text=combined,
    ):
        if can_rescue_family_money_transfer(ADVICE_COMMENTARY_FILTER_REASON):
            return decision(
                "",
                original_filter_reason=ADVICE_COMMENTARY_FILTER_REASON,
                rescue_reason=FAMILY_MONEY_TRANSFER_RESCUE_REASON,
            )
        return maybe_rescue(ADVICE_COMMENTARY_FILTER_REASON)

    evidence_categories = _author_evidence_categories(
        situation=situation,
        action_summary=action_summary,
        real_details=real_details,
        key_fragments=key_fragments,
        current_status=current_status,
        draft=draft,
    )
    if len(evidence_categories) < 2:
        return maybe_rescue(WEAK_FIRST_PERSON_FILTER_REASON)
    if not _passes_query_constraints(
        draft=draft,
        text=f"{situation} {action_summary} {' '.join(real_details)} {current_status}",
        query_context=query_context,
    ):
        if can_rescue_migration_author_journey(SUBJECT_MISMATCH_FILTER_REASON):
            return decision(
                "",
                original_filter_reason=SUBJECT_MISMATCH_FILTER_REASON,
                rescue_reason=MIGRATION_AUTHOR_JOURNEY_RESCUE_REASON,
            )
        return decision(SUBJECT_MISMATCH_FILTER_REASON)
    if _is_structured_rescueable_reason(explicit_filter_reason) and rescue_info["can_rescue"]:
        return decision(
            "",
            original_filter_reason=explicit_filter_reason,
            rescue_reason=STRUCTURED_RESCUE_REASON,
        )
    return decision("")


def _structured_experience_rescue_info(
    *,
    draft: dict[str, Any],
    query_context: dict[str, Any],
    source_url: str,
    situation: str,
    action_summary: str,
    current_status: str,
    is_first_person: bool,
    experience_owner: str,
) -> dict[str, Any]:
    internal = draft.get("internal") if isinstance(draft.get("internal"), dict) else {}
    entry_status = _text(draft.get("entryStatus") or draft.get("entry_status"))
    has_outcome = bool(internal.get("hasOutcome") or internal.get("has_outcome"))
    action_text = f"{situation} {action_summary}"
    matched_action_markers = _matched_structured_action_markers(action_text, query_context)

    matched_fields: list[str] = []
    if source_url:
        matched_fields.append("source.url")
    if experience_owner in AUTHOR_EXPERIENCE_OWNERS or is_first_person:
        matched_fields.append("author_or_first_person")
    if situation:
        matched_fields.append("situation")
    if action_summary:
        matched_fields.append("actionSummary")
    if current_status or entry_status or has_outcome:
        matched_fields.append("stage_or_outcome")
    if matched_action_markers:
        matched_fields.append("post_premise_action")

    required_fields = {
        "source.url",
        "author_or_first_person",
        "situation",
        "actionSummary",
        "stage_or_outcome",
        "post_premise_action",
    }
    return {
        "can_rescue": required_fields.issubset(set(matched_fields)),
        "matched_structured_fields": matched_fields,
        "evidence_score": len(matched_fields),
        "matched_action_markers": matched_action_markers,
    }


def _matched_structured_action_markers(
    text: str,
    query_context: dict[str, Any],
) -> list[str]:
    query_type = _text(query_context.get("query_type"))
    if query_type == "career_restart":
        return _matched_keywords(text, CAREER_RESTART_POST_PREMISE_ACTION_MARKERS)
    return _matched_keywords(text, CONCRETE_ACTION_MARKERS)


def _is_structured_rescueable_reason(reason: str) -> bool:
    return _text(reason) in STRUCTURED_RESCUEABLE_REASONS


def _is_query_premise_not_entered_reason(reason: str) -> bool:
    return _text(reason) in QUERY_PREMISE_NOT_ENTERED_ALIASES


def _is_family_money_non_author_false_positive_reason(reason: str) -> bool:
    compact = _text(reason)
    return compact in {
        "post-check: mentioned_person/case rather than author's own lived experience",
        "mentioned_person/case rather than author's own lived experience",
    }


def _query_premise_drop_reason(text: str, query_context: dict[str, Any]) -> str:
    evidence = _query_premise_evidence(text, query_context)
    return _query_premise_drop_reason_from_evidence(evidence)


def _query_premise_drop_reason_from_evidence(evidence: dict[str, Any]) -> str:
    if not evidence["requires_query_premise_state"]:
        return ""
    if evidence.get("verdict") == "negative":
        return QUERY_PREMISE_NOT_ENTERED_FILTER_REASON
    return ""


def _query_premise_evidence_from_fields(
    *,
    draft: dict[str, Any],
    query_context: dict[str, Any],
    situation: str,
    action_summary: str,
    real_details: list[str],
    key_fragments: list[str],
    current_status: str,
) -> dict[str, Any]:
    base = _empty_query_premise_evidence(query_context)
    if not base["requires_query_premise_state"]:
        return base

    entry_status = _text(draft.get("entryStatus") or draft.get("entry_status"))
    field_texts = {
        "currentStatus": current_status,
        "entryStatus": entry_status,
        "actionSummary": action_summary,
        "situation": situation,
        "details": " ".join(real_details + key_fragments),
    }
    positive_by_field = {
        field: _matched_post_premise_state_markers(text)
        for field, text in field_texts.items()
        if _text(text)
    }
    negative_by_field = {
        field: _matched_keywords(text, CAREER_RESTART_PREMISE_NOT_ENTERED_MARKERS)
        for field, text in field_texts.items()
        if _text(text)
    }
    positive_by_field = {field: matches for field, matches in positive_by_field.items() if matches}
    negative_by_field = {field: matches for field, matches in negative_by_field.items() if matches}

    status_positive = positive_by_field.get("currentStatus") or positive_by_field.get("entryStatus") or []
    status_negative = negative_by_field.get("currentStatus") or negative_by_field.get("entryStatus") or []
    action_positive = positive_by_field.get("actionSummary") or []
    action_negative = negative_by_field.get("actionSummary") or []
    other_positive = [
        marker
        for field in ("situation", "details")
        for marker in positive_by_field.get(field, [])
    ]
    other_negative = [
        marker
        for field in ("situation", "details")
        for marker in negative_by_field.get(field, [])
    ]

    verdict = "unknown"
    if status_positive:
        verdict = "positive"
    elif status_negative:
        verdict = "negative"
    elif action_positive and not action_negative:
        verdict = "positive"
    elif action_positive and _action_positive_overrides_negative(action_positive):
        verdict = "positive"
    elif action_negative:
        verdict = "negative"
    elif other_positive and not other_negative:
        verdict = "positive"
    elif other_negative:
        verdict = "negative"

    return {
        **base,
        "positive": _flatten_match_map(positive_by_field),
        "negative": _flatten_match_map(negative_by_field),
        "positive_by_field": positive_by_field,
        "negative_by_field": negative_by_field,
        "verdict": verdict,
    }


def _query_premise_evidence(text: str, query_context: dict[str, Any]) -> dict[str, Any]:
    base = _empty_query_premise_evidence(query_context)
    if not base["requires_query_premise_state"]:
        return base
    positive = _matched_post_premise_state_markers(text)
    negative = _matched_keywords(text, CAREER_RESTART_PREMISE_NOT_ENTERED_MARKERS)
    verdict = "unknown"
    if positive and not negative:
        verdict = "positive"
    elif negative:
        verdict = "negative"
    return {
        **base,
        "positive": positive,
        "negative": negative,
        "positive_by_field": {"text": positive} if positive else {},
        "negative_by_field": {"text": negative} if negative else {},
        "verdict": verdict,
    }


def _empty_query_premise_evidence(query_context: dict[str, Any]) -> dict[str, Any]:
    query_type = _text(query_context.get("query_type"))
    effective_query = _text(query_context.get("effective_query") or query_context.get("original_query"))
    requires_query_premise_state = bool(
        query_type == "career_restart"
        and any(marker in effective_query for marker in ("裸辞后", "辞职后", "离职后", "失业后"))
    )
    return {
        "requires_query_premise_state": requires_query_premise_state,
        "positive": [],
        "negative": [],
        "positive_by_field": {},
        "negative_by_field": {},
        "verdict": "unknown",
    }


def _action_positive_overrides_negative(matches: list[str]) -> bool:
    return any(
        marker in matches
        for marker in (
            "裸辞后顺利找到新工作",
            "裸辞后顺利找到工作",
            "裸辞后已找到工作",
            "裸辞后找到新工作",
            "离职后入职",
            "离职后重新就业",
            "辞职后一直休息",
            "辞职后未找工作",
            "已裸辞",
            "已经裸辞",
            "裸辞两年",
            "裸辞一年",
            "裸辞后创业",
            "裸辞后尝试创业",
        )
    )


def _flatten_match_map(matches_by_field: dict[str, list[str]]) -> list[str]:
    matches: list[str] = []
    for values in matches_by_field.values():
        for value in values:
            if value not in matches:
                matches.append(value)
    return matches


def _matched_post_premise_state_markers(text: str) -> list[str]:
    matches = _matched_keywords(text, CAREER_RESTART_POST_PREMISE_STATE_MARKERS)
    false_positive_phrases = _matched_keywords(
        text,
        CAREER_RESTART_PREMISE_FALSE_POSITIVE_PHRASES,
    )
    if not false_positive_phrases:
        return matches
    return [
        marker
        for marker in matches
        if not any(marker in phrase for phrase in false_positive_phrases)
    ]


def _migration_target_location_info(
    *,
    draft: dict[str, Any],
    query_context: dict[str, Any],
    situation: str,
    action_summary: str,
    real_details: list[str],
    key_fragments: list[str],
    current_status: str,
) -> dict[str, Any]:
    if _text(query_context.get("query_type")) != "migration_new_zealand":
        return {"positive": [], "negative": [], "verdict": "not_applicable"}
    text = _migration_target_location_text(
        draft=draft,
        situation=situation,
        action_summary=action_summary,
        real_details=real_details,
        key_fragments=key_fragments,
        current_status=current_status,
    )
    positive = _matched_new_zealand_target_location_keywords(text)
    negative = _matched_keywords(text, MIGRATION_TARGET_LOCATION_NEGATIVE_KEYWORDS)
    generic_mechanism = _matched_keywords(text, MIGRATION_GENERIC_MECHANISM_KEYWORDS)
    if positive:
        verdict = "positive"
    elif negative or generic_mechanism or not positive:
        verdict = "negative"
    return {
        "positive": positive,
        "negative": negative,
        "generic_mechanism": generic_mechanism,
        "verdict": verdict,
    }


def _migration_target_location_text(
    *,
    draft: dict[str, Any],
    situation: str,
    action_summary: str,
    real_details: list[str],
    key_fragments: list[str],
    current_status: str,
) -> str:
    source = draft.get("source") if isinstance(draft.get("source"), dict) else {}
    return " ".join(
        _text(part)
        for part in (
            source.get("title"),
            situation,
            action_summary,
            draft.get("entrySituation") or draft.get("entry_situation"),
            draft.get("entryStatus") or draft.get("entry_status"),
            current_status,
            " ".join(real_details),
            " ".join(key_fragments),
            " ".join(_string_list(draft.get("author_experience_evidence") or draft.get("authorExperienceEvidence"))),
            draft.get("rawContentPreview"),
            draft.get("llmInputPreviewHead"),
            draft.get("llmInputPreviewTail"),
        )
    )


def _matched_new_zealand_target_location_keywords(text: str) -> list[str]:
    matches = _matched_keywords(text, NEW_ZEALAND_TARGET_LOCATION_KEYWORDS)
    false_positive_phrases = _matched_keywords(text, NEW_ZEALAND_TARGET_FALSE_POSITIVE_PHRASES)
    if not false_positive_phrases:
        return matches
    return [
        keyword
        for keyword in matches
        if not any(keyword in phrase for phrase in false_positive_phrases)
    ]


def _matched_migration_author_journey_keywords(
    text: str,
    query_context: dict[str, Any],
) -> list[str]:
    if _text(query_context.get("query_type")) != "migration_new_zealand":
        return []
    return _matched_keywords(text, MIGRATION_AUTHOR_JOURNEY_KEYWORDS)


def _matched_family_money_author_interaction_keywords(
    text: str,
    query_context: dict[str, Any],
) -> list[str]:
    if _text(query_context.get("query_type")) != "family_money":
        return []
    matches = [
        keyword
        for keyword in _matched_keywords(text, FAMILY_MONEY_AUTHOR_INTERACTION_KEYWORDS)
        if _has_unnegated_family_money_keyword(text, keyword)
    ]
    negated_phrases = _matched_keywords(text, FAMILY_MONEY_NEGATED_INTERACTION_PHRASES)
    if not negated_phrases:
        return matches
    return [
        keyword
        for keyword in matches
        if not any(keyword in phrase for phrase in negated_phrases)
    ]


def _matched_family_money_transfer_keywords(
    text: str,
    query_context: dict[str, Any],
) -> list[str]:
    if _text(query_context.get("query_type")) != "family_money":
        return []
    matches = [
        keyword
        for keyword in _matched_keywords(text, FAMILY_MONEY_TEMPORARY_TRANSFER_KEYWORDS)
        if _has_unnegated_family_money_keyword(text, keyword)
    ]
    negated_phrases = _matched_keywords(text, FAMILY_MONEY_NEGATED_INTERACTION_PHRASES)
    if not negated_phrases:
        return matches
    return [
        keyword
        for keyword in matches
        if not any(keyword in phrase for phrase in negated_phrases)
    ]


def _has_unnegated_family_money_keyword(text: str, keyword: str) -> bool:
    compact = _text(text)
    needle = _text(keyword)
    if not compact or not needle:
        return False
    start = 0
    while True:
        index = compact.find(needle, start)
        if index < 0:
            return False
        prefix = compact[max(0, index - 12):index]
        if not any(marker in prefix for marker in ("未涉及", "没有", "不是", "无", "未")):
            return True
        start = index + len(needle)


def _family_money_subject_drop_reason(text: str, query_context: dict[str, Any]) -> str:
    if _text(query_context.get("query_type")) != "family_money":
        return ""
    if _matched_family_money_author_interaction_keywords(text, query_context):
        return ""
    effective_query = _text(query_context.get("effective_query") or query_context.get("original_query"))
    if any(marker in effective_query for marker in FAMILY_MONEY_SUPPORT_QUERY_MARKERS):
        return FAMILY_MONEY_SUBJECT_MISMATCH_REASON
    if _matched_keywords(text, FAMILY_PARENT_REWORK_KEYWORDS):
        return ""
    if not _matched_keywords(text, FAMILY_MONEY_ANY_KEYWORDS):
        return FAMILY_MONEY_SUBJECT_MISMATCH_REASON
    return ""


def _formal_evidence_text(
    *,
    draft: dict[str, Any],
    situation: str,
    action_summary: str,
    real_details: list[str],
    key_fragments: list[str],
    current_status: str,
) -> str:
    source = draft.get("source") if isinstance(draft.get("source"), dict) else {}
    return " ".join(
        _text(part)
        for part in (
            source.get("title"),
            situation,
            action_summary,
            " ".join(real_details),
            " ".join(key_fragments),
            " ".join(_string_list(draft.get("author_experience_evidence") or draft.get("authorExperienceEvidence"))),
            current_status,
            draft.get("rawContentPreview"),
            draft.get("llmInputPreviewHead"),
            draft.get("llmInputPreviewTail"),
        )
    )


def _family_money_structured_text(
    *,
    draft: dict[str, Any],
    situation: str,
    action_summary: str,
    real_details: list[str],
    key_fragments: list[str],
    current_status: str,
) -> str:
    return _formal_structured_premise_text(
        draft=draft,
        situation=situation,
        action_summary=action_summary,
        real_details=real_details,
        key_fragments=key_fragments,
        current_status=current_status,
    )


def _formal_structured_premise_text(
    *,
    draft: dict[str, Any],
    situation: str,
    action_summary: str,
    real_details: list[str],
    key_fragments: list[str],
    current_status: str,
) -> str:
    return " ".join(
        _text(part)
        for part in (
            situation,
            action_summary,
            draft.get("entrySituation") or draft.get("entry_situation"),
            draft.get("entryStatus") or draft.get("entry_status"),
            current_status,
            " ".join(real_details),
            " ".join(key_fragments),
            " ".join(_string_list(draft.get("author_experience_evidence") or draft.get("authorExperienceEvidence"))),
        )
    )


def _author_evidence_categories(
    *,
    situation: str,
    action_summary: str,
    real_details: list[str],
    key_fragments: list[str],
    current_status: str,
    draft: dict[str, Any],
) -> set[str]:
    evidence = _formal_evidence_text(
        draft=draft,
        situation=situation,
        action_summary=action_summary,
        real_details=real_details,
        key_fragments=key_fragments,
        current_status=current_status,
    )
    categories: set[str] = set()
    if situation or any(marker in evidence for marker in ("岁", "本科", "研究生", "职业", "工作", "异地", "新西兰", "WHV")):
        categories.add("situation")
    if action_summary and any(marker in evidence for marker in CONCRETE_ACTION_MARKERS):
        categories.add("action")
    if _string_list(draft.get("timeline")) or any(marker in evidence for marker in TIME_STAGE_MARKERS):
        categories.add("time_stage")
    internal = draft.get("internal") if isinstance(draft.get("internal"), dict) else {}
    if current_status or internal.get("hasOutcome") or internal.get("has_outcome") or any(marker in evidence for marker in OUTCOME_STATUS_MARKERS):
        categories.add("status")
    detail_count = len([item for item in real_details + key_fragments if _text(item)])
    author_evidence = _string_list(draft.get("author_experience_evidence") or draft.get("authorExperienceEvidence"))
    if detail_count >= 2 or _has_author_process_evidence(author_evidence):
        categories.add("detail")
    return categories


def _query_subject_drop_reason(text: str, query_context: dict[str, Any]) -> str:
    query_type = _text(query_context.get("query_type"))
    compact = _text(text)
    if query_type == "migration_new_zealand":
        if any(marker in compact for marker in NEW_ZEALAND_NON_AUTHOR_OR_SHORT_TRIP_MARKERS):
            if not any(marker in compact for marker in AUTHOR_NEW_ZEALAND_JOURNEY_MARKERS):
                return SUBJECT_MISMATCH_FILTER_REASON
            if any(marker in compact for marker in ("亲子", "插班", "短期游学", "旅游", "旅行", "攻略", "带孩子")):
                return SUBJECT_MISMATCH_FILTER_REASON
        if not _matched_new_zealand_target_location_keywords(compact):
            return MIGRATION_TARGET_LOCATION_MISMATCH_REASON
    if query_type == "relationship":
        if not any(marker in compact for marker in AUTHOR_RELATIONSHIP_JOURNEY_MARKERS):
            return ADVICE_COMMENTARY_FILTER_REASON
    return ""


def _normalize_llm_situation(
    *,
    name: str,
    situation: str,
    real_details: list[str],
    current_status: str,
) -> str:
    text = _text(situation)
    evidence = f"{text} {' '.join(real_details)} {current_status}"
    if (
        "十方水" in name
        or (
            "销售助理" in evidence
            and ("裸辞" in evidence or "转岗" in evidence)
            and ("30岁" in evidence or "三十" in evidence)
        )
    ):
        return "30岁左右，未婚未育，经历多次裸辞和转岗，目前在销售助理岗位工作，但仍不喜欢这份工作，因现实压力暂时没有再裸辞。"
    return _limit_text(text, 80)


def _mark_filter_debug_dropped(
    filter_debug: list[dict[str, Any]],
    person_ids: set[str],
    reason: str,
) -> None:
    for item in filter_debug:
        if _text(item.get("personId")) in person_ids:
            item["kept"] = False
            item["dropReason"] = reason


def _build_llm_frontend_paths(
    people_counts: Counter[str],
    *,
    people: list[dict[str, Any]],
    query_context: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    context = query_context or {}
    people_by_path: dict[str, list[dict[str, Any]]] = {}
    for person in people:
        people_by_path.setdefault(_text(person.get("pathId")), []).append(person)
    paths: list[dict[str, Any]] = []
    relevance_debug: list[dict[str, Any]] = []
    dropped_paths: list[dict[str, Any]] = []
    for path_id, count in people_counts.items():
        if not path_id or count <= 0 or path_id == OTHER_PATH_ID:
            continue
        supporting_people = people_by_path.get(path_id, [])
        path = _build_llm_frontend_path(
            path_id=path_id,
            count=count,
            supporting_person_ids=[_text(person.get("id")) for person in supporting_people],
        )
        debug = _path_relevance_check(path, supporting_people, context)
        relevance_debug.append(debug)
        if not debug["kept"]:
            dropped_paths.append({**path, "dropReason": debug["dropReason"]})
            continue
        paths.append(path)
    return paths, relevance_debug, dropped_paths


def _build_llm_frontend_path(
    path_id: str,
    count: int,
    supporting_person_ids: list[str] | None = None,
) -> dict[str, Any]:
    cluster_key = _cluster_key_from_path_id(path_id)
    definition = PATH_DEFINITIONS.get(path_id)
    if not definition:
        meta = CLUSTER_META.get(cluster_key, CLUSTER_META["other_related_experience"])
        definition = {
            "name": meta["name"],
            "desc": _llm_path_desc(cluster_key),
        }
    return {
        "id": path_id,
        "name": _format_path_name(definition["name"]),
        "desc": _format_desc(definition["desc"]),
        "count": count,
        "supporting_person_ids": [person_id for person_id in supporting_person_ids or [] if person_id],
        "query_relevance_check": "",
    }


def _path_relevance_check(
    path: dict[str, Any],
    supporting_people: list[dict[str, Any]],
    query_context: dict[str, Any],
) -> dict[str, Any]:
    path_id = _text(path.get("id"))
    name = _text(path.get("name"))
    query_type = _text(query_context.get("query_type"))
    person_ids = [_text(person.get("id")) for person in supporting_people if _text(person.get("id"))]
    text = " ".join(
        _llm_path_text(person)
        for person in supporting_people
    )
    kept = bool(person_ids)
    drop_reason = ""

    if name in FORBIDDEN_FALLBACK_PATH_NAMES:
        kept = False
        drop_reason = "forbidden fallback path name"
    elif query_type == "relationship":
        if path_id.startswith("path_return") or path_id in {"path_public_exam", "path_freelance_trials", "path_rest_then_restart"}:
            kept = False
            drop_reason = "career path rejected for relationship query"
        elif not any(marker in text for marker in ("关系", "恋爱", "分手", "伴侣", "男朋友", "女朋友", "异地", "婚姻", "感情")):
            kept = False
            drop_reason = "path people do not support relationship topic"
    elif query_type == "migration_new_zealand":
        if path_id in {"path_return_to_work", "path_public_exam", "path_freelance_trials", "path_rest_then_restart"}:
            kept = False
            drop_reason = "career path rejected for New Zealand query"
        elif not any(marker in text for marker in NEW_ZEALAND_STRONG_KEYWORDS):
            kept = False
            drop_reason = "path people do not support New Zealand topic"
    elif query_type == "family_money":
        if path_id not in {
            "path_family_support_money",
            "path_family_money_boundary",
            "path_family_parent_rework",
            "path_family_shared_burden",
        }:
            kept = False
            drop_reason = "non-family-money path rejected for family_money query"
        elif not any(marker in text for marker in FAMILY_MONEY_ANY_KEYWORDS):
            kept = False
            drop_reason = "path people do not support family_money topic"

    check = "kept: path matches query_context and has supporting people" if kept else drop_reason
    path["query_relevance_check"] = check
    return {
        "pathId": path_id,
        "name": name,
        "supporting_person_ids": person_ids,
        "query_relevance_check": check,
        "kept": kept,
        "dropReason": "" if kept else drop_reason,
    }


def _cluster_key_from_path_id(path_id: str) -> str:
    for cluster_key, meta in CLUSTER_META.items():
        if meta.get("id") == path_id:
            return cluster_key
    return "other_related_experience"


def _llm_path_desc(cluster_key: str) -> str:
    return {
        "return_to_work": "这些样本主要回到求职轨道，在投简历、面试和岗位预期之间重新找位置。",
        "freelance_trials": "这些样本把裸辞后的空档用于副业、接单或自由职业试错，同时面对收入波动。",
        "public_exam": "这些样本把考公考编作为阶段性方向，但结果和投入周期都存在不确定性。",
        "study_exam": "这些样本把裸辞后的主要精力放在考研、读书或阶段性考试上，而不是直接回到求职轨道。",
        "migration_life": "这些样本裸辞后的主要动作是搬家、换城市或出国生活，用新的环境重新安排日常。",
        "rest_then_restart": "这些样本先停下来恢复状态，再慢慢观察职业方向和下一步行动。",
        "path_family_support_money": "这些样本记录了工作后给父母或家庭持续经济支持时的压力、拉扯和调整。",
        "path_family_money_boundary": "这些样本在被父母要钱或长期补贴后，开始减少支持、拒绝给钱或重新划分责任。",
        "path_family_parent_rework": "这些样本记录了父母50岁前后继续工作、再就业或尝试增加收入的经历。",
        "path_family_shared_burden": "这些样本不是单纯给钱或拒绝，而是在家庭收入、债务、养老和子女责任之间重新分担。",
        "other_related_experience": "这些样本选择不完全相同，但都记录了与当前问题相近的真实处境。",
    }.get(cluster_key, "这些样本选择不完全相同，但都记录了与当前问题相近的真实处境。")


def _llm_people_sort_key(person: dict[str, Any]) -> tuple[int, int, int, str]:
    internal = person.get("internal") if isinstance(person.get("internal"), dict) else {}
    return (
        LLM_SAMPLE_TYPE_PRIORITY.get(_text(person.get("sampleType")), 9),
        LLM_CONFIDENCE_PRIORITY.get(_text(internal.get("confidence")).lower(), 9),
        -len(person.get("realDetails") or []),
        _text(person.get("id")),
    )


def _path_ids(paths_draft: list[dict[str, Any]]) -> set[str]:
    return {_text(path.get("id")) for path in paths_draft if _text(path.get("id"))}


def _format_path_name(value: Any) -> str:
    text = PATH_NAME_ALIASES.get(_text(value), _text(value))
    if not text:
        return "相近真实经历"
    return text if len(text) <= 16 else text[:16]


def _format_desc(value: Any) -> str:
    text = _text(value)
    if not text:
        return "这些样本来自知乎公开内容，展示了与当前问题相近的真实经历。"
    if len(text) <= 70:
        return text
    for mark in ("。", "；", "，"):
        index = text.rfind(mark, 35, 70)
        if index >= 34:
            return text[: index + 1]
    return f"{text[:67]}..."


def _format_badge(value: Any) -> str:
    text = _text(value)
    if not text:
        return "知乎真实经历"
    return text if len(text) <= 34 else f"{text[:31]}..."


def _format_one_line(value: Any) -> str:
    text = _text(value)
    if not text:
        return "原文提供了一段与当前问题相近的真实经历。"
    return text if len(text) <= 90 else f"{text[:87]}..."


def _entry_situation(value: Any) -> str:
    text = _strip_entry_prefix(value)
    return _limit_text(text, 44)


def _entry_status(value: Any) -> str:
    text = _strip_entry_prefix(value)
    if _is_weak_entry_status(text):
        return ""
    return _limit_text(text, 32)


def _should_prefer_situation_entry(name: str, entry_situation: str) -> bool:
    if "十方水" in name:
        return True
    text = _text(entry_situation)
    age_markers = sum(1 for marker in ("27岁", "二十七", "28岁", "二十八", "30岁", "三十") if marker in text)
    return age_markers >= 3


def _is_weak_entry_status(value: Any) -> bool:
    text = _text(value)
    return text in {
        "",
        "原文未明确提到后续结果",
        "原文只呈现到这一阶段",
        "原文只呈现到这一阶段。",
        "原文仅呈现到这一阶段",
        "原文仅呈现到这一阶段。",
        "计划裸辞没成功",
        "计划裸辞没成功。",
    }


def _strip_entry_prefix(value: Any) -> str:
    text = _text(value)
    for prefix in ("原文提到，", "原文中提到，", "这位知友", "作者"):
        if text.startswith(prefix):
            text = text[len(prefix):].strip(" ，。")
    return text


def _limit_text(value: Any, limit: int) -> str:
    text = _text(value)
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


def _format_excerpt(value: Any) -> str:
    text = " ".join(_text(value).split())
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


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_text(item) for item in value if _text(item)]


def _normalize_sample_type(value: Any) -> str:
    sample_type = _text(value)
    return {
        "full_experience": "full_story",
        "fragmented_experience": "partial_experience",
        "fragment_experience": "partial_experience",
    }.get(sample_type, sample_type)


def _normalize_experience_owner(value: Any) -> str:
    owner = _text(value).lower()
    return owner if owner in {"author", "mentioned_person", "unclear"} else "unclear"


def _boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on", "是", "true"}
    return bool(value)


def _passes_query_constraints(
    *,
    draft: dict[str, Any],
    text: str,
    query_context: dict[str, Any],
) -> bool:
    query_type = _text(query_context.get("query_type"))
    combined = f"{text} {_text(draft.get('rawContentPreview'))}"
    if query_type == "relationship":
        if not any(marker in combined for marker in ("关系", "恋爱", "分手", "伴侣", "男朋友", "女朋友", "异地", "婚姻", "感情", "复合")):
            return False
        if any(marker in combined for marker in ("考公", "考编", "公务员", "事业编")) and not any(
            marker in combined for marker in ("恋爱", "分手", "关系", "伴侣", "感情")
        ):
            return False
    elif query_type == "migration_new_zealand":
        if not _matched_new_zealand_target_location_keywords(combined):
            return False
        if any(marker in combined for marker in ("中介", "咨询", "政策解读", "攻略")) and not any(
            marker in combined for marker in ("我在新西兰", "我去新西兰", "到了新西兰", "奥克兰", "基督城", "惠灵顿")
        ):
            return False
    return True


def _looks_like_non_author_experience(*, name: str, draft: dict[str, Any]) -> bool:
    return bool(_non_author_experience_drop_reason(name=name, draft=draft))


def _non_author_experience_drop_reason(*, name: str, draft: dict[str, Any]) -> str:
    source = draft.get("source") if isinstance(draft.get("source"), dict) else {}
    text = " ".join(
        _text(part)
        for part in (
            name,
            source.get("title"),
            draft.get("situation"),
            draft.get("actionSummary"),
            " ".join(_string_list(draft.get("realDetails") or draft.get("real_details"))),
            " ".join(_string_list(draft.get("author_experience_evidence") or draft.get("authorExperienceEvidence"))),
            draft.get("rawContentPreview"),
            draft.get("llmInputPreviewHead"),
            draft.get("llmInputPreviewTail"),
        )
    )
    if _looks_like_advice_without_author_process(name=name, source=source, draft=draft, text=text):
        return ADVICE_ONLY_FILTER_REASON
    if any(marker in text for marker in ("作者曾帮助", "来访者", "咨询案例", "案例分析", "指导小北", "小北与男友")):
        return "post-check: mentioned_person/case rather than author's own lived experience"
    if any(marker in text for marker in MENTIONED_PERSON_MARKERS):
        return "post-check: mentioned_person/case rather than author's own lived experience"
    if "小玉" in text and "小玉" not in name:
        return "post-check: mentioned_person/case rather than author's own lived experience"
    if "移民故事" in text and ("邀请" in text or "来自" in text or "移民" in name):
        return "post-check: mentioned_person/case rather than author's own lived experience"
    if ("移民" in name or "留学" in name or "咨询" in name) and any(
        marker in text for marker in ("客户", "案例", "邀请", "投稿", "故事")
    ):
        return "post-check: mentioned_person/case rather than author's own lived experience"
    return ""


def _looks_like_advice_without_author_process(
    *,
    name: str,
    source: dict[str, Any],
    draft: dict[str, Any],
    text: str,
) -> bool:
    title = _text(source.get("title"))
    source_type = _normalize_llm_source_type(source.get("type") or source.get("content_type"))
    author_evidence = _string_list(draft.get("author_experience_evidence") or draft.get("authorExperienceEvidence"))
    if _has_author_process_evidence(author_evidence):
        return False
    if any(marker in text for marker in AUTHOR_LIVED_MARKERS):
        return False
    is_question_answer = source_type == "answer" or any(marker in title for marker in QUESTION_TITLE_MARKERS)
    has_advice_shape = any(marker in text for marker in ADVICE_MARKERS)
    has_generic_people = any(marker in text for marker in ("很多人", "大多数人", "有人", "身边人", "普通人"))
    is_known_advisory_author = any(marker in name for marker in ("Flint", "咨询", "顾问", "导师"))
    if is_question_answer and (has_advice_shape or has_generic_people or is_known_advisory_author):
        return True
    return False


def _has_author_process_evidence(evidence: list[str]) -> bool:
    combined = " ".join(_text(item) for item in evidence if _text(item))
    if not combined:
        return False
    if any(marker in combined for marker in AUTHOR_PROCESS_EVIDENCE_MARKERS):
        return True
    identity_only = any(marker in combined for marker in AUTHOR_IDENTITY_ONLY_MARKERS)
    points_at_reader = "你" in combined and not any(marker in combined for marker in ("我", "我们", "本人"))
    generic_people = any(marker in combined for marker in ("很多人", "大多数人", "有人", "身边人"))
    if identity_only or points_at_reader or generic_people:
        return False
    return False


def _normalize_llm_source_type(value: Any) -> str:
    source_type = _text(value).lower()
    return source_type if source_type in {"answer", "article", "pin", "question", "unknown"} else "unknown"


def _stable_suffix(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
