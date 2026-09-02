---
name: boss-job-hunter
description: >-
  Boss直聘求职流水线：Agent 采集岗位（搜索 / 收藏两条通道）→ ABC 匹配评分（硬性要求防误判封顶）→
  生成打招呼语三变体 → 写入飞书多维表格（两表唯一 SSOT，写前去重）→ 收尾对账小结。
  永不代发消息，结果止步于「待发送」状态，由用户自己发送。
  Use for Boss直聘, 找工作, 岗位采集, 抓取Boss, JD评估, JD匹配, 打分, 匹配度,
  这个岗位怎么样, 打招呼语, 写飞书表格, 收藏岗位分析, 批量评估, 待发送, 当日小结, 跑一轮.
  不支持自动投递/代发；本 skill 不内置爬虫，采集由 Agent 按 references/collection-guide.md 亲自执行。
---

# Boss Job Hunter（Boss直聘求职流水线）

帮求职者把 Boss直聘上的岗位变成飞书多维表格里可管理的投递记录：采集 → 评分 → 打招呼语 → 落表 → 对账。**只准备、永不发送**。

## 铁律

1. **永不代发**：任何情况下不点击「立即沟通/发送」，不代用户发出任何消息；产出止步于表中「投递状态=待发送」，由用户自己在 Boss 端发送
2. **采集只读**：浏览岗位时严禁点击「立即沟通 / 发送 / 收藏 / 投递」等任何按钮；**不要用宿主内置浏览器打开 zhipin.com**——一律用独立 Chrome 进程
3. **两表唯一 SSOT**：飞书多维表格是投递记录唯一事实源；写入前必须两表去重（流程见 `references/lark-tables.md`）
4. **规则唯一来源**：评分逻辑只在 `references/scoring.md`，打招呼语格式只在 `references/greeting.md`——本文与其余文档只引用、永不复述
5. **风控即停**：出现验证码 / 安全验证页 / 403 / code=37 等信号 → 终止本轮不重试（识别与恢复见 `references/collection-guide.md` §风控）

## 首次配置（bootstrap）

触发条件：工作目录不存在或缺 `config.yaml`（默认工作目录 `~/boss-job-hunter/`）。
按 `references/lark-tables.md` §首跑 bootstrap 引导完成：建工作目录 → 填 profile 与 config → 安装 lark-cli 与 lark skills（两步都要装）→ 自动建 Base 和两张表 → 回填 token/id → 存删一条测试记录验证。未完成前不要执行采集或写表。

## 四个模式

| 模式 | 用户说 | 流程 |
|------|--------|------|
| **score** | 「这个岗位怎么样」「帮我评这条JD」（+ 一条 JD 文本/链接内容） | 单条评分 → 结构化结果，对话中展示 |
| **hunt** | 「跑一轮」「搜一波XX岗」（关键词/城市可选） | 搜索采集 → 逐条评估 → 去重 → 写主表 → 对账 |
| **favorites** | 「处理我的收藏」「跑收藏轮」 | 收藏列表采集 → 全等级入收藏表 → 对账 |
| **status** | 「今天情况怎么样」「来个小结」 | 统计当日两表数据，输出小结 |

各模式 checklist 见 `references/modes-playbook.md`。

### score（单条评估）

1. 读工作目录 `profile.md` + 简历事实（事实只能来自这些文件，禁止编造）
2. 按 `references/scoring.md` 完成：硬性要求抽取 → 维度打分 → 封顶 → 分级
3. B 级以上产出完整结构化结果（含打招呼语、HR 模拟、简历建议）；C 级只给 🚫 原因
4. 结束在对话展示，等用户决定；**不主动写表**——想入库让用户改用 hunt/favorites 或明说

### hunt（搜索采集）

1. 读 `config.yaml`；若启用每日目标且当日已达标 → 只出 status 小结并建议停止（风控安全阀）
2. 确定关键词与城市（用户给的优先，否则从 `keywords.pool` 选并与用户确认）；避免连续多轮同一组合
3. 按 `references/collection-guide.md` 的 prompt 模板采集搜索结果，产出 `out/search-<时间戳>.json`
4. 逐条走 score 流程（`jd` 为空的条目跳过并在小结说明）；B 级以上生成打招呼语前先做变体轮换检查（`references/lark-tables.md` §变体轮换检查）
5. 两表去重后 B 级以上全部入**主表**（无薪资分流）；C 级不入表，原因记入小结
6. 收尾对账 + 小结

### favorites（收藏采集）

1. 先拉两表已有「公司|岗位」清单作为跳过清单，减少对已处理条目的重复访问
2. 按 `references/collection-guide.md` 采集用户的 Boss「收藏/感兴趣」列表，产出 `out/favorites-<时间戳>.json`
3. 只处理收藏列表，不执行搜索抓取；薪资、城市不作排除条件（用户主动收藏的）
4. 逐条评估后**全等级入收藏表**：C 级 → 投递状态=不合适、不生成打招呼语；A/B 级正常（A 级附简历建议）
5. 收尾对账 + 小结

### status（当日小结）

拉两表当日记录（按「评估日期」过滤），输出 Markdown 小结：新增数 / A·B·C 分布 / 待发送数。仅供参考与决策，不做任何抓取和写入。

## 数据契约

所有模式的采集产物统一为 JSON 文件（顶层 `source/keyword/city/fetchedAt/riskInterrupted/jobs`，每条 job 含 `company/title/salary/link/jd` 等字段）。字段定义与合法性检查见 `references/collection-guide.md` §输入契约——无论用什么方式采集，最终必须长这样。

## 何时读哪个 reference

| 文件 | 何时读 |
|------|--------|
| `references/lark-tables.md` | 首次配置；任何建表 / 写表 / 查重 / 变体检查之前 |
| `references/collection-guide.md` | hunt / favorites 采集前；脚本或浏览器操作异常时 |
| `references/scoring.md` | 每条 JD 评估前（评分真身，含打分卡 schema 与结果模板） |
| `references/greeting.md` | 生成打招呼语前（格式真身：三变体、长度、CTA 池、反模式） |
| `references/modes-playbook.md` | 各模式开始（checklist）与收尾（对账格式） |

## 安全边界

- 本 skill **永不**发送消息、提交表单、点击任何有副作用的页面按钮
- 私密文件（`config.yaml`、`profile.md`、简历）只放个人工作目录，不入任何 git
- 未经用户明确确认，不做超出当前指令的批量动作
