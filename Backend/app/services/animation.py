"""Select actual execution behavior, serialize one event, persist it, and correlate ACK."""

from __future__ import annotations

from typing import Any

from app.animations.package import map_package_data, map_package_sort, serialize_package
from app.animations.registry import build_payload
from app.animations.river import map_river_recursion, serialize_river
from app.animations.rescue import map_rescue_legacy, map_rescue_path, serialize_rescue
from app.animations.traffic import serialize_invalid_preview, serialize_main_sequence
from app.database import create_animation_event, get_attempt, get_executions
from app.ids import new_animation_run_id
from app.questions.registry import get_question


def create_animation(attempt_id: str, *, mode: str, selected_test_id: str | None = None) -> dict[str, Any]:
    attempt = get_attempt(attempt_id)
    if not attempt:
        raise KeyError(attempt_id)
    question = get_question(attempt["question_code"])
    if not question.animation_adapter:
        raise ValueError("Question has no animation adapter.")
    if mode == "FINAL" and attempt.get("completed_at") is None:
        raise PermissionError("Run/Submit must be completed before animation.")

    executions = get_executions(attempt_id)
    evaluation = attempt.get("evaluation_data") or {}

    if question.animation_adapter == "RESCUE_RL_LEGACY":
        return _create_rescue_legacy_animation(
            attempt=attempt,
            executions=executions,
            evaluation=evaluation,
        )

    if question.animation_adapter in {"RESCUE_PATH_CHECK", "RESCUE_BFS", "RESCUE_BEST_ROUTE"}:
        return _create_rescue_animation(
            attempt=attempt,
            executions=executions,
            mode=mode,
            selected_test_id=selected_test_id,
        )

    animation_run_id = new_animation_run_id()
    if question.animation_adapter == "TRAFFIC_SEQUENCE":
        selected = _build_traffic(animation_run_id, executions, mode, selected_test_id)
    elif question.animation_adapter == "M04_PACKAGE_DATA_ANALYSIS":
        selected = _build_package(animation_run_id, executions, mode, selected_test_id)
    elif question.animation_adapter == "PACKAGE_SORT":
        selected = _build_package_sort(animation_run_id, attempt, executions, mode, selected_test_id)
    elif question.animation_adapter == "RIVER_RECURSION":
        selected = _build_river(animation_run_id, executions)
    else:
        visible = [item for item in executions if item["test_visibility"] == "VISIBLE"]
        execution = _select_execution(attempt, visible, mode, selected_test_id)
        if not execution:
            raise ValueError("No visible execution can be animated.")
        payload, mapped = build_payload(
            adapter=question.animation_adapter,
            animation_run_id=animation_run_id,
            attempt=attempt,
            evaluation=evaluation,
            execution=execution,
        )
        normalized = execution.get("normalized_result") or {}
        selected = {
            "execution": execution,
            "animation_case_id": normalized.get("animation_case_id") or execution["test_id"],
            "test_id": execution["test_id"],
            "payload": payload,
            "selected_behavior": mapped,
        }

    execution = selected["execution"]
    record = {
        "animation_run_id": animation_run_id,
        "attempt_id": attempt_id,
        "execution_id": execution["execution_id"],
        "animation_case_id": selected["animation_case_id"],
        "question_code": attempt["question_code"],
        "test_id": selected["test_id"],
        "visible_test_id": selected["test_id"],
        "scene": attempt["scene_code"],
        "payload": selected["payload"],
        "selected_behavior": selected["selected_behavior"],
    }
    create_animation_event(record)
    return record


