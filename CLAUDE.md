# CLAUDE.md — Vincent Skills 公开发布仓库规范

这是 Vincent 对外发布 Agent Skill 成品的公开仓库。本仓库不是开发区；技能源码、测试、评估和开发记录保存在独立的私有 `skill_builder` 仓库。

## 唯一发布来源

- `dist/`、根目录的 `*.skill`、`MANIFEST.md` 和 `SHA256SUMS` 只能由私有仓库的 `tools/publish-public.sh` 生成和覆盖，不得手工编辑。
- 发布方向固定为私有 `skill_builder` → 本仓库，不做反向同步。
- 发布器完成打包、结构检查和泄漏检查后只更新工作树，不自动 commit 或 push。
- 提交前必须检查 `git diff`；`git push` 等待 Vincent 明确执行或授权。

## 仓库结构

```text
vincent-skills/
├── CLAUDE.md
├── AGENTS.md -> CLAUDE.md
├── LICENSE
├── README.md
├── MANIFEST.md
├── SHA256SUMS
├── <skill-name>.skill
└── dist/
    └── <skill-name>/
```

- `<skill-name>/` 是可浏览、可直接安装的运行期目录。
- 根目录的 `<skill-name>.skill` 是同内容的发布压缩包，便于直接下载。
- `MANIFEST.md` 记录来源提交和本次技能清单；`SHA256SUMS` 用于校验压缩包。

## 公开边界

这里的所有内容都按公开信息处理。禁止加入密钥、token、密码、私人素材、无再分发权的资源，以及 `tests/`、`evals/`、项目级 `docs/`、开发报告、`.env`、缓存和 Git 元数据。

## 许可协议

本仓库全部公开内容采用根目录 `LICENSE` 中的 MIT License，版权人为 Vincent Liu。

## CLAUDE.md / AGENTS.md 同源

`CLAUDE.md` 是唯一规范真身，`AGENTS.md` 必须是指向它的软链接。只编辑 `CLAUDE.md`，永不直接编辑 `AGENTS.md`。
