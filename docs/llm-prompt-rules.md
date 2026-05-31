# LLM 使用边界

## 不需要 LLM 的事情

用代码规则处理：

- paths.length / people.length 判断
- 是否展示路径页
- 是否展示人物样本墙
- 是否展示“先选一个人”
- source.url 校验
- 空结果 / 低召回兜底
- 前端布局和 CSS
- 固定文案从文案库读取
- 单路径 / 单人物降级
- 当前人物入口卡是否高亮

## 需要 LLM 的事情

用 LLM 或后端语义理解处理：

- query 理解
- clarification 影响 query_context
- loading 动态变量
- 搜索线索生成
- 判断是否作者本人亲历
- sample_type 判断
- path.name / path.desc 表达
- path 与 query / clarification 是否一致
- people 是否真的支撑 path
- entrySituation / entryStatus
- AI 分身回答

## LLM 抽取硬规则

- 只能基于 rawText / title / source 信息。
- 不允许编造年龄、职业、城市、收入、结果、时间线。
- 作者本人亲历才能进入正式 people。
- mentioned_person / unclear / 纯观点 / 攻略 / 机构号 / 别人故事不进入正式 people。
- source.url 缺失不进入正式 people。
- sampleType 统一为：
  - full_story
  - partial_experience
  - opinion_with_experience
- 正式 people 默认只展示 full_story / partial_experience。
- opinion_with_experience 进入 debug，不进入正式 people。

### valid person 与 query 前提状态

如果 query 是“X后怎么办 / X之后怎么办 / X后怎么生活”，正式 person 必须已经进入 X 之后的状态。

- 对 `30岁裸辞后怎么办`，正式 person 必须明确已经裸辞、已离职、待业、无工作、离职后重新找工作、离职后休整、离职后换城市等。
- 如果只是提离职、交接中、计划裸辞、想裸辞、离职未完成、离职日期未定，不能作为正式 person。
- 这类候选返回 `can_be_person_sample=false`，或在正式过滤阶段剔除。
- `filter_reason` 写 `not yet entered query premise state`。
- 这类内容可以留在 debug candidate，但不能作为正式 people，也不能进入 path clustering。
- 正式过滤阶段不能只机械相信 `not yet entered query premise state`。如果结构化字段中出现“裸辞两年 / 已裸辞 / 裸辞后 / 已离职 / 离职后 / 辞职后 / 待业 / 失业后 / 裸辞后尝试创业 / 辞职后一直休息”等强后置状态证据，可以记录 `rescued_by_post_premise_evidence` 并进入后续路径分配。
- 如果结构化字段只有“准备裸辞 / 想裸辞 / 提出离职 / 尚未正式离职 / 未开始交接 / 离职日期未定 / 交接中”等前置阶段证据，仍然过滤为 `not_yet_entered_query_premise_state`。
- 如果正反证据同时出现，优先看是否已有明确“已裸辞 / 已离职 / 裸辞后 / 辞职后”等后置状态；只有明确仍未进入后置状态时才过滤。
- formal filter 的 query premise guard 要按字段仲裁：`currentStatus / entryStatus` 中的明确后置结果优先保留，明确前置未完成状态优先过滤；`actionSummary` 里只有“裸辞后顺利找到新工作 / 辞职后一直休息 / 已经裸辞 / 裸辞两年”等明确后置动作或结果可以 rescue。
- “离职后 / 裸辞 / 辞职 / 岗位 / 工作”等弱词不能单独作为 rescue 证据，避免把提出离职、交接未完成、仍在原工作的人放进 valid people。

### 结构化经历字段反证

formal valid people filter 不能只相信 LLM 给出的 advice / weak 类 `filter_reason`。当 `filter_reason` 是 `advice/commentary without author journey`、`answer/advice without author's own lived experience` 或 `weak first-person mention without concrete lived process` 时，可以用结构化经历字段做二次判定。

允许 rescue 的最低条件：

- `source.url` 存在。
- `experience_owner=author`，或 `is_first_person_experience=true`。
- `situation` 非空。
- `actionSummary` 非空，且能看到作者自己的行动。
- `currentStatus`、`entryStatus` 或 `hasOutcome=true` 至少一个成立。
- `situation` 或 `actionSummary` 命中 query 前提后的实际行动，例如裸辞后、辞职后、离职后、待业、面试、找工作、入职、创业、自由职业、换城市、回老家。

