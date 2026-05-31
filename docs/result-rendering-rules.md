# 结果页展示规则

## 路径展示规则

- paths.length >= 2：展示路径页，用户先选路径。
- paths.length === 1 && people.length > 1：跳过路径页，直接进入该路径的人物样本墙。
- paths.length === 1 && people.length === 1：跳过路径页和选人步骤，直接展示唯一人物卡。
- paths.length === 0 && people.length > 0：不生成假路径，直接展示人物样本墙。
- paths.length === 0 && people.length === 0：展示低召回提示。
- 不展示“其他相近真实经历 / 其他路径 / 相关经历”这类兜底路径。

## 人物样本墙规则

- 当前可选人物数 > 1 时，显示“先选一个人，看看 TA 的经历”。
- 当前可选人物数 <= 1 时，不显示选择引导文案。
- 多人路径不默认选人。
- 单人路径可以默认选中唯一人物并展开人物卡。
- 人物入口卡只展示：头像、昵称、entrySituation、entryStatus。
- 不在入口卡展示 actionSummary、realDetails、source.title、按钮、匹配原因。

## 人物卡规则

当前新版人物卡结构固定为：

- TA 的处境
- TA 做了什么
- TA 提到的细节
- 现在走到哪一步
- TA 的真实经历
- 向 TA 提问
- 存入我的样本库

禁止恢复旧模块：

- TA 是谁
- 为什么匹配到 TA
- TA 的经历时间线

## 字段降级规则

- entrySituation = 起点 / 困境 / 关键约束，不超过 45 字。
- entryStatus = 原文最后走到哪一步；没有明确结果时返回空字符串，前端隐藏。
- currentStatus 没有明确结果时可以为空，不要硬写“原文未明确提到后续结果”。
- timeline 只有原文有明确时间顺序时才展示。
- key_fragments / realDetails 用于展示真实片段。
