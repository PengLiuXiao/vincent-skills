"""Metric computation. Computes ALL available metrics for a task_type.

The eval_plan (produced by the Agent) decides which metrics are primary /
secondary; this tool only computes. Metric pools match SKILL_DESIGN.md §3.
"""
from __future__ import annotations

import json
from typing import Any


METRIC_POOLS: dict[str, list[str]] = {
    "classification": ["accuracy", "macro_precision", "macro_recall", "macro_f1"],
    "quality_judgement": ["accuracy", "macro_precision", "macro_recall", "macro_f1"],
    "tagging": ["micro_precision", "micro_recall", "micro_f1", "exact_match", "label_regression_rate"],
    "structured_extraction": ["field_accuracy", "field_f1", "missing_field_rate", "extra_field_rate"],
    "rubric_scoring": ["exact_match", "within_1_accuracy", "mae"],
}

LOWER_IS_BETTER = {"mae", "missing_field_rate", "extra_field_rate", "label_regression_rate"}


def compute_metrics(task_type: str, rows: list[dict[str, Any]]) -> dict[str, float]:
    if task_type in {"classification", "quality_judgement"}:
        return _single_label(rows)
    if task_type == "tagging":
        return _tagging(rows)
    if task_type == "structured_extraction":
        return _extraction(rows)
    if task_type == "rubric_scoring":
        return _rubric(rows)
    raise ValueError(f"unsupported task_type: {task_type}")


def _single_label(rows: list[dict[str, Any]]) -> dict[str, float]:
    golds = [_norm(row.get("gold")) for row in rows]
    preds = [_norm(row.get("prediction")) for row in rows]
    labels = sorted(set(golds) | set(preds))
    total = len(rows)
    correct = sum(1 for gold, pred in zip(golds, preds) if gold == pred)
    precisions, recalls, f1s = [], [], []
    for label in labels:
        tp = sum(1 for gold, pred in zip(golds, preds) if gold == label and pred == label)
        fp = sum(1 for gold, pred in zip(golds, preds) if gold != label and pred == label)
        fn = sum(1 for gold, pred in zip(golds, preds) if gold == label and pred != label)
        precision = _safe_div(tp, tp + fp)
        recall = _safe_div(tp, tp + fn)
        precisions.append(precision)
        recalls.append(recall)
        f1s.append(_safe_div(2 * precision * recall, precision + recall))
    return {
        "accuracy": _safe_div(correct, total),
        "macro_precision": _mean(precisions),
        "macro_recall": _mean(recalls),
        "macro_f1": _mean(f1s),
    }


def _tagging(rows: list[dict[str, Any]]) -> dict[str, float]:
    tp = fp = fn = exact = total_labels = correct_labels = 0
    for row in rows:
        expected = _as_set(row.get("gold"))
        predicted = _as_set(row.get("prediction"))
        tp += len(expected & predicted)
        fp += len(predicted - expected)
        fn += len(expected - predicted)
        total_labels += len(expected | predicted)
        correct_labels += len(expected & predicted)
        if expected == predicted:
            exact += 1
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    return {
        "micro_precision": precision,
        "micro_recall": recall,
        "micro_f1": _safe_div(2 * precision * recall, precision + recall),
        "exact_match": _safe_div(exact, len(rows)),
        "label_regression_rate": 1 - _safe_div(correct_labels, total_labels) if total_labels else 0.0,
    }


def _extraction(rows: list[dict[str, Any]]) -> dict[str, float]:
    correct = total = missing = extra = predicted_total = 0
    for row in rows:
        expected = row.get("gold") or {}
        predicted = _as_dict(row.get("prediction"))
        expected_keys = set(expected)
        predicted_keys = set(predicted)
        predicted_total += len(predicted_keys)
        for key in expected_keys:
            total += 1
            if key not in predicted_keys:
                missing += 1
            elif str(predicted.get(key)) == str(expected.get(key)):
                correct += 1
        extra += len(predicted_keys - expected_keys)
    precision = _safe_div(correct, predicted_total)
    recall = _safe_div(correct, total)
    return {
        "field_accuracy": _safe_div(correct, total),
        "field_f1": _safe_div(2 * precision * recall, precision + recall),
        "missing_field_rate": _safe_div(missing, total),
        "extra_field_rate": _safe_div(extra, total + extra),
    }


def _rubric(rows: list[dict[str, Any]]) -> dict[str, float]:
    errors = []
    for row in rows:
        gold = _as_number(row.get("gold"))
        pred = _as_number(row.get("prediction"))
        if gold is None or pred is None:
            # non-numeric prediction counts as a max-distance miss, not 0 error
            errors.append(float("inf"))
        else:
            errors.append(abs(gold - pred))
    exact = sum(1 for error in errors if error == 0)
    within_1 = sum(1 for error in errors if error <= 1)
    finite_errors = [error for error in errors if error != float("inf")]
    return {
        "exact_match": _safe_div(exact, len(rows)),
        "within_1_accuracy": _safe_div(within_1, len(rows)),
        "mae": _mean(finite_errors) if len(finite_errors) == len(errors) else float("inf"),
    }


def _norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _as_set(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        return {str(item).strip() for item in value}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return {str(item).strip() for item in parsed}
        except (json.JSONDecodeError, ValueError):
            pass
    return {str(value).strip()}


def _as_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
    return value if isinstance(value, dict) else {}


def _as_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)
