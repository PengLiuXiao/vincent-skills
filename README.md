# Vincent Skills

Vincent 对外发布的 Agent Skill 成品仓库。开发源码、测试与评估保存在独立的私有仓库；这里仅保留经过打包检查的运行期产物。

## 获取技能

- 浏览 `dist/<skill-name>/` 查看技能内容。
- 从仓库根目录下载 `<skill-name>.skill` 获取可分发压缩包。
- 使用根目录 `SHA256SUMS` 校验下载文件完整性。
- 查看根目录 `MANIFEST.md` 确认本次发布来源和技能清单。

`.skill` 本质是 ZIP。如果目标平台不识别 `.skill` 扩展名，可以将其改为 `.zip` 后解压。

## 发布说明

`dist/`、根目录的 `.skill` 压缩包和发布清单均由私有开发仓库的发布工具单向生成，请勿直接编辑。

## License

本仓库采用 [MIT License](./LICENSE)，版权归 Vincent Liu 所有。
