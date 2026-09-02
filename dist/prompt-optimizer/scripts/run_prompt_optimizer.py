#!/usr/bin/env python3
"""Self-contained entry point for the Prompt Optimizer deterministic tools.

Dispatches to prompt_optimizer.cli subcommands. The Skill folder is
self-contained: scripts/prompt_optimizer/ holds the runtime package, so this
wrapper does not depend on the source repo and can be called by absolute path
from any working directory.
"""
from __future__ import annotations

import sys
from pathlib import Path


def _prepare_import_path() -> None:
    script_dir = Path(__file__).resolve().parent
    for path in (str(script_dir), str(script_dir.parent)):
        if path not in sys.path:
            sys.path.insert(0, path)


def run(argv: list[str] | None = None) -> int:
    _prepare_import_path()
    from prompt_optimizer.cli import main

    try:
        return main(argv)
    except Exception as error:  # noqa: BLE001 - top-level guard reports runtime failures
        print(f"prompt_optimizer runtime error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1:]))
