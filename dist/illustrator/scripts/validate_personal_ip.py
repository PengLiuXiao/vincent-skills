#!/usr/bin/env python3
"""Validate Illustrator's private, portable personal-IP runtime assets."""

from __future__ import annotations

import argparse
import json
import re
import struct
from pathlib import Path
from typing import Any


SPEC_HEADINGS = (
    "## 角色定位",
    "## 固定身份特征",
    "## 标志性服装与配件",
    "## 允许变化",
    "## 禁止漂移",
    "## 唯一身份锁",
    "## 生图提示词片段",
    "## 一致性检查清单",
)
REQUIRED_SPEC_PHRASES = (
    "CANONICAL IDENTITY LOCK",
    "3—3.5 头身",
    "亮橙色",
)
SENSITIVE_PATH_PATTERNS = (
    re.compile(r"/Users/[^\s)]+"),
    re.compile(r"[A-Za-z]:\\Users\\[^\s)]+"),
    re.compile(r"file://", re.IGNORECASE),
    re.compile(r"photoslibrary", re.IGNORECASE),
)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if len(data) < 24 or data[:8] != PNG_SIGNATURE or data[12:16] != b"IHDR":
        raise ValueError("turnaround.png is not a readable PNG with an IHDR header")
    return struct.unpack(">II", data[16:24])


def validate(root: Path) -> dict[str, Any]:
    root = root.resolve()
    failures: list[str] = []
    warnings: list[str] = []
    turnaround = root / "assets" / "personal-ip" / "turnaround.png"
    spec = root / "references" / "character-spec.md"

    if not turnaround.is_file():
        failures.append("missing confirmed personal IP: assets/personal-ip/turnaround.png")
    else:
        if turnaround.is_symlink():
            failures.append("turnaround.png must be a regular in-package file, not a symlink")
        try:
            width, height = png_dimensions(turnaround)
            if width < 1200 or height < 600:
                failures.append(f"turnaround.png is too small for a reusable three-view reference: {width}x{height}")
            ratio = width / height
            if not 1.5 <= ratio <= 2.1:
                failures.append(f"turnaround.png must be a landscape three-view sheet near 16:9: {width}x{height}")
        except (OSError, ValueError) as exc:
            failures.append(str(exc))

    assets_dir = root / "assets" / "personal-ip"
    if assets_dir.exists():
        unexpected = sorted(
            str(path.relative_to(root))
            for path in assets_dir.iterdir()
            if path.name != "turnaround.png"
        )
        if unexpected:
            failures.append(
                "personal-ip runtime directory contains unconfirmed or raw assets: " + ", ".join(unexpected)
            )

    if not spec.is_file():
        failures.append("missing confirmed character rules: references/character-spec.md")
    else:
        text = spec.read_text(encoding="utf-8")
        for heading in SPEC_HEADINGS:
            if heading not in text:
                failures.append(f"character-spec.md missing section: {heading}")
        for phrase in REQUIRED_SPEC_PHRASES:
            if phrase not in text:
                failures.append(f"character-spec.md missing fixed identity contract: {phrase}")
        if re.search(r"<[^>]+>", text):
            failures.append("character-spec.md still contains angle-bracket placeholders")
        for pattern in SENSITIVE_PATH_PATTERNS:
            if pattern.search(text):
                failures.append(f"character-spec.md contains a private source path matching: {pattern.pattern}")

    return {
        "ok": not failures,
        "root": str(root),
        "failures": failures,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate Illustrator's confirmed turnaround and character specification."
    )
    parser.add_argument("skill_dir", nargs="?", default=".", help="Illustrator skill directory")
    args = parser.parse_args()
    result = validate(Path(args.skill_dir))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
