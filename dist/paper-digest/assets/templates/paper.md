<!--
唯一阅读入口 paper.md。替换所有 {{...}}；删除不属于当前档位的条件区块和本注释。
overview = 元数据 + 概述 + 结构图
skim = overview + 粗读
deep-read = overview + 精读正文；绝不包含粗读
-->

# {{title}}

- **作者**：{{authors}}
- **原文**：{{source-link-or-local-path}}
- **发布日期**：{{published-date}}
- **处理日期**：{{processed-date}}
- **当前档位**：`{{overview|skim|deep-read}}`

<!-- AUTO_ONLY_START：用户明确指定档位时删除 -->
> **阅读建议**：{{概述 / 粗读 / 精读}}  
> **原因**：{{与画像的相关点 + 文章质量信号}}
<!-- AUTO_ONLY_END -->

<!-- PARTIAL_SOURCE_ONLY：来源不完整时保留 -->
> ⚠️ 当前来源不完整：{{缺失范围与影响}}

<!-- DEEP_READ_FOREIGN_ONLY：外文精读时保留 -->
> 本文由 AI 翻译，请以原文为准。

## 概述

{{约一分钟读完：问题、核心结论、价值边界}}

![文章结构图](./figures/00-structure.png)

<!-- SKIM_ONLY_START -->
## 粗读

### 文章解决什么问题

{{...}}

### 核心观点或结论

{{...}}

### 方法

{{...}}

### 关键证据

{{...}}

### 论证如何成立

{{...}}

### 局限与可能的问题

{{...}}

### 对你的价值

{{...}}

### 是否值得精读

{{结论与原因}}
<!-- SKIM_ONLY_END -->

<!-- DEEP_READ_ONLY_START：精读时删除整个 SKIM 区块，保留本区块 -->
## 精读正文

### {{原文一级标题的中文翻译}}

{{忠实完整正文。保留段落、公式、表格、引用和脚注；图片放在对应段落之后。}}

![{{alt text}}](./figures/{{NN-topic.png}})

*{{图注；原图写编号和来源，生成图标明“示意图”，重绘图写“依据原图重绘，请以原图为准”。}}*
<!-- DEEP_READ_ONLY_END -->
