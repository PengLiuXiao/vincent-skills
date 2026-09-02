"""CLI dispatch for the Prompt Optimizer deterministic tools + inference.

Every subcommand reads/writes JSON so the calling Agent can pipe artifacts
between steps. The Agent orchestrates and performs LLM-judgement steps
(eval_plan, attribution, rewrite, etc.); these subcommands handle:
- Deterministic computation (validate, score, metrics, guardrails)
- Model API inference (run-inference via litellm)

Exit codes:
  0  success
  2  input/boundary error (bad dataset, missing gold, missing model config)
  1  unexpected runtime failure
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .tools import dataset, guardrail, inference, metrics, scorer


def _read_json(source: str) -> Any:
    """Read JSON from a file path, or parse the string as inline JSON."""
    path = Path(source)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return json.loads(source)


def _read_records(source: str) -> list[dict[str, Any]]:
    """Read a list of records from a file or inline string.

    Accepts a JSON array, a single JSON object, or JSONL (one object per
    line) — regardless of file extension — so piping any subcommand's stdout
    into a file and feeding it to the next step always works.
    """
    path = Path(source)
    text = path.read_text(encoding="utf-8") if path.exists() else source
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        rows = []
        for line in text.splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows
    if isinstance(data, dict):
        return [data]
    return data


def _read_prompt(source: str) -> str:
    """Read prompt text from a file path or return as literal string."""
    path = Path(source)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return source


def _emit(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _emit_jsonl(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        print(json.dumps(row, ensure_ascii=False, sort_keys=True))


def _write_jsonl_file(path: str, rows: list[dict[str, Any]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="prompt_optimizer")
    sub = parser.add_subparsers(dest="command", required=True)

    # --- validate-inputs ---
    p_validate = sub.add_parser("validate-inputs", help="check dataset format and gold presence")
    p_validate.add_argument("--dataset", required=True)
    p_validate.add_argument("--input-column")
    p_validate.add_argument("--gold-column")
    p_validate.add_argument("--sample-size", type=int, default=5)

    # --- load-dataset ---
    p_load = sub.add_parser("load-dataset", help="load and normalize full dataset")
    p_load.add_argument("--dataset", required=True)
    p_load.add_argument("--input-column")
    p_load.add_argument("--gold-column")
    p_load.add_argument("--strip-gold", action="store_true", help="output only {id, input}, no gold — for feeding to run-inference")

    # --- split-dataset ---
    p_split = sub.add_parser("split-dataset", help="stratified train/holdout split for honest generalization measurement")
    p_split.add_argument("--dataset", required=True)
    p_split.add_argument("--input-column")
    p_split.add_argument("--gold-column")
    p_split.add_argument("--holdout-ratio", type=float, default=0.2, help="target fraction held out (default 0.2)")
    p_split.add_argument("--train-out", help="write train rows (JSONL) here")
    p_split.add_argument("--holdout-out", help="write holdout rows (JSONL) here")

    # --- run-inference ---
    p_infer = sub.add_parser("run-inference", help="call real model API to produce predictions")
    p_infer.add_argument("--prompt", required=True, help="prompt text or file path")
    p_infer.add_argument("--dataset", required=True, help="input rows {id, input} — must NOT contain gold")
    p_infer.add_argument("--model", required=True, help="litellm model ID (e.g. claude-sonnet-4-20250514, gpt-4o)")
    p_infer.add_argument("--api-key", help="API key (literal or env var name). Required.")
    p_infer.add_argument("--base-url", help="custom API endpoint for OpenAI-compatible providers")
    p_infer.add_argument("--prompt-mode", choices=["system", "template"], default="system",
                         help="system: prompt=system msg, input=user msg; template: prompt has {input} placeholder")
    p_infer.add_argument("--concurrency", type=int, default=5, help="max parallel API requests")
    p_infer.add_argument("--timeout", type=int, default=60, help="per-request timeout in seconds")
    p_infer.add_argument("--output", help="write JSONL to file instead of stdout")

    # --- score-predictions ---
    p_score = sub.add_parser("score-predictions", help="judge is_correct for predictions")
    p_score.add_argument("--task-type", required=True)
    p_score.add_argument("--predictions", required=True, help="jsonl/json of {id, prediction} or {id, gold, prediction}")
    p_score.add_argument("--dataset", help="original dataset path for gold merge (when predictions lack gold)")

    # --- compute-metrics ---
    p_metrics = sub.add_parser("compute-metrics", help="compute all metrics for a task_type")
    p_metrics.add_argument("--task-type", required=True)
    p_metrics.add_argument("--results", required=True, help="jsonl/json of scored rows")

    # --- check-guardrails ---
    p_guard = sub.add_parser("check-guardrails", help="decide candidate eligibility")
    p_guard.add_argument("--payload", required=True, help="json file or inline JSON")

    args = parser.parse_args(argv)

    try:
        if args.command == "validate-inputs":
            result = dataset.validate_inputs(
                args.dataset,
                input_column=args.input_column,
                gold_column=args.gold_column,
                sample_size=args.sample_size,
            )
            _emit(result)
            return 0 if result["valid"] else 2

        if args.command == "load-dataset":
            rows = dataset.load_dataset(
                args.dataset,
                input_column=args.input_column,
                gold_column=args.gold_column,
                strip_gold=args.strip_gold,
            )
            _emit(rows)
            return 0

        if args.command == "split-dataset":
            rows = dataset.load_dataset(
                args.dataset,
                input_column=args.input_column,
                gold_column=args.gold_column,
            )
            train, holdout, summary = dataset.split_dataset(rows, holdout_ratio=args.holdout_ratio)
            if not holdout:
                print(
                    "error: could not form a holdout set (every gold answer is unique, so no "
                    "stratum can be split). Provide more rows per label, or supply a separate "
                    "test set instead of relying on an automatic split.",
                    file=sys.stderr,
                )
                return 2
            if args.train_out:
                _write_jsonl_file(args.train_out, train)
            if args.holdout_out:
                _write_jsonl_file(args.holdout_out, holdout)
            _emit({"summary": summary,
                   "train_out": args.train_out,
                   "holdout_out": args.holdout_out,
                   "train": None if args.train_out else train,
                   "holdout": None if args.holdout_out else holdout})
            return 0

        if args.command == "run-inference":
            api_key = inference.resolve_api_key(args.api_key)
            if not api_key:
                print(
                    "error: API key not found. Set up in one of these ways:\n"
                    "  1. Create a .env file: cp skills/prompt-optimizer/assets/.env.example .env  (then fill in your key)\n"
                    "  2. Export env var: export DEEPSEEK_API_KEY=sk-xxx\n"
                    "  3. Pass via arg: --api-key DEEPSEEK_API_KEY  (env var name)\n",
                    file=sys.stderr,
                )
                return 2
            prompt_text = _read_prompt(args.prompt)
            rows = _read_records(args.dataset)
            results = inference.run_inference_sync(
                rows=rows,
                prompt_text=prompt_text,
                prompt_mode=args.prompt_mode,
                model=args.model,
                api_key=api_key,
                base_url=args.base_url,
                concurrency=args.concurrency,
                timeout=args.timeout,
            )
            if args.output:
                output_path = Path(args.output)
                output_path.parent.mkdir(parents=True, exist_ok=True)
                with output_path.open("w", encoding="utf-8") as f:
                    for row in results:
                        f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            else:
                _emit_jsonl(results)
            error_count = sum(1 for r in results if r.get("error"))
            return 1 if error_count == len(results) else 0

        if args.command == "score-predictions":
            predictions = _read_records(args.predictions)
            has_gold = any("gold" in row for row in predictions)
            if not has_gold:
                if not args.dataset:
                    print("error: predictions lack 'gold' field. Provide --dataset to merge gold answers.", file=sys.stderr)
                    return 2
                gold_rows = dataset.load_dataset(args.dataset)
                predictions = scorer.merge_gold(predictions, gold_rows)
            _emit(scorer.score_predictions(args.task_type, predictions))
            return 0

        if args.command == "compute-metrics":
            rows = _read_records(args.results)
            _emit(metrics.compute_metrics(args.task_type, rows))
            return 0

        if args.command == "check-guardrails":
            payload = _read_json(args.payload)
            result = guardrail.check_guardrails(
                candidate_metrics=payload["candidate_metrics"],
                baseline_metrics=payload["baseline_metrics"],
                baseline_correct_ids=payload.get("baseline_correct_ids", []),
                candidate_results=payload.get("candidate_results", []),
                eval_plan=payload["eval_plan"],
                noise_floor_rate=payload.get("noise_floor_rate", 0.0),
            )
            _emit(result)
            return 0
    except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"prompt_optimizer input error: {error}", file=sys.stderr)
        return 2

    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
