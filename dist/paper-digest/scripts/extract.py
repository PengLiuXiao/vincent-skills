#!/usr/bin/env python3
"""
extract.py — paper-digest 技能的 PDF / HTML / text 文本抽取【兜底脚本】。

定位（PDF 抽取兜底链的第二环）
================================
paper-digest 处理 PDF 时按下面三级【兜底链】逐级尝试，任一级拿到文本即停，
全失败则打印清晰错误与安装提示，**绝不伪造内容**：

  1. 运行时原生读取：若当前 Agent 运行时本身支持读 PDF（如某些自带工具），
     直接读，不走本脚本；
  2. 本脚本（你现在看的 extract.py）——内部再分两级：
       a) pypdf（Python 软依赖，`pip install pypdf`）；
       b) pdftotext 系统命令（poppler 套件）。
  3. 再往后由调用方 / 用户兜底处理。

只读本地文件 / 不联网
=====================
本脚本**不抓 URL、不联网**——URL 抓取由宿主 Agent（host agent）负责；
本脚本只接收一个本地文件路径，把内容整理成 markdown 输出。

用法
====
    python3 scripts/extract.py <input-file> [--output <out.md>] [--format auto|pdf|html|text]

    <input-file>            本地输入文件路径（PDF / HTML / 文本）。
    --output <out.md>       写入该文件（UTF-8 markdown）；省略则打印到 stdout。
    --format {auto|pdf|html|text}
                            auto（默认）按扩展名推断：
                            .pdf→pdf，.html/.htm/.xhtml→html，其余→text。
"""

import argparse
import os
import re
import subprocess
import sys
from html.parser import HTMLParser


# --------------------------------------------------------------------------- #
# 异常
# --------------------------------------------------------------------------- #
class PdfExtractionError(RuntimeError):
    """PDF 兜底链（pypdf → pdftotext）全部失败的专用异常。"""


# --------------------------------------------------------------------------- #
# 通用 IO
# --------------------------------------------------------------------------- #
def _read_text(path):
    """读取本地文件为文本。优先 UTF-8；解码失败则宽松解码并提示。"""
    with open(path, "rb") as f:
        data = f.read()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        sys.stderr.write(
            "extract.py: 文件非 UTF-8，已用宽松解码（不可解码字符会被替换）。\n"
        )
        return data.decode("utf-8", errors="replace")


# --------------------------------------------------------------------------- #
# PDF 兜底链
# --------------------------------------------------------------------------- #
def _extract_pdf_pypdf(path):
    """用 pypdf 逐页抽取；每页加 `<!-- page N -->` 标记，页间空行分隔。"""
    import pypdf  # 软依赖；未安装时抛 ImportError 由调用方捕获

    reader = pypdf.PdfReader(path)
    blocks = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""  # 单页失败不拖垮整篇
        blocks.append(f"<!-- page {i} -->\n{txt}")
    return "\n\n".join(blocks)