def _build_traffic(
    animation_run_id: str,
    executions: list[dict[str, Any]],
    mode: str,
    selected_test_id: str | None,
) -> dict[str, Any]:
    by_id = {item["test_id"]: item for item in executions if item["test_visibility"] == "VISIBLE"}
    valid_ids = ("VISIBLE-YELLOW", "VISIBLE-RED", "VISIBLE-GREEN")
    if selected_test_id == "VISIBLE-INVALID":
        invalid = by_id.get("VISIBLE-INVALID")
        if not invalid:
            raise ValueError("VISIBLE-INVALID execution is unavailable.")
        payload, mapped = serialize_invalid_preview(animation_run_id, invalid["normalized_result"])
        mapped["source_execution_ids"] = {"invalid_execution_id": invalid["execution_id"]}
        mapped["selected_normalized_behavior"] = invalid["normalized_result"]
        return {
            "execution": invalid,
            "animation_case_id": "VISIBLE-INVALID",
            "test_id": "VISIBLE-INVALID",
            "payload": payload,
            "selected_behavior": mapped,
        }

    if mode == "PREVIEW" and selected_test_id is None:
        valid_failed = any(not bool(by_id.get(test_id, {}).get("case_behavior_correct")) for test_id in valid_ids)
        invalid = by_id.get("VISIBLE-INVALID")
        invalid_failed = invalid is not None and not bool(invalid.get("case_behavior_correct"))
        if not valid_failed and invalid_failed:
            payload, mapped = serialize_invalid_preview(animation_run_id, invalid["normalized_result"])
            mapped["source_execution_ids"] = {"invalid_execution_id": invalid["execution_id"]}
            mapped["selected_normalized_behavior"] = invalid["normalized_result"]
            return {
                "execution": invalid,
                "animation_case_id": "VISIBLE-INVALID",
                "test_id": "VISIBLE-INVALID",
                "payload": payload,
                "selected_behavior": mapped,
            }

    missing = [test_id for test_id in valid_ids if test_id not in by_id]
    if missing:
        raise ValueError(f"Traffic executions missing: {missing}")
    normalized = {test_id: by_id[test_id]["normalized_result"] for test_id in valid_ids}
    payload, mapped = serialize_main_sequence(animation_run_id, normalized)
    mapped["source_execution_ids"] = {
        "yellow_execution_id": by_id["VISIBLE-YELLOW"]["execution_id"],
        "red_execution_id": by_id["VISIBLE-RED"]["execution_id"],
        "green_execution_id": by_id["VISIBLE-GREEN"]["execution_id"],
    }
    mapped["selected_case_results"] = [normalized[test_id] for test_id in valid_ids]
    return {
        "execution": by_id["VISIBLE-YELLOW"],
        "animation_case_id": "TRAFFIC-MAIN-SEQUENCE",
        "test_id": "TRAFFIC-MAIN-SEQUENCE",
        "payload": payload,
        "selected_behavior": mapped,
    }


def _build_package(
    animation_run_id: str,
    executions: list[dict[str, Any]],
    mode: str,
    selected_test_id: str | None,
) -> dict[str, Any]:
    visible = [item for item in executions if item["test_visibility"] == "VISIBLE"]
    if selected_test_id:
        execution = next((item for item in visible if item["test_id"] == selected_test_id), None)
    elif mode == "FINAL":
        execution = next((item for item in visible if item["test_id"] == "VISIBLE-1"), None)
    else:
        execution = next((item for item in visible if not item["case_behavior_correct"]), None) or (visible[0] if visible else None)
    if not execution:
        raise ValueError("No visible Package execution can be animated.")
    normalized = execution["normalized_result"]
    if not normalized.get("animation_case_id"):
        raise ValueError("Selected Package case blocks animation because its return is malformed.")
    steps = map_package_data(normalized, include_labels=True)
    payload = serialize_package(animation_run_id, steps)
    return {
        "execution": execution,
        "animation_case_id": normalized["animation_case_id"],
        "test_id": execution["test_id"],
        "payload": payload,
        "selected_behavior": {
            "steps": steps,
            "selected_normalized_behavior": normalized,
            "source_execution_ids": {"execution_id": execution["execution_id"]},
            "selected_test_input": normalized.get("input_data") or {},
            "visual_contract": {
                "slot_order_confirmed": True,
                "slot_order": "LEFT_TO_RIGHT",
                "package_labels_visible": True,
                "dynamic_label_source": "SELECTED_VISIBLE_TEST_INPUT",
                "editor_legend_required": True,
            },
        },
    }