被 rescue 的样本在 debug 中记录 `rescued_by_structured_experience_fields`。但 source 缺失、`experience_owner=mentioned_person`、机构/客户案例、纯观点无行动、与 queryContext 明显不一致、尚未进入 query 前提状态，仍然必须过滤。

### family_money 作者经济互动

family_money query 中，父母 / 父亲 / 母亲是经济互动对象，不默认等于 mentioned_person。

- 当作者本人在 `situation`、`actionSummary`、`currentStatus`、`entrySituation`、`entryStatus` 中出现给父母钱、给生活费或红包、转账、父母向我/作者要钱、帮父母还债、减少给款、停止给钱、固定金额支持、因钱和父母争执等动作时，应按作者本人亲历处理。
- 如果 post-check 误判为 `mentioned_person/case rather than author's own lived experience`，但结构化字段能证明作者本人参与了父母金钱互动，可以 rescue，并记录 `rescued_by_family_money_author_interaction`。
- 如果候选被误判为 advice/commentary，但结构化字段明确出现“父母开口要钱 / 父亲或母亲向我要钱 / 作者转账几千元 / 给了钱”等临时转账或应急支持过程，可以作为 `partial_experience` rescue，并记录 `rescued_by_family_money_transfer_interaction`。
- family_money 片段经历不强制要求 `currentStatus` 非空；明确的金额、转账、红包、给钱、停止给钱等动作可以支撑 `partial_experience`。
- 主要讲父母照顾作者、带孩子、做家务，但没有父母要钱、作者给钱或家庭经济支持动作，应过滤为 `family_money_subject_mismatch`。
- 机构案例、客户案例、采访转载、朋友同事故事、纯建议或理财观点仍然必须过滤。

### migration_new_zealand 目标地点一致性

地点迁移类 query 必须保持目标地点一致。对 `migration_new_zealand`，泛机制词不能替代新西兰证据。

- 正式 people 必须有明确新西兰目标地证据，例如新西兰、奥克兰、基督城、惠灵顿、皇后镇、去新西兰、在新西兰、新西兰 WHV、新西兰打工度假、新西兰留学、新西兰工签、新西兰生活、从新西兰回来。
- 只有 WHV、打工度假、留学、工签、移民、旅居等泛机制词，但没有新西兰目标地证据，不能进入正式 people。
- 澳洲、澳大利亚、加拿大、英国、日本、欧洲、美国、新加坡、爱尔兰等非目标地内容，如果没有明确新西兰经历，过滤为 `migration_target_location_mismatch`。
- 新西兰短期旅行、旅游攻略、亲子插班、带孩子短期游学、朋友/客户/孩子故事、纯政策攻略仍然必须过滤。
- “孩子 / 朋友”如果只是作者迁移动机、家庭背景或正文顺带提及，不单独构成主体错配；亲子插班、带孩子游学、朋友一家/朋友故事、孩子本人经历仍然过滤。
- 明确准备新西兰但尚未出发的作者本人经历可以进入“准备过但最终没去”；前提是目标地明确是新西兰。
- 如果结构化字段能证明作者本人有新西兰迁移或生活过程，例如移居新西兰、搬到/搬去/搬新西兰、搬到奥克兰、在新西兰奥克兰生活、在新西兰工作、拿到新西兰工作 offer、新西兰工作offer、落地基督城、新西兰 WHV、新西兰打工度假、从新西兰回来，可以反证 `mentioned_person/case` 或 `experience subject mismatch`，并记录 `rescued_by_migration_author_journey`。
- 如果 migration rescue 没有发生，debug 需要给出 `migration_rescue_blocked_reason`，用于判断是 hard negative、缺少作者旅程证据、缺少目标地正证据，还是 reason 本身不可 rescue。

## query 多样性回归

后续修改如影响后端逻辑、路径、LLM prompt，至少考虑这些类型：

1. 职业选择
2. 裸辞 / 失业
3. 关系困扰
4. 家庭压力
5. 城市 / 国家迁移
6. 高考志愿
7. 读研 / 转专业
8. 赚钱焦虑
9. 泛化迷茫问题

## 路径聚类规则