def _extract_pdf_pdftotext(path):
    """调用系统命令 `pdftotext -layout <input> -`，捕获 stdout。"""
    result = subprocess.run(
        ["pdftotext", "-layout", path, "-"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"pdftotext 退出码 {result.returncode}: {result.stderr.strip()[:200]}"
        )
    return result.stdout


def extract_pdf(path):
    """
    PDF 兜底链：pypdf → pdftotext，任一抽到非空文本即返回。

    Returns:
        (text, method): 成功抽取的文本与所用方法名（"pypdf" / "pdftotext"）。
    Raises:
        PdfExtractionError: 两级都不可用 / 都未抽到文本。
    """
    attempts = (
        ("pypdf", _extract_pdf_pypdf),
        ("pdftotext", _extract_pdf_pdftotext),
    )

    for method, func in attempts:
        try:
            text = func(path)
        except ImportError:
            sys.stderr.write(f"extract.py: 未安装 {method}，跳过该兜底级。\n")
            continue
        except FileNotFoundError:
            sys.stderr.write(
                f"extract.py: 未找到系统命令 {method}，跳过该兜底级。\n"
            )
            continue
        except Exception as exc:  # noqa: BLE001 — 兜底链要吞掉单级错误继续下一级
            sys.stderr.write(
                f"extract.py: {method} 抽取失败"
                f"（{type(exc).__name__}: {exc}），尝试下一级。\n"
            )
            continue

        if text and text.strip():
            return text, method
        sys.stderr.write(
            f"extract.py: {method} 未抽到任何文本（可能是扫描件），尝试下一级。\n"
        )

    raise PdfExtractionError(
        "PDF 文本抽取全部失败：pypdf 与 pdftotext 均不可用或未抽到文本。\n"
        "  请安装其中任意一个（任选其一即可）：\n"
        "    pip install pypdf\n"
        "        ——纯 Python 包，无需系统权限，推荐首选；\n"
        "    或安装 poppler 以获得 pdftotext：\n"
        "        macOS:   brew install poppler\n"
        "        Debian/Ubuntu: sudo apt install poppler-utils"
    )


# --------------------------------------------------------------------------- #
# HTML → markdown-ish（仅用标准库 html.parser）
# --------------------------------------------------------------------------- #
class _HtmlToMarkdown(HTMLParser):
    """best-effort：把 HTML 标签转成 markdown 风格文本（标题/段落/列表）。"""

    _SKIP = {"script", "style", "noscript", "head", "svg"}
    _HEAD = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}
    _BLOCK = {
        "p", "div", "section", "article", "blockquote", "tr", "header",
        "footer", "main", "aside", "figure", "figcaption", "table",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._chunks = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self._SKIP:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "br":
            self._chunks.append("\n")
        elif tag in self._HEAD:
            self._chunks.append("\n\n" + "#" * self._HEAD[tag] + " ")
        elif tag == "li":
            self._chunks.append("\n- ")
        elif tag in self._BLOCK:
            self._chunks.append("\n\n")

    def handle_startendtag(self, tag, attrs):
        # 自闭合标签，如 <br/> <hr/>
        if not self._skip_depth and tag.lower() == "br":
            self._chunks.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self._SKIP:
            if self._skip_depth > 0:
                self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in self._BLOCK or tag in self._HEAD:
            self._chunks.append("\n\n")

    def handle_data(self, data):
        if self._skip_depth or not data:
            return
        self._chunks.append(data)

    def result(self):
        return _normalize_whitespace("".join(self._chunks))


def _normalize_whitespace(text):
    """规整空白：行内空格折叠、去行首尾空白、最多保留一个空行。"""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def extract_html(raw):
    """用标准库 html.parser 把 HTML 转成 markdown 风格文本。"""
    parser = _HtmlToMarkdown()
    parser.feed(raw)
    parser.close()
    return parser.result()


# --------------------------------------------------------------------------- #
# 格式推断
# --------------------------------------------------------------------------- #
def infer_format(path):
    """按扩展名推断格式；无法识别一律按 text 处理。"""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return "pdf"
    if ext in (".html", ".htm", ".xhtml"):
        return "html"
    return "text"


# --------------------------------------------------------------------------- #
# 入口
# --------------------------------------------------------------------------- #
def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="extract.py",
        description=(
            "从本地文件抽取文本到 markdown（PDF 兜底链：pypdf → pdftotext）。"
            "仅读本地文件，不联网。"
        ),
    )
    parser.add_argument("input", help="输入文件路径（本地文件）")
    parser.add_argument(
        "--output", "-o", default=None,
        help="输出 markdown 文件路径；省略则打印到 stdout",
    )
    parser.add_argument(
        "--format", choices=["auto", "pdf", "html", "text"], default="auto",
        help="抽取模式；auto 按扩展名推断（默认 auto）",
    )
    args = parser.parse_args(argv)

    # 输入校验：缺失 / 不可读要优雅处理
    if not os.path.exists(args.input):
        sys.stderr.write(f"extract.py: 输入文件不存在: {args.input}\n")
        return 2
    if not os.path.isfile(args.input):
        sys.stderr.write(f"extract.py: 输入不是普通文件: {args.input}\n")
        return 2

    fmt = args.format
    if fmt == "auto":
        fmt = infer_format(args.input)

    # 抽取
    try:
        if fmt == "pdf":
            content, method = extract_pdf(args.input)
            sys.stderr.write(f"extract.py: PDF 用 {method} 抽取成功。\n")
        elif fmt == "html":
            content = extract_html(_read_text(args.input))
            sys.stderr.write("extract.py: HTML（标准库 html.parser）抽取完成。\n")
        else:  # text / .md 直通
            content = _read_text(args.input)
            sys.stderr.write("extract.py: 文本直通（未改动）。\n")
    except PdfExtractionError as exc:
        sys.stderr.write(f"extract.py: {exc}\n")
        return 1
    except Exception as exc:  # noqa: BLE001 — 顶层兜底，给一行 stderr 原因
        sys.stderr.write(
            f"extract.py: 抽取失败 — {type(exc).__name__}: {exc}\n"
        )
        return 1

    # markdown 末尾卫生：确保恰好一个换行
    if content and not content.endswith("\n"):
        content += "\n"

    # 输出
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(content)
        except OSError as exc:
            sys.stderr.write(
                f"extract.py: 写出失败 — {type(exc).__name__}: {exc}\n"
            )
            return 1
    else:
        sys.stdout.write(content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
