"""Deterministic student scoring presentation built on evaluator output.

The correctness evaluator remains authoritative. This module only converts the
existing functional test score and required-technique result into a clear
100-point breakdown for students.
"""

from __future__ import annotations

from typing import Any


def _clamp(value: Any, minimum: float = 0.0, maximum: float = 100.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = 0.0
    return max(minimum, min(maximum, numeric))


def apply_student_score(question: Any, result: Any) -> None:
    """Apply the public score model without changing correctness decisions.

    - Questions without a required technique: functional tests are worth 100.
    - Questions with a required technique: functional tests are worth 80 and
      the required technique is worth 20.
    """

    functional_percent = _clamp(getattr(result, "score", 0.0))
    required_technique = getattr(question, "required_technique", None)
    technique_result = getattr(result, "technique_result", None)
    technique_passed = bool(getattr(technique_result, "passed", True))

    if required_technique:
        functional_max = 80.0
        technique_max = 20.0
        functional_points = round(functional_percent * functional_max / 100.0, 1)
        technique_points = technique_max if technique_passed else 0.0
        breakdown = [
            {
                "key": "functional",
                "label": "Functional Tests",
                "points": functional_points,
                "max_points": functional_max,
                "passed": functional_percent >= 100.0,
            },
            {
                "key": "technique",
                "label": "Required Technique",
                "detail": str(required_technique).upper(),
                "points": technique_points,
                "max_points": technique_max,
                "passed": technique_passed,
            },
        ]
        final_score = round(functional_points + technique_points, 1)
    else:
        functional_max = 100.0
        functional_points = round(functional_percent, 1)
        breakdown = [
            {
                "key": "functional",
                "label": "Functional Tests",
                "points": functional_points,
                "max_points": functional_max,
                "passed": functional_percent >= 100.0,
            }
        ]
        final_score = functional_points

    result.functional_score = round(functional_percent, 1)
    result.score = final_score
    result.score_breakdown = breakdown
