"""Async batch inference via litellm.

Calls the user-specified model API to produce predictions for each input row.
This tool NEVER sees gold answers — it only receives {id, input} rows.
Gold is merged later by score-predictions from the original dataset.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any


def _load_dotenv_once() -> None:
    """Try to load .env file once. No-op if python-dotenv is not installed."""
    if getattr(_load_dotenv_once, "_done", False):
        return
    _load_dotenv_once._done = True  # type: ignore[attr-defined]
    try:
        from dotenv import load_dotenv
        load_dotenv()  # does NOT override existing env vars
    except ImportError:
        pass


# Common API key env var names to auto-detect.
_COMMON_KEY_ENVS = [
    "API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DEEPSEEK_API_KEY",
    "DASHSCOPE_API_KEY",
]


def resolve_api_key(api_key_arg: str | None) -> str | None:
    """Resolve API key with priority: env-var-by-name > .env > common env vars > literal.

    Priority chain:
      1. If *api_key_arg* is an env-var name that exists, return its value.
      2. Auto-detect common API-key env vars (may come from .env or shell).
      3. If *api_key_arg* looks like a literal key, accept it (fallback).
    """
    _load_dotenv_once()

    # 1. Treat arg as env var name
    if api_key_arg:
        env_val = os.environ.get(api_key_arg)
        if env_val:
            return env_val

    # 2. Auto-detect common env var names
    for name in _COMMON_KEY_ENVS:
        val = os.environ.get(name)
        if val:
            return val

    # 3. Literal key fallback (allowed but not encouraged)
    if api_key_arg and (
        api_key_arg.startswith("sk-")
        or api_key_arg.startswith("key-")
        or len(api_key_arg) > 20
    ):
        return api_key_arg

    return None


def build_messages(prompt_text: str, input_text: str, prompt_mode: str) -> list[dict[str, str]]:
    """Build message list based on prompt_mode."""
    if prompt_mode == "template":
        rendered = prompt_text.replace("{input}", input_text)
        return [{"role": "user", "content": rendered}]
    return [
        {"role": "system", "content": prompt_text},
        {"role": "user", "content": input_text},
    ]


async def run_inference(
    rows: list[dict[str, Any]],
    prompt_text: str,
    prompt_mode: str,
    model: str,
    api_key: str | None = None,
    base_url: str | None = None,
    concurrency: int = 5,
    timeout: int = 60,
) -> list[dict[str, Any]]:
    """Run inference on all rows with bounded concurrency.

    Returns list of {id, prediction} or {id, prediction: null, error: str}.
    Prints progress JSON lines to stderr.
    """
    import litellm

    litellm.drop_params = True

    sem = asyncio.Semaphore(concurrency)
    results: list[dict[str, Any]] = [None] * len(rows)  # type: ignore[list-item]
    completed = 0
    errors = 0
    tokens_in = 0
    tokens_out = 0
    total = len(rows)

    def _report_progress() -> None:
        print(
            json.dumps({
                "completed": completed,
                "total": total,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "errors": errors,
            }, ensure_ascii=False),
            file=sys.stderr,
            flush=True,
        )

    async def infer_one(index: int, row: dict[str, Any]) -> None:
        nonlocal completed, errors, tokens_in, tokens_out
        row_id = str(row.get("id", index))
        input_text = str(row.get("input", ""))
        messages = build_messages(prompt_text, input_text, prompt_mode)

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "timeout": timeout,
            "num_retries": 3,
        }
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["api_base"] = base_url

        async with sem:
            try:
                response = await litellm.acompletion(**kwargs)
                prediction = response.choices[0].message.content
                if prediction:
                    prediction = prediction.strip()
                usage = getattr(response, "usage", None)
                if usage:
                    tokens_in += getattr(usage, "prompt_tokens", 0)
                    tokens_out += getattr(usage, "completion_tokens", 0)
                results[index] = {"id": row_id, "prediction": prediction}
            except Exception as exc:
                results[index] = {"id": row_id, "prediction": None, "error": str(exc)}
                errors += 1
            finally:
                completed += 1
                if completed % max(1, total // 10) == 0 or completed == total:
                    _report_progress()

    await asyncio.gather(*(infer_one(i, row) for i, row in enumerate(rows)))
    _report_progress()
    return results


def run_inference_sync(
    rows: list[dict[str, Any]],
    prompt_text: str,
    prompt_mode: str,
    model: str,
    api_key: str | None = None,
    base_url: str | None = None,
    concurrency: int = 5,
    timeout: int = 60,
) -> list[dict[str, Any]]:
    """Synchronous wrapper around the async inference engine."""
    return asyncio.run(
        run_inference(rows, prompt_text, prompt_mode, model, api_key, base_url, concurrency, timeout)
    )
