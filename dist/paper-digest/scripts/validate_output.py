#!/usr/bin/env python3
"""Validate a completed paper-digest output folder using only the stdlib."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


TIER_RE = re.compile(r"当前档位[^\n]*(overview|skim|deep-read)")
IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def local_image_paths(markdown: str) -> list[str]:
    paths: list[str] = []
    for raw in IMAGE_RE.findall(markdown):
        target = raw.strip().split(maxsplit=1)[0].strip("<>")
        if target.startswith(("http://", "https://", "data:")):
            continue
        paths.append(target)
    return paths


def validate(folder: Path) -> list[str]:
    errors: list[str] = []
    paper = folder / "paper.md"
    source = folder / "source.md"
    figures = folder / "figures"

    if not paper.is_file():
        return ["missing paper.md"]
    if not source.is_file() or not source.read_text(encoding="utf-8").strip():
        errors.append("missing or empty source.md")

    text = paper.read_text(encoding="utf-8")
    if "{{" in text or "_ONLY" in text:
        errors.append("paper.md still contains template placeholders or control comments")

    if not re.search(r"^##\s+概述\s*$", text, re.MULTILINE):
        errors.append("paper.md must contain 概述")

    tier_match = TIER_RE.search(text)
    if not tier_match:
        errors.append("paper.md does not declare overview, skim, or deep-read as 当前档位")
        tier = None
    else:
        tier = tier_match.group(1)

    has_skim = bool(re.search(r"^##\s+粗读\s*$", text, re.MULTILINE))
    has_deep = bool(re.search(r"^##\s+精读正文\s*$", text, re.MULTILINE))
    if tier == "overview" and (has_skim or has_deep):
        errors.append("overview must not contain 粗读 or 精读正文")
    elif tier == "skim" and (not has_skim or has_deep):
        errors.append("skim must contain 粗读 and must not contain 精读正文")
    elif tier == "deep-read" and (has_skim or not has_deep):
        errors.append("deep-read must contain 精读正文 and must not contain 粗读")

    required_structure = [
        figures / "00-structure.png",
        figures / "00-structure.excalidraw",
        figures / "prompts" / "00-structure.md",
    ]
    for path in required_structure:
        if not path.is_file():
            errors.append(f"missing required structure asset: {path.relative_to(folder)}")

    image_paths = local_image_paths(text)
    if "./figures/00-structure.png" not in image_paths:
        errors.append("paper.md does not embed ./figures/00-structure.png")

    folder_root = folder.resolve()
    for rel in image_paths:
        path = (folder / rel).resolve()
        try:
            path.relative_to(folder_root)
        except ValueError:
            errors.append(f"image path escapes output folder: {rel}")
            continue
        if not path.is_file():
            errors.append(f"broken image link: {rel}")
            continue

        stem = path.stem
        if stem.endswith("-original"):
            continue
        brief = figures / "prompts" / f"{stem}.md"
        if not brief.is_file():
            errors.append(f"missing visual brief for {rel}: figures/prompts/{stem}.md")
            continue

        brief_text = brief.read_text(encoding="utf-8")
        if re.search(r"\*\*类型\*\*：.*(?:structure|excalidraw|original-redraw)", brief_text):
            editable = figures / f"{stem}.excalidraw"
            if not editable.is_file():
                errors.append(f"missing editable Excalidraw source for {rel}: {editable.name}")

        if stem.endswith("-redraw"):
            image_position = text.find(rel)
            prior_text = text[:image_position]
            if "-original." not in prior_text:
                errors.append(f"redraw appears without an earlier original figure: {rel}")
            following = text[image_position : image_position + 500]
            if "请以原图为准" not in following:
                errors.append(f"redraw caption lacks 请以原图为准: {rel}")

        if "generated-illustration" in brief_text:
            image_position = text.find(rel)
            following = text[image_position : image_position + 500]
            if "示意图" not in following:
                errors.append(f"generated illustration caption lacks 示意图: {rel}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_folder", type=Path)
    args = parser.parse_args()

    errors = validate(args.output_folder)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"OK: {args.output_folder}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