def _build_package_sort(
    animation_run_id: str,
    attempt: dict[str, Any],
    executions: list[dict[str, Any]],
    mode: str,
    selected_test_id: str | None,
) -> dict[str, Any]:
    visible = [item for item in executions if item.get("test_visibility") == "VISIBLE"]
    execution = _select_execution(attempt, visible, mode, selected_test_id)
    if not execution:
        raise ValueError("No visible Package Sort execution can be animated.")
    cases = (attempt.get("input_data") or {}).get("cases") or []
    case = next((item for item in cases if item.get("test_id") == execution.get("test_id")), None)
    if case is None and isinstance(execution.get("test_id"), str):
        try:
            index = int(execution["test_id"].split("-", 1)[1]) - 1
        except (ValueError, IndexError):
            index = -1
        if 0 <= index < len(cases):
            case = cases[index]
    case = case or {}
    input_values = list(case.get("values") or (case.get("input_data") or {}).get("values") or [])
    normalized = execution.get("normalized_result") or {}
    actual_output = str(normalized.get("actual") or execution.get("stdout_raw") or "").strip()
    steps, mapping = map_package_sort(input_values, actual_output)
    payload = serialize_package(animation_run_id, steps)
    return {
        "execution": execution,
        "animation_case_id": normalized.get("animation_case_id") or execution["test_id"],
        "test_id": execution["test_id"],
        "payload": payload,
        "selected_behavior": {
            "steps": steps,
            "selected_test_input": {"values": input_values},
            "selected_normalized_behavior": normalized,
            "actual_sort_mapping": mapping,
            "fields": [",".join(map(str, input_values)), actual_output],
            "source_execution_ids": {"execution_id": execution["execution_id"]},
            "visual_contract": {
                "package_labels_visible": True,
                "dynamic_label_source": "SELECTED_VISIBLE_TEST_INPUT",
                "slot_order": "LEFT_TO_RIGHT",
            },
        },
    }


def _build_river(animation_run_id: str, executions: list[dict[str, Any]]) -> dict[str, Any]:
    execution = next((item for item in executions if item["test_id"] == "CANONICAL"), None)
    if not execution:
        raise ValueError("Canonical River execution is unavailable.")
    normalized = execution["normalized_result"]
    steps = map_river_recursion(normalized)
    payload = serialize_river(animation_run_id, steps)
    return {
        "execution": execution,
        "animation_case_id": "canonical",
        "test_id": "CANONICAL",
        "payload": payload,
        "selected_behavior": {
            "steps": steps,
            "selected_normalized_behavior": normalized,
            "source_execution_ids": {"canonical_execution_id": execution["execution_id"]},
        },
    }


def _create_rescue_animation(
    *,
    attempt: dict[str, Any],
    executions: list[dict[str, Any]],
    mode: str,
    selected_test_id: str | None,
) -> dict[str, Any]:
    """Select/map first, then create the globally unique run ID and payload."""

    eligible = [
        item for item in executions
        if item.get("test_visibility") in {"CANONICAL", "VISIBLE"}
    ]
    if selected_test_id:
        execution = next((item for item in eligible if item["test_id"] == selected_test_id), None)
    elif mode == "FINAL":
        execution = next(
            (item for item in eligible if item["test_id"] == "VISIBLE-1"),
            None,
        )
    else:
        execution = next((item for item in eligible if not item["case_behavior_correct"]), None)
        if execution is None:
            execution = next((item for item in eligible if item["test_id"] == "VISIBLE-1"), None)

    if not execution:
        raise ValueError("No visible Rescue execution can be animated.")
    normalized = execution.get("normalized_result") or {}
    if execution.get("test_visibility") == "HIDDEN":
        raise ValueError("Hidden Rescue test cannot be animated.")
    technique_required = "BFS" if attempt.get("question_code") == "H04_RESCUE_BFS" else None
    steps = map_rescue_path(
        normalized,
        technique_required=technique_required,
        technique_passed=bool(attempt.get("technique_passed", True)),
    )
    if not steps:
        raise ValueError("Selected Rescue case has no safe animation action.")

    animation_run_id = new_animation_run_id()
    payload = serialize_rescue(animation_run_id, steps)
    record = {
        "animation_run_id": animation_run_id,
        "attempt_id": attempt["attempt_id"],
        "execution_id": execution["execution_id"],
        "animation_case_id": normalized.get("animation_case_id") or execution["test_id"],
        "question_code": attempt["question_code"],
        "test_id": execution["test_id"],
        "visible_test_id": execution["test_id"],
        "scene": attempt["scene_code"],
        "payload": payload,
        "selected_behavior": {
            "steps": steps,
            "maze_version": normalized.get("maze_version"),
            "selected_test_input": {
                "start": normalized.get("start"),
                "target": normalized.get("target"),
                "walls": normalized.get("walls"),
                "input_steps": normalized.get("input_steps"),
            },
            "selected_normalized_behavior": normalized,
            "source_execution_ids": {"execution_id": execution["execution_id"]},
        },
    }
    create_animation_event(record)
    return record



def _create_rescue_legacy_animation(
    *,
    attempt: dict[str, Any],
    executions: list[dict[str, Any]],
    evaluation: dict[str, Any],
) -> dict[str, Any]:
    """Serialize legacy Q-learning output through the same actor-safe protocol."""

    animation = evaluation.get("animation") or {}
    path = animation.get("path") or []
    case = (attempt.get("input_data") or {}).get("animation_case") or {}
    steps, evidence = map_rescue_legacy(
        path=list(path),
        start=list(case.get("start") or [0, 0]),
        target=list(case.get("target") or [4, 4]),
        walls=[list(item) for item in case.get("walls") or []],
    )
    if not steps:
        raise ValueError("Legacy Rescue result has no safe animation action.")

    animation_run_id = new_animation_run_id()
    payload = serialize_rescue(animation_run_id, steps)
    execution = next(
        (item for item in executions if item.get("test_visibility") == "VISIBLE"),
        executions[0] if executions else None,
    )
    if execution is None:
        raise ValueError("Legacy Rescue execution is unavailable.")

    record = {
        "animation_run_id": animation_run_id,
        "attempt_id": attempt["attempt_id"],
        "execution_id": execution["execution_id"],
        "animation_case_id": "LEGACY-DEMO",
        "question_code": attempt["question_code"],
        "test_id": execution["test_id"],
        "visible_test_id": execution["test_id"],
        "scene": attempt["scene_code"],
        "payload": payload,
        "selected_behavior": {
            "steps": steps,
            "selected_test_input": {
                "start": evidence.get("start"),
                "target": evidence.get("target"),
                "walls": evidence.get("walls"),
            },
            "selected_normalized_behavior": evidence,
            "source_execution_ids": {"execution_id": execution["execution_id"]},
            "legacy_adapter": "U_D_L_R_TO_UP_DOWN_LEFT_RIGHT",
        },
    }
    create_animation_event(record)
    return record

def _select_execution(
    attempt: dict[str, Any],
    executions: list[dict[str, Any]],
    mode: str,
    selected_test_id: str | None,
) -> dict[str, Any] | None:
    if selected_test_id:
        return next((item for item in executions if item["test_id"] == selected_test_id), None)
    if mode == "PREVIEW":
        return next((item for item in executions if not bool(item["case_behavior_correct"])), None) or (executions[0] if executions else None)
    preferred = attempt.get("input_data", {}).get("final_animation_case_id")
    if preferred:
        selected = next((item for item in executions if item["test_id"] == preferred), None)
        if selected:
            return selected
    if bool(attempt.get("overall_correct")):
        return next((item for item in executions if bool(item["case_behavior_correct"])), None)
    return next((item for item in executions if not bool(item["case_behavior_correct"])), None) or (executions[0] if executions else None)
