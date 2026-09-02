# PDF 抽取与输出验证

## PDF 抽取

优先使用宿主原生 PDF 读取。失败时运行：

```bash
python3 scripts/extract.py input.pdf --output outputs/paper/source.md
```

依赖：

```bash
pip install -r scripts/requirements.txt
```

`extract.py` 使用 `pypdf`，保留分页标记并尽量清理 PDF 文本。仍失败时尝试系统 `pdftotext`；三条路径都失败就说明原因，不编造正文。

## 交付物验证

```bash
python3 scripts/validate_output.py outputs/paper
```

验证器只使用 Python 标准库，检查：

- `paper.md` / `source.md`；
- 非对称三档正文组成；
- 结构图 `.excalidraw + .png + brief`；
- Markdown 图片链接；
- 新增视觉的 prompt / brief；
- 重绘图的原图对照与声明；
- 生成示意图的图注。

验证失败代表产物未完成；不要把它报告为成功。
