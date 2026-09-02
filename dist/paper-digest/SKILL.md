---
name: paper-digest
description: >-
  将论文、arXiv、PDF、技术博客或公众号文章整理成一份分档阅读文档：概述档给概述与结构图，粗读档追加论证链，精读档给完整中文图文正文并在需要视觉辅助的位置插入原图、Excalidraw 图表或生成示意图。当用户说“看看这篇”“概述/粗读/精读这篇”“判断值不值得读”“翻译成图文版”或提供文章 URL、PDF、正文让 Agent 阅读消化时使用。
---

# Paper Digest

把一篇文章变成一个阅读入口，而不是一组报告文件。

## 交付契约

每篇文章创建 `<output_dir>/<slug>/`，只提供一个面向读者的 `paper.md`：

| 档位 | `paper.md` 必须包含 | 必须排除 |
|---|---|---|
| `overview` | 溯源信息、概述、结构图 | 粗读、完整正文、节级插图 |
| `skim` | 概述档全部内容、粗读 | 完整正文、节级插图 |
| `deep-read` | 概述档全部内容、完整中文图文正文 | 粗读 |

始终保留 `source.md`。不要生成 `verdict.md`、`digest.md`、`deep-read.md` 或 `translation.md`。模板见 `assets/templates/paper.md`。

## 配置与画像

按顺序读取：

1. 当前工作目录 `.paper-digest/EXTEND.md`；
2. `~/.paper-digest/EXTEND.md`；
3. 当前对话和工作区上下文；
4. 自动选档仍缺少关键信息时，按 `references/profile-resolution.md` 询问最小画像问卷。

不要为了显式档位请求阻塞式收集画像。字段与旧配置兼容规则见 `references/preferences-schema.md`。

## 工作流

### 1. 抽取并验证原文

把 URL、PDF 或粘贴文本整理为 `<output_dir>/<slug>/source.md`。

- URL：优先抓渲染后正文；去掉导航、广告和页脚。
- arXiv：优先 HTML / 导出正文，摘要页不足以支撑粗读或精读。
- PDF：依次尝试运行时原生读取、`python3 scripts/extract.py <pdf> --output <source.md>`、`pdftotext`。
- 粘贴文本：保留标题层级、公式、表格、图注、引用编号与重要脚注。

记录抽取完整性：

- `overview`：正文足以识别主题与结论即可；不完整时在 `paper.md` 标明。
- `skim`：必须包含主要章节、核心论证与结论。
- `deep-read`：必须是完整正文。登录墙、扫描失败、缺页或截断时暂停，请用户补充来源；不要静默降档或伪造缺失内容。

### 2. 选择档位

用户明确说“概述 / 快速了解”“粗读 / 速读”“精读 / 全文翻译 / 图文版”时直接采用相应档位，且不显示系统选档理由。

只有模糊请求才结合文章质量与画像相关度自动选择：

| 条件 | 档位 |
|---|---|
| 相关度低，或质量 / 证据明显弱 | `overview` |
| 有一定价值，但不是画像核心，或证据强度一般 | `skim` |
| 高度相关，且新颖性、证据强度、实际价值都强 | `deep-read` |

应用 `max_auto_depth` 上限；默认允许到 `deep-read`。该上限不限制用户明确指定的档位。自动选择时在概述开头写两行“阅读建议 + 原因”，不要另建判断文件。

### 3. 分析文章

只基于 `source.md` 提取：

- 元数据：标题、作者、原文入口、发布日期；
- 论证骨架：问题 → 主张 / 方法 → 证据 → 结论 / 局限；
- 质量信号：新颖性、证据强度、适用范围、可复现性；
- 画像相关点：与兴趣、背景和当前目标的关系；
- 原图清单与视觉辅助候选位置。

### 4. 预检视觉能力

任何档位都需要结构图；`deep-read` 还可能需要节级 Excalidraw 或生成示意图。先检查当前 Agent 是否具有对应 Skill、工具或原生能力。

缺少能力时：

1. 优先使用 `find-skills`；若没有，则用宿主的联网 / 搜索能力自主寻找候选；
2. 核对候选来源、能力与输出格式，只推荐一个最匹配选项；
3. 说明安装范围、权限和对本次结果的影响，获得用户授权后才安装；
4. 不静默下载、覆盖或升级 Skill，不要求用户在对话中粘贴 token；
5. 安装后若当前上下文不能立即使用，提示用户继续或重新执行；
6. 用户不安装时继续可完成的文字工作，保存缺失图片的视觉 brief，不插入不存在的图片链接，也不把场景插画强行改成流程图。