路径聚类用于后续旁路测试阶段：`valid people → LLM 聚类 paths → 规则校验 → 再进入正式结果`。当前规则只为 prompt 准备，不替换正式 `paths / people`，也不接入主链路。

### 路径定义

路径 = 一组人在相似起点 / 相似问题下，实际走过的主要做法或去向。

- 路径只能来自已经通过真实性过滤的 valid people。
- 不能先根据 query 预设路径，再把 personIds 塞进去。
- 不能补充不存在的人物、经历、结果。
- 没有人支撑的路径不要生成。
- 不硬凑路径；如果结果少，可以返回 1 条路径，甚至只走单人兜底。
- 路径优先描述“他们怎么做 / 怎么过去 / 怎么选择”，不要描述“他们是什么类型的人”。

### 核心动作方向

路径必须对齐用户问句里的核心动作方向。

- 对“怎么办 / 之后怎么办 / 要不要 / 怎么选择”类 query，path 必须描述用户问题发生后的实际行动、选择方向、进入机制、处理方式或阶段去向。
- 不要把“导致问题发生的原因 / 背景约束 / 生活事件 / 情绪状态 / 现实压力”包装成 path。
- 起因和约束只能出现在 `desc`、`shared_evidence` 或 `weakness` 里，不能单独成为 `path.name`。
- 除非用户明确问的是“为什么会这样 / 原因是什么”，否则原因型聚类不应成为 path。

query: `30岁裸辞后怎么办`

坏 path：

- 生活事件中断职业计划
- 因家庭原因裸辞
- 因健康问题暂停工作

原因：这些是裸辞或职业中断的背景/起因，不是裸辞之后的走法。

好 path：

- 裸辞后重新找工作
- 先休整再重新开始
- 转向考公考编
- 尝试自由职业
- 降低预期先就业

query: `出来工作后，父母要求给他们钱怎么办`

坏 path：

- 父母收入不足
- 家庭经济压力大

原因：这是背景，不是子女处理方式。

好 path：

- 持续给家庭经济支持
- 重新设定给钱边界
- 按固定金额支持
- 和父母协商分担方式

### 前提状态继承

路径必须继承用户 query 已经设定的前提状态。

- 如果 query 已经说“裸辞后 / 失业后 / 分手后 / 毕业后 / 工作后”，path 必须描述这个状态之后的行动、选择、处理方式或阶段去向。
- 不要把发生在该状态之前的“意向、准备、犹豫、交接、尚未完成、还没真正发生”的阶段包装成 path。
- 前置阶段可以放入 `unassignedPersonIds.reason`、`weakness`、`shared_evidence` 或人物卡字段，但不能单独成为 `path.name`。
- 如果某个 person 还没有真正进入 query 所描述的前提状态，应优先放入 `unassignedPersonIds`，reason 写明“尚未进入 query 所要求的状态”。
- 如果输入 people 很少，宁可少生成 path，也不要把前置阶段硬包装成路径。
- 如果 3 个 people 里只有 2 个真正符合 query 前提状态，只用这 2 个聚类，剩下 1 个进入 `unassignedPersonIds`。

query: `30岁裸辞后怎么办`

坏 path：

- 裸辞后交接未完成继续工作
- 提出离职继续工作交接
- 决定裸辞但还没离开
- 想裸辞但没成功
- 离职日期未定

原因：这些是裸辞前 / 离职未完成 / 意向阶段，不是裸辞后的走法。

好 path：

- 裸辞后重新找工作
- 先休整再重新开始
- 转向考公考编
- 尝试自由职业
- 降低预期先就业
- 搬家后重新找工作

### 主动选择优先

路径名必须抽取人物的主动选择 / 主要走法，不抽外部偶发事件、环境遭遇或突发阻碍。

- 如果人物经历是“裸辞后搬家，后来遇到疫情封控”，path 应命名为 `裸辞后换城市生活`、`搬家后重新开始` 或 `裸辞后回老家调整`。
- 不应命名为 `搬家定居遇疫情封控` 或 `疫情影响计划`。
- 外部事件只能进入 `desc`、`shared_evidence`、`weakness` 或 `realDetails`。
- 外部事件可以作为代价、约束、经历细节出现，但不能成为 `path.name` 的核心。

