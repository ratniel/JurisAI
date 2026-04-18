from __future__ import annotations

from typing import Any

ABSOLUTE_RETRIEVAL_GATE_NAME = "golden_seed_strict_v1"
ABSOLUTE_RETRIEVAL_GATE_THRESHOLDS = {
    "strict_record_pass_rate": 1.0,
    "per_record_min_recall_pass_rate": 1.0,
    "expected_filter_match_rate": 1.0,
    "zero_raw_hit_rate": 0.0,
}


def record_passes_min_recall(*, hits_at_k: int, min_recall_at_k: int) -> bool:
    return hits_at_k >= min_recall_at_k


def record_passes_absolute_gate(
    *,
    raw_hit_count: int,
    hits_at_k: int,
    min_recall_at_k: int,
    distractor_pass: bool,
    filter_match: bool,
) -> bool:
    return (
        raw_hit_count > 0
        and record_passes_min_recall(
            hits_at_k=hits_at_k,
            min_recall_at_k=min_recall_at_k,
        )
        and distractor_pass
        and filter_match
    )


def evaluate_summary_against_thresholds(
    *,
    summary: dict[str, Any],
    thresholds: dict[str, float] | None = None,
) -> list[str]:
    checks = thresholds or ABSOLUTE_RETRIEVAL_GATE_THRESHOLDS
    failures: list[str] = []

    for metric_name, expected_value in checks.items():
        actual_value = float(summary.get(metric_name, 0.0))
        if metric_name == "zero_raw_hit_rate":
            if actual_value > expected_value:
                failures.append(
                    f"{metric_name}={actual_value:.3f} exceeds {expected_value:.3f}"
                )
            continue

        if actual_value < expected_value:
            failures.append(
                f"{metric_name}={actual_value:.3f} is below {expected_value:.3f}"
            )

    return failures