### 5. 生成概述和结构图

概述控制在约一分钟阅读量，说明文章解决的问题、核心结论和价值边界。

无论档位如何，都生成：

- `figures/prompts/00-structure.md`；
- `figures/00-structure.excalidraw`；
- `figures/00-structure.png`；
- `paper.md` 概述之后的 `![文章结构图](./figures/00-structure.png)`。

结构图解释论证骨架，不是章节目录。用可用的 Excalidraw companion 完成生成、渲染、查看和修正循环。详细路由与 brief 规范见 `references/illustration-design-guide.md`。

### 6. 按档位写正文

#### `overview`

写到结构图结束即停止。不要预生成粗读、全文翻译或节级插图。

#### `skim`

在结构图后追加约五至十分钟的粗读，不逐章复述。固定回答：

1. 文章解决什么问题；
2. 核心观点或结论；
3. 使用什么方法；
4. 最关键的证据；
5. 论证如何成立；
6. 局限与可能的问题；
7. 对当前用户有什么价值；
8. 是否值得精读，以及原因。

不要生成完整正文或节级插图。

#### `deep-read`

结构图后直接放完整中文图文正文，不包含粗读：

- 中文原文保持原样；外文做忠实、通顺的完整翻译；
- 保留标题层级、叙事顺序、段落、公式、表格、引用编号和重要脚注；
- 不摘要、不缩写、不重组，不加入未标记的讲解；
- 专业术语首次出现写“中文（English term）”，之后使用中文；
- 代码、API、模型名和变量名不翻译；不确定的专名保留原文；
- 外文精读在文首写“AI 翻译，请以原文为准”。

长文章按章节推进并保存进度；中断后从未完成章节继续。未完成时明确标记“部分完成”，不能报告成功。

### 7. 视觉增强精读正文

按 `references/illustration-design-guide.md` 执行“识别位置 → 路由 → 保存 brief → 生成 → 视觉检查 → 原位插入”：

1. 原文已有且清晰的图：提取并放回对应位置，保留编号、图注和来源。
2. 原图难读：先放原图，再放中文重绘；重绘图注写“依据原图重绘，请以原图为准”。
3. 流程、机制、因果、架构、层级、时间线和对比：使用 Excalidraw，交付 `.excalidraw + .png`。
4. 场景、概念隐喻和抽象意象：使用原生生图或生图 Skill，图注标明“示意图”。
5. 数据、实验结果、系统架构、过程和因果不得用自由生图表达。
6. 不按章节凑图；`visual_density` 是上限，不是配额。

每张新增视觉都先保存 `figures/prompts/<NN-topic>.md`。生成失败只重试失败项；最终失败则保留 brief，在对话说明缺项，正文不留破损链接。

### 8. 更新与升档

若该文章已有工作区，更新原来的 `paper.md`，不要创建第二份阅读入口：

- `overview → skim`：保留概述和结构图，追加粗读；
- `overview → deep-read`：保留概述和结构图，追加完整中文图文正文；
- `skim → deep-read`：删除粗读，保留概述和结构图，写入完整中文图文正文。

复用 `source.md`、结构图和已验证的原图；只生成差额内容。

### 9. 验证并回报

完成前运行：

```bash
python3 scripts/validate_output.py <output-folder>
```

再人工检查：

- `paper.md` 内容严格匹配当前档位；
- 所有 Markdown 图片链接存在；
- 每张新增视觉都有 prompt / brief；
- 重绘图之前保留了原图；
- 生成示意图没有承担论文证据；
- 精读基于完整 `source.md`；
- 未完成项没有被报告为成功。

对话里只给当前档位、一句话结果、缺失项（如有）和 `paper.md` 入口。

## 输出目录

```text
outputs/<slug>/
├── paper.md
├── source.md
└── figures/
    ├── prompts/
    │   ├── 00-structure.md
    │   └── NN-topic.md
    ├── 00-structure.excalidraw
    ├── 00-structure.png
    ├── NN-original.png
    ├── NN-redraw.excalidraw
    ├── NN-redraw.png
    └── NN-illustration.png
```

文件不存在就不要在 `paper.md` 中引用。原图不需要 prompt，但必须在图注记录出处。

## 按需读取

- 画像或配置不足：读 `references/profile-resolution.md` 与 `references/preferences-schema.md`。
- 规划、生成或恢复视觉：读 `references/illustration-design-guide.md`。
- PDF 抽取失败或需要解释验证器：读 `references/pdf-extraction.md`。
