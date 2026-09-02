#!/usr/bin/env python3
"""Validate Infographics' private identity and runtime content contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path
from typing import Any


EXPECTED_TURNAROUND_SHA256 = "23818b182e284d61a9cd81ae70e5380a346d86845ae457e55df11312dcbdc08d"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
REQUIRED_RUNTIME_FILES = (
    "SKILL.md",
    "assets/personal-ip/turnaround.png",
    "references/character-spec.md",
    "references/information-architecture.md",
    "references/visual-system.md",
    "references/prompt-template.md",
    "references/qa-checklist.md",
    "references/privacy-and-files.md",
    "references/sources-and-rights.md",
)
SPEC_HEADINGS = (
    "## 角色定位",
    "## 固定身份特征",
    "## 标志性服装与配件",
    "## 信息图中的职责",
    "## 允许变化",
    "## 禁止漂移",
    "## 唯一身份锁",
    "## 生图提示词片段",
    "## 一致性检查清单",
)
SPEC_PHRASES = (
    "CANONICAL IDENTITY LOCK",
    "3—3.5 头身",
    "亮橙色",
    "8%—18%",
)
CONTRACT_PHRASES = {
    "SKILL.md": ("3:4", "事实清单", "illustrator", "图片尚未通过准确性验收"),
    "references/information-architecture.md": ("SOURCE LEDGER", "LOCKED TEXT", "4—6"),
    "references/visual-system.md": ("3:4", "彩铅", "文本可靠性优先"),
    "references/prompt-template.md": ("LOCKED TEXT", "CHANGE ONLY", "PROTECT"),
    "references/qa-checklist.md": ("来源与事实", "文字准确性", "图表与关系"),
}
SENSITIVE_PATH_PATTERNS = (
    re.compile(r"/Users/[^\s)]+"),
    re.compile(r"[A-Za-z]:\\Users\\[^\s)]+"),
    re.compile(r"file://", re.IGNORECASE),
    re.compile(r"photoslibrary", re.IGNORECASE),
)


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if len(data) < 24 or data[:8] != PNG_SIGNATURE or data[12:16] != b"IHDR":
        raise ValueError("turnaround.png is not a readable PNG with an IHDR header")
    return struct.unpack(">II", data[16:24])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(root: Path, expected_sha256: str | None = EXPECTED_TURNAROUND_SHA256) -> dict[str, Any]:
    root = root.resolve()
    failures: list[str] = []
    warnings: list[str] = []

    for relative in REQUIRED_RUNTIME_FILES:
        if not (root / relative).is_file():
            failures.append(f"missing runtime file: {relative}")

    turnaround = root / "assets" / "personal-ip" / "turnaround.png"
    if turnaround.is_file():
        if turnaround.is_symlink():
            failures.append("turnaround.png must be an in-package regular file, not a symlink")
        try:
            width, height = png_dimensions(turnaround)
            if width < 1200 or height < 600:
                failures.append(f"turnaround.png is too small for a reusable three-view reference: {width}x{height}")
            if not 1.5 <= width / height <= 2.1:
                failures.append(f"turnaround.png must be a landscape three-view sheet near 16:9: {width}x{height}")
        except (OSError, ValueError) as exc:
            failures.append(str(exc))
        if expected_sha256 and sha256(turnaround) != expected_sha256:
            failures.append("turnaround.png does not match the confirmed Vincent identity asset")

    identity_dir = root / "assets" / "personal-ip"
    if identity_dir.exists():
        unexpected = sorted(
            str(path.relative_to(root))
            for path in identity_dir.iterdir()
            if path.name != "turnaround.png"
        )
        if unexpected:
            failures.append("personal-ip runtime directory contains raw or unconfirmed assets: " + ", ".join(unexpected))

    spec = root / "references" / "character-spec.md"
    if spec.is_file():
        text = spec.read_text(encoding="utf-8")
        for heading in SPEC_HEADINGS:
            if heading not in text:
                failures.append(f"character-spec.md missing section: {heading}")
        for phrase in SPEC_PHRASES:
            if phrase not in text:
                failures.append(f"character-spec.md missing fixed identity contract: {phrase}")
        if re.search(r"<[^>]+>", text):
            failures.append("character-spec.md still contains angle-bracket placeholders")

    for relative, phrases in CONTRACT_PHRASES.items():
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for phrase in phrases:
            if phrase not in text:
                failures.append(f"{relative} missing infographic contract: {phrase}")

    for relative in ("SKILL.md", *(f"references/{path.name}" for path in (root / "references").glob("*.md"))):
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in SENSITIVE_PATH_PATTERNS:
            if pattern.search(text):
                failures.append(f"{relative} contains a private source path matching: {pattern.pattern}")

    nested_entries = sorted(
        str(path.relative_to(root))
        for path in root.rglob("SKILL.md")
        if path != root / "SKILL.md" and ".git" not in path.parts
    )
    if nested_entries:
        failures.append("nested discoverable SKILL.md files found: " + ", ".join(nested_entries))

    return {
        "ok": not failures,
        "root": str(root),
        "turnaround_sha256": sha256(turnaround) if turnaround.is_file() else None,
        "failures": failures,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate Infographics' confirmed identity and information-accuracy runtime contracts."
    )
    parser.add_argument("skill_dir", nargs="?", default=".", help="Infographics skill directory")
    args = parser.parse_args()
    result = validate(Path(args.skill_dir))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
