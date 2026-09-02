"""Guardrail checks. Decides if a candidate is eligible to replace current prompt.

Pure threshold comparison driven by the eval_plan; no inference.
Logic follows SKILL_DESIGN.md §3 tool_check_guardrails.
"""
from __future__ import annotations

from typing import Any

from .metrics import LOWER_IS_BETTER


def check_guardrails(
    candidate_metrics: dict[str, float],
    baseline_metrics: dict[str, float],
    baseline_correct_ids: list[str],
    candidate_results: list[dict[str, Any]],
    eval_plan: dict[str, Any],
    noise_floor_rate: float = 0.0,
) -> dict[str, Any]:
    """Decide candidate eligibility.

    ``noise_floor_rate`` accounts for a stochastic target model. When the model
    is sampled (temperature > 0), re-running the *same* prompt flips some
    previously-correct rows purely by chance. On small eval sets that jitter can
    exceed the fixed ``max_correct_to_wrong_rate`` and would wrongly disqualify
    every candidate — including the unchanged ``hold`` prompt. Pass the ``hold``
    candidate's own correct_to_wrong_rate as ``noise_floor_rate`` so the check
    judges regressions *above the measured noise floor*: the effective threshold
    becomes ``max_correct_to_wrong_rate + noise_floor_rate``. Default 0.0 keeps
    the strict behavior for deterministic models."""
    primary = eval_plan["primary_metric"]
    secondary = eval_plan.get("secondary_metrics", [])
    guardrails = eval_plan.get("guardrails", {})

    primary_improved = _better(primary, candidate_metrics.get(primary), baseline_metrics.get(primary))

    baseline_correct = {str(case_id) for case_id in baseline_correct_ids}
    results_by_id = {str(row.get("id")): row for row in candidate_results}
    correct_to_wrong = [
        case_id
        for case_id in baseline_correct
        if not results_by_id.get(case_id, {}).get("is_correct", False)
    ]
    correct_to_wrong_count = len(correct_to_wrong)
    correct_to_wrong_rate = _safe_div(correct_to_wrong_count, len(baseline_correct))

    min_ratio = float(guardrails.get("min_secondary_metric_ratio", 0.95))
    secondary_violations = []
    for metric in secondary:
        base = baseline_metrics.get(metric)
        cand = candidate_metrics.get(metric)
        if base is None or cand is None:
            continue
        if not _passes_secondary(metric, cand, base, min_ratio):
            secondary_violations.append(metric)

    empty_predictions = []
    if guardrails.get("no_empty_prediction", False):
        empty_predictions = [
            str(row.get("id"))
            for row in candidate_results
            if "prediction" in row and _is_empty_prediction(row.get("prediction"))
        ]

    max_rate = float(guardrails.get("max_correct_to_wrong_rate", 0.05))
    noise_floor = max(0.0, float(noise_floor_rate))
    effective_max_rate = max_rate + noise_floor

    eligible = True
    reason = "主指标提升，辅助指标和 Guardrail 通过"
    if not primary_improved:
        eligible = False
        reason = f"主指标 {primary} 未超过 baseline"
    elif secondary_violations:
        eligible = False
        reason = f"辅助指标退化: {', '.join(secondary_violations)}"
    elif correct_to_wrong_rate > effective_max_rate:
        eligible = False
        floor_note = f" = {max_rate} + 噪声地板 {noise_floor:.3f}" if noise_floor else ""
        reason = f"原本正确样本退化过多 ({correct_to_wrong_rate:.3f} > {effective_max_rate:.3f}{floor_note})"
    elif empty_predictions:
        eligible = False
        reason = f"存在空预测: {', '.join(empty_predictions)}"

    return {
        "eligible": eligible,
        "primary_improved": primary_improved,
        "correct_to_wrong_count": correct_to_wrong_count,
        "correct_to_wrong_rate": correct_to_wrong_rate,
        "correct_to_wrong_ids": sorted(correct_to_wrong),
        "noise_floor_rate": noise_floor,
        "effective_max_correct_to_wrong_rate": effective_max_rate,
        "secondary_violations": secondary_violations,
        "empty_prediction_ids": empty_predictions,
        "reason": reason,
    }


def _passes_secondary(metric: str, candidate: float, baseline: float, min_ratio: float) -> bool:
    if metric in LOWER_IS_BETTER:
        # lower is better: candidate must not exceed baseline / min_ratio
        if baseline == 0:
            return candidate <= 0 or min_ratio >= 1
        return candidate <= baseline / min_ratio
    if baseline == 0:
        return True
    return _safe_div(candidate, baseline) >= min_ratio


def _better(metric: str, candidate: float | None, baseline: float | None) -> bool:
    if candidate is None or baseline is None:
        return False
    if metric in LOWER_IS_BETTER:
        return candidate < baseline
    return candidate > baseline


def _is_empty_prediction(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator
