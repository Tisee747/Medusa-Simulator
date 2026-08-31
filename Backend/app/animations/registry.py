"""Scene-based animation mapping; question modules never build raw LSL payloads."""

from __future__ import annotations

from typing import Any

from app.animations.parking import map_parking_loop, map_parking_session, map_parking_single, serialize_parking


def build_payload(
    *,
    adapter: str,
    animation_run_id: str,
    attempt: dict[str, Any],
    evaluation: dict[str, Any],
    execution: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    normalized = execution.get("normalized_result") or {}
    actual = str(normalized.get("actual", ""))
    input_data = normalized.get("input_data") or {}

    if adapter == "M03_PARKING_SESSION_TOTAL":
        steps = map_parking_session(normalized, technique_passed=bool(attempt.get("technique_passed", True)))
        return serialize_parking(animation_run_id, steps), {"steps": steps, "normalized": normalized}

    if adapter == "PARKING_SINGLE":
        steps = map_parking_single(normalized)
        return serialize_parking(animation_run_id, steps), {"steps": steps, "normalized": normalized}

    if adapter == "PARKING_LOOP":
        case = _case_for_execution(attempt, execution)
        steps = map_parking_loop(
            normalized,
            vehicles=list(case.get("vehicles") or []),
            technique_passed=bool(attempt.get("technique_passed", True)),
        )
        return serialize_parking(animation_run_id, steps), {
            "steps": steps,
            "normalized": normalized,
            "selected_test_input": {"vehicles": list(case.get("vehicles") or [])},
        }

    if adapter == "TRAFFIC_ACTION":
        color = input_data.get("color", "")
        expected = normalized.get("expected", "")
        fields = [color, actual, expected]
    elif adapter == "PACKAGE_SORT":
        case = _case_for_execution(attempt, execution)
        input_values = case.get("values", [])
        fields = [",".join(map(str, input_values)), ",".join(actual.split())]
    elif adapter == "RIVER_PATH":
        path = evaluation.get("animation", {}).get("path") or evaluation.get("program_output", "").split("|")
        fields = [",".join(item for item in path if item)]
    elif adapter == "RESCUE_RL_LEGACY":
        animation = evaluation.get("animation", {})
        fields = [str(animation.get("seed", 0)), "".join(animation.get("path", [])), str(animation.get("score", 0))]
    else:
        raise ValueError(f"Animation adapter not registered: {adapter}")

    # Compatibility format for the six legacy scene controllers.
    payload = "|".join([
        "RESULT", attempt["question_code"], attempt["scene_code"], attempt["attempt_id"], *map(str, fields)
    ])
    return payload, {"fields": fields, "normalized": normalized, "animation_run_id": animation_run_id}


def _case_for_execution(attempt: dict[str, Any], execution: dict[str, Any]) -> dict[str, Any]:
    test_id = execution.get("test_id")
    cases = attempt.get("input_data", {}).get("cases", [])
    for case in cases:
        if case.get("test_id") == test_id:
            return case

    # Attempts created by the older Package Sort module did not store test_id
    # inside each case. Match VISIBLE-N to its original case position so those
    # already-open attempts remain animatable after deployment.
    if isinstance(test_id, str) and (test_id.startswith("VISIBLE-") or test_id.startswith("TEST-")):
        try:
            index = int(test_id.split("-", 1)[1]) - 1
        except ValueError:
            index = -1
        if 0 <= index < len(cases):
            return cases[index]
    return {}
