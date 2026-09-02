# `EXTEND.md` 字段参考

配置是可选的；没有配置时先从对话和工作区推断。模板见 `../assets/EXTEND.md.template`，画像询问规则见 `./profile-resolution.md`。

## Version 2

### `profile`

| 字段 | 类型 | 默认 | 含义 |
|---|---|---|---|
| `interests` | string[] | `[]` | 长期兴趣，用于画像相关度 |
| `background` | string | `""` | 知识水平与相关经验 |
| `current_goals` | string[] | `[]` | 当前目标，优先级高于长期兴趣 |
| `output_language` | string | `zh` | 概述、粗读和精读的输出语言 |

### `preferences`

| 字段 | 取值 | 默认 | 含义 |
|---|---|---|---|
| `max_auto_depth` | `overview` / `skim` / `deep-read` | `deep-read` | 模糊请求的自动选档上限；不限制明确指令 |
| `visual_density` | `auto` / `minimal` / `balanced` / `rich` | `auto` | 新增视觉的上限，不是最低配额 |
| `output_dir` | 路径 | `./outputs` | 每篇文章工作区的父目录 |

`visual_density` 语义：

- `auto`：只由认知难点决定；
- `minimal`：只处理最强的一个视觉机会；
- `balanced`：覆盖主要认知难点，但每个主要论点最多一张新增视觉；
- `rich`：覆盖所有真实视觉机会，仍禁止装饰图。

结构图不受 `visual_density` 影响，任何档位都需要一张。

## 文件解析

按顺序找：

1. `.paper-digest/EXTEND.md`；
2. `~/.paper-digest/EXTEND.md`。

先找到即用；相对 `output_dir` 按宿主当前工作目录解析。字段缺失或非法时仅对该字段使用默认值，不阻塞任务。

## Version 1 兼容

读取旧配置时映射：

- `profile.language` → `profile.output_language`；
- `profile.read_depth` → `preferences.max_auto_depth`；
- `preferences.figure_density` → `preferences.visual_density`，其中 `per-section` 映射为 `balanced`；
- 忽略 `preferences.image_backend`，因为新版本按内容类型自动路由视觉能力。

不要为了迁移自动覆盖用户文件；仅在用户要求保存新配置时升级为 version 2。
