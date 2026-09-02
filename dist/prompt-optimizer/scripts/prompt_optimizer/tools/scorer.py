"""Deterministic scoring: judge is_correct per task_type.

The run-inference tool produces predictions via a real model API; this tool
only compares prediction vs gold using rules fixed by task_type. No inference.
"""
from __future__ import annotations

import json
from typing import Any


SUPPORTED_TASK_TYPES = {
    "classification",
    "quality_judgement",
    "tagging",
    "structured_extraction",
    "rubric_scoring",
}


def merge_gold(predictions: list[dict[str, Any]], dataset: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge gold answers from dataset into prediction rows by id.

    Predictions have {id, prediction}; dataset has {id, input, gold}.
    Returns rows with {id, input, gold, prediction}.
    """
    gold_lookup = {str(row["id"]): row for row in dataset}
    merged = []
    for pred_row in predictions:
        row_id = str(pred_row.get("id", ""))
        source = gold_lookup.get(row_id, {})
        merged.append({
            "id": row_id,
            "input": source.get("input", pred_row.get("input", "")),
            "gold": source.get("gold"),
            "prediction": pred_row.get("prediction"),
        })
    return merged


def score_predictions(task_type: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Annotate each row with is_correct based on task_type.

    Each input row must contain at least gold and prediction; id/input are
    passed through if present.
    """
    if task_type not in SUPPORTED_TASK_TYPES:
        raise ValueError(f"unsupported task_type: {task_type}")
    scored = []
    for row in rows:
        result = dict(row)
        result["is_correct"] = _is_correct(task_type, row.get("gold"), row.get("prediction"))
        scored.append(result)
    return scored


def _is_correct(task_type: str, gold: Any, prediction: Any) -> bool:
    if task_type in {"classification", "quality_judgement"}:
        return _normalize_scalar(gold) == _normalize_scalar(prediction)
    if task_type == "tagging":
        return _as_set(gold) == _as_set(prediction)
    if task_type == "rubric_scoring":
        gold_num = _as_number(gold)
        pred_num = _as_number(prediction)
        return gold_num is not None and gold_num == pred_num
    if task_type == "structured_extraction":
        return _fields_match(gold, prediction)
    return False


def _normalize_scalar(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _as_set(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        return {str(item).strip() for item in value}
    # LLM predictions often return JSON-encoded lists as strings
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return {str(item).strip() for item in parsed}
        except (json.JSONDecodeError, ValueError):
            pass
    return {str(value).strip()}


def _as_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fields_match(gold: Any, prediction: Any) -> bool:
    gold_dict = gold if isinstance(gold, dict) else {}
    prediction_dict = prediction if isinstance(prediction, dict) else {}
    if not prediction_dict and isinstance(prediction, str):
        try:
            parsed = json.loads(prediction)
            if isinstance(parsed, dict):
                prediction_dict = parsed
        except (json.JSONDecodeError, ValueError):
            pass
    if set(gold_dict.keys()) != set(prediction_dict.keys()):
        return False
    return all(
        _normalize_scalar(gold_dict[key]) == _normalize_scalar(prediction_dict.get(key))
        for key in gold_dict
    )