### cluster_axis

每次聚类必须选择一个主要聚类维度 `cluster_axis`，并尽量让所有路径使用同一主维度。

可选值：

- `action_strategy`：行动路径 / 处理方式 / 实际做法
- `access_mechanism`：进入机制 / 实现方式 / 到达路径
- `choice_direction`：选择方向 / 取舍方向
- `current_stage`：当前阶段 / 进展状态
- `constraint_context`：关键约束 / 现实条件
- `outcome_direction`：结果走向

query 类型优先级：

- 职业、裸辞、关系、家庭经济类问题，优先使用 `action_strategy`。
- 迁移、留学、去某国生活类问题，优先使用 `access_mechanism`。
- 高考志愿、专业选择、读研择校类问题，优先使用 `choice_direction`。
- 只有当 people 的主要差异确实在结果上，才使用 `outcome_direction`。

允许“主维度 + 最多 1 条辅助路径”。辅助路径必须和 query 强相关，不能命名为“其他相关经历 / 其他路径 / 相近经历”等垃圾桶路径；如果使用辅助路径，必须在 `axis_reason` 或 `axis_risks` 中说明原因。

### 路径命名

路径名要像用户能一眼看懂的真实走法：

- 使用短句，不超过 12 个中文字符，特殊情况最多 16 个。
- 优先使用“动作 + 方向/选择结果”的结构。
- 不用人格标签、价值判断或 AI 味分类。
- 不写成建议句。

禁止路径名：

- 理性规划型
- 勇敢尝试型
- 自我成长型
- 稳定回归型
- 寻找意义型
- 突破自我型
- 积极面对型
- 阶段性探索型
- 最优选择路径
- 其他相关经历

好路径名示例：

- 裸辞后重新找工作
- 先休整再重新开始
- 尝试副业和自由职业
- 决定分开
- 继续沟通修复
- 用 WHV 先去试生活
- 通过留学进入新西兰
- 靠远程收入旅居
- 持续给家庭经济支持
- 重新设定给钱边界
- 优先城市和平台
- 转向相近专业
- 跨专业考研上岸

### desc 文案

`desc` 要解释“这组人共同做了什么”。

- 必须包含具体行动、进入方式、现实约束或阶段结果。
- 不写“提供参考 / 帮助理解 / 具有启发 / 值得借鉴 / 适合你看”。
- 不写建议，不鸡汤。
- 优先使用“他们……”或“这组人……”开头，像真实经历总结，不像 AI 分析报告。

好 desc：

- 他们裸辞后回到求职轨道，在投简历、面试和岗位预期之间重新找位置。
- 他们先停下来恢复状态，再慢慢观察职业方向和下一步行动。
- 他们通过 WHV 或打工度假进入新西兰，在真实工作和生活成本中试探适配度。
- 他们持续给父母或家庭经济支持，同时记录了压力、拉扯和调整。

坏 desc：

- 这些样本具有很强参考价值，可以帮助用户理解不同选择。
- 他们积极面对挑战，最终找到了自己的方向。
- 该路径体现了理性规划和自我成长。

### 分配规则

- `shared_evidence` 必须绑定 `personId`，不能只写泛化总结。
- 同一个 person 只能进入一个 path。
- 如果一个人同时符合多个路径，选择最能回应 query 的主路径。
- 无法归类的人放入 `unassignedPersonIds`，并说明原因。
- 不能只因为情绪相似、年龄相似、问题相似就生成路径。
- “都很迷茫”“都很焦虑”“都是30岁”不能单独成为路径。

数量规则：

- 1 个有效人物：允许返回 1 条弱路径，也可以返回 0 条 paths，并放入 `singlePersonFallbackPersonIds`。
- 2-3 个有效人物：通常 1-2 条路径。
- 4-8 个有效人物：通常 2-4 条路径。
- 如果差异很弱，优先合并；如果都是碎片经历，不硬拆复杂路径。

### JSON schema

```json
{
  "cluster_axis": "action_strategy | access_mechanism | choice_direction | current_stage | constraint_context | outcome_direction",
  "axis_reason": "",
  "axis_risks": "",
  "paths": [
    {
      "id": "path_xxx",
      "name": "",
      "desc": "",
      "personIds": [],
      "query_relevance_check": "",
      "shared_evidence": [
        {
          "personId": "",
          "evidence": ""
        }
      ],
      "confidence": "high | medium | low",
      "weakness": ""
    }
  ],
  "unassignedPersonIds": [
    {
      "personId": "",
      "reason": ""
    }
  ],
  "singlePersonFallbackPersonIds": []
}
```

字段要求：

- `id` 使用英文小写 snake_case，以 `path_` 开头。
- `name` 是前端展示路径名。
- `desc` 是前端展示的一句话解释。
- `personIds` 必须来自输入 people。
- `query_relevance_check` 必须说明这条路径由哪些 people 的共同事实归纳出来，以及这个共同事实为什么回应本轮 query。
- `shared_evidence` 必须绑定 `personId`。
- `confidence` 表示路径聚类是否可靠。
- `weakness` 写证据不足或维度不稳的地方；没有则写空字符串。
- `unassignedPersonIds` 必须说明未归类原因。
- `singlePersonFallbackPersonIds` 用于只有一个有效人物、不适合硬生成群体路径的情况。

### 常见 query 约束

- 关系困扰：路径围绕关系中的实际处理方式，例如决定分开、继续沟通修复、暂停关系重新观察、复盘自己的关系模式；不能生成职业路径。
- 新西兰生活：优先按进入机制分，例如 WHV、留学、工作机会、远程收入、去了又回来；不要混用“进入方式”和“最终结果”，除非作为最多 1 条辅助路径。
- 家庭给钱：不能写承担型、边界型等人格标签；要写持续给家庭经济支持、重新设定给钱边界等实际做法。
- 父母再就业：如果是作者本人记录“我父母50多岁后怎么挣钱/再就业”的家庭亲历，可以保留；采访、转载、机构案例、别人故事不应作为 valid people 进入聚类。
- 高考志愿：不能生成“推荐计算机 / 推荐医学”等专业建议路径；只有 people 中有真实选择和后续体验时，才能按 `choice_direction` 聚类。
- 跨专业考研：路径围绕真实跨考方式、准备过程、是否上岸、是否转向相近专业；不要写成“努力提升型”。

### 自检规则

生成前检查：

1. 每条 path 是否有 personIds 支撑。
2. 是否有同一个 personId 出现在多个 path。
3. path.name 是否是实际走法，而不是人格标签。
4. desc 是否像真实经历总结，而不是 AI 分析。
5. 所有路径是否尽量使用同一 cluster_axis。
6. 是否出现没有证据的路径。
7. 是否为了凑数量硬拆。
8. 是否把纯情绪、年龄、泛泛问题相似包装成路径。

### 旁路 debug 字段

LLM path clustering 旁路接入阶段只输出 debug，不替换正式 `paths / people`。正式结果仍由现有规则链路决定。

debug 字段：

- `pathGenerationMode`: 固定为 `rule_based_with_llm_cluster_debug`。
- `llmClusterInputPeopleCount`: 本次送入 LLM path clustering 的 valid people 数。
- `llmClusterPathsRaw`: LLM 返回的原始 JSON object；解析失败时为空对象。
- `llmClusterValidationDebug`: 基础规则校验记录，包括 warning / error / info。
- `droppedClusterPaths`: 被基础校验丢弃的 LLM cluster paths。
- `ruleFallbackUsed`: 当前正式结果是否使用规则 fallback。

基础校验不影响正式结果：

- `path.personIds` 必须都存在于 valid people。
- 同一个 `personId` 不能出现在多个 path。
- 没有 `personIds` 的 path 丢弃。
- `shared_evidence` 必须绑定有效 `personId`。
- `path.name` 命中禁止词时标记 dropped 或 warning。
- `path.name` 命中“疫情 / 封控 / 意外 / 家里出事 / offer 被取消 / 生病”等外部事件词时，标记 `external_event_used_as_path_name`；如果还有可恢复的主动选择表达，只 warning；如果整个路径名只有外部事件，没有主动选择，则进入 `droppedClusterPaths`。
- `desc` 命中“提供参考 / 帮助理解 / 具有启发 / 值得借鉴 / 适合你看”等 AI 味表达时标记 warning。
- LLM JSON 解析失败时，只在 debug 标记失败，不影响正式 `paths / people`。
