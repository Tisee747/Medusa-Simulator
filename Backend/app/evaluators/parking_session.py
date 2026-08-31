"""Exact parser and evaluator for M03_PARKING_SESSION_TOTAL."""

from __future__ import annotations

import re
from typing import Any

from app.code_runner import run_source
from app.evaluators.technique import evaluate_technique
from app.ids import new_execution_id
from app.questions.base import EvaluationResult

_RATES = {"MOTOR": 2000, "MOBIL": 5000, "TRUK": 8000}
_INTEGER = re.compile(r"^[+-]?\d+$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def expected_fee(vehicle: str, hours: int) -> int:
    return _RATES[vehicle] * hours


def sanitize_display_tokens(*tokens: object) -> str:
    text = " ".join(str(token) for token in tokens)
    text = text.replace(">", " ").replace(",", " ").replace("=", " ").replace("|", " ")
    text = _CONTROL.sub(" ", text)
    text = " ".join(text.split()).strip()
    if not text:
        return "OUTPUT_TIDAK_VALID"
    result = text.replace(" ", "_")[:80]
    return result or "OUTPUT_TIDAK_VALID"


def parse_parking_stdout(
    actual_raw: str,
    vehicles: list[dict[str, Any]],
    *,
    animation_case_id: str,
    execution_id: str,
) -> dict[str, Any]:
    parse_text = actual_raw
    if parse_text.endswith("\r\n"):
        parse_text = parse_text[:-2]
    elif parse_text.endswith("\n") or parse_text.endswith("\r"):
        parse_text = parse_text[:-1]
    parse_text = parse_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [] if parse_text == "" else parse_text.split("\n")

    if lines:
        actual_total_line_raw = lines[-1]
        candidates = lines[:-1]
    else:
        actual_total_line_raw = None
        candidates = []

    total_present = actual_total_line_raw is not None
    total_tokens = actual_total_line_raw.split() if actual_total_line_raw is not None else []
    total_format = len(total_tokens) == 2 and bool(_INTEGER.fullmatch(total_tokens[1]))
    actual_total_label = total_tokens[0] if total_format else None
    actual_total = int(total_tokens[1]) if total_format else None
    total_display = (
        sanitize_display_tokens(actual_total_label, actual_total)
        if total_format
        else "OUTPUT_TIDAK_VALID"
    )

    normalized_vehicles: list[dict[str, Any]] = []
    premature_total = False
    for index, input_item in enumerate(vehicles):
        raw = candidates[index] if index < len(candidates) else None
        line_present = raw is not None
        tokens = raw.split() if raw is not None else []
        is_premature = bool(tokens and tokens[0] == "TOTAL")
        premature_total = premature_total or is_premature
        line_format_valid = (
            line_present
            and not is_premature
            and len(tokens) == 2
            and bool(_INTEGER.fullmatch(tokens[1]))
        )
        actual_vehicle = tokens[0] if line_format_valid else None
        actual_fee = int(tokens[1]) if line_format_valid else None
        expected = expected_fee(input_item["vehicle"], int(input_item["hours"]))
        vehicle_name_correct = line_format_valid and actual_vehicle == input_item["vehicle"]
        fee_correct = line_format_valid and actual_fee == expected
        correct = bool(line_present and line_format_valid and vehicle_name_correct and fee_correct)
        display = (
            sanitize_display_tokens(actual_vehicle, actual_fee)
            if line_format_valid
            else "OUTPUT_TIDAK_VALID"
        )
        normalized_vehicles.append(
            {
                "vehicle": input_item["vehicle"],
                "hours": int(input_item["hours"]),
                "actual_line_raw": raw,
                "actual_vehicle": actual_vehicle,
                "actual_fee": actual_fee,
                "actual_line_display_text": display,
                "expected_fee": expected,
                "line_present": line_present,
                "line_format_valid": bool(line_format_valid),
                "vehicle_name_correct": bool(vehicle_name_correct),
                "fee_correct": bool(fee_correct),
                "correct": correct,
            }
        )

    expected_total = sum(expected_fee(item["vehicle"], int(item["hours"])) for item in vehicles)
    count_expected = len(vehicles)
    count_actual = len(candidates)
    count_correct = count_actual == count_expected
    no_extra_output = count_actual <= count_expected
    total_label_correct = total_format and actual_total_label == "TOTAL"
    total_value_correct = total_format and actual_total == expected_total
    output_structure_correct = bool(
        count_correct
        and total_present
        and total_format
        and total_label_correct
        and not premature_total
        and no_extra_output
    )
    case_correct = bool(
        output_structure_correct
        and all(item["correct"] for item in normalized_vehicles)
        and total_value_correct
        and no_extra_output
    )

    return {
        "animation_case_id": animation_case_id,
        "execution_id": execution_id,
        "vehicles": normalized_vehicles,
        "actual_raw": actual_raw,
        "actual_total_line_raw": actual_total_line_raw,
        "actual_total_label": actual_total_label,
        "actual_total": actual_total,
        "actual_total_line_display_text": total_display,
        "expected_total": expected_total,
        "transaction_line_count_expected": count_expected,
        "transaction_line_count_actual": count_actual,
        "transaction_line_count_correct": count_correct,
        "total_line_present": total_present,
        "total_line_format_valid": bool(total_format),
        "total_label_correct": bool(total_label_correct),
        "total_value_correct": bool(total_value_correct),
        "premature_total_found": premature_total,
        "no_extra_output": no_extra_output,
        "output_structure_correct": output_structure_correct,
        "case_behavior_correct": case_correct,
    }


def evaluate_parking_session(source_code: str, data: dict[str, Any]) -> EvaluationResult:
    executions: list[dict[str, Any]] = []
    normalized_cases: list[dict[str, Any]] = []
    visible_results: list[dict[str, Any]] = []

    for index, case in enumerate(data["cases"], 1):
        execution_id = new_execution_id()
        run = run_source(source_code, stdin_text=case["input"])
        normalized = parse_parking_stdout(
            run.stdout,
            case["vehicles"],
            animation_case_id=case.get("animation_case_id", f"VISIBLE-{index}"),
            execution_id=execution_id,
        )
        if not run.ok:
            normalized["case_behavior_correct"] = False
        error_type = None
        error_detail = None
        status = "COMPLETED"
        if run.validation_error:
            status = "SYNTAX_ERROR" if run.validation_error.startswith("SyntaxError") else "RUNTIME_ERROR"
            error_type, error_detail = status, run.validation_error
        elif run.timed_out:
            status, error_type, error_detail = "TIMEOUT", "TIMEOUT", "Program melewati batas waktu."
        elif run.output_limit_exceeded:
            status, error_type, error_detail = "RUNTIME_ERROR", "OUTPUT_LIMIT", "Output melebihi batas."
        elif not run.ok:
            status, error_type, error_detail = "RUNTIME_ERROR", "RUNTIME_ERROR", run.stderr.strip() or "Runtime error."

        test_id = case.get("test_id", f"VISIBLE-{index}")
        feedback = {
            "test_id": test_id,
            "name": case.get("name", test_id),
            "input": case["input"].rstrip(),
            "expected": case["expected_output"],
            "actual": run.stdout,
            "passed": normalized["case_behavior_correct"],
            "error": error_detail or "",
            "visible": True,
            "execution_id": execution_id,
        }
        visible_results.append(feedback)
        normalized_cases.append(normalized)
        executions.append(
            {
                "execution_id": execution_id,
                "test_id": test_id,
                "test_visibility": "VISIBLE",
                "status": status,
                "stdout_raw": run.stdout,
                "stderr_raw": run.stderr,
                "return_value_serialized": None,
                "case_behavior_correct": normalized["case_behavior_correct"],
                "duration_ms": run.duration_ms,
                "error_type": error_type,
                "error_detail": error_detail,
                "feedback": feedback,
                "normalized_result": normalized,
                "evaluation_result": {"case_behavior_correct": normalized["case_behavior_correct"]},
            }
        )

    behavior_correct = all(item["case_behavior_correct"] for item in normalized_cases)
    technique = evaluate_technique(source_code, "WHILE")
    overall = behavior_correct and technique.passed
    passed = sum(1 for item in normalized_cases if item["case_behavior_correct"])
    score = round(100.0 * passed / max(1, len(normalized_cases)), 1)
    first_error = next((item["error"] for item in visible_results if item["error"]), "")
    status = "CORRECT" if overall else ("ERROR" if first_error else "WRONG")
    return EvaluationResult(
        status=status,
        score=score,
        message=(
            "Semua sesi dan teknik while benar."
            if overall
            else f"{passed} dari {len(normalized_cases)} visible test benar."
        ),
        program_output=normalized_cases[0]["actual_raw"] if normalized_cases else "",
        error_message=first_error or ("Teknik while wajib belum terpenuhi." if behavior_correct and not technique.passed else ""),
        stdout="\n---\n".join(item["stdout_raw"] for item in executions),
        stderr="\n---\n".join(item["stderr_raw"] for item in executions),
        visible_results=visible_results,
        hidden_summary={"total": 0, "passed": 0},
        executions=executions,
        normalized_cases=normalized_cases,
        case_results=[
            {
                "test_id": execution["test_id"],
                "execution_id": execution["execution_id"],
                "case_behavior_correct": execution["case_behavior_correct"],
            }
            for execution in executions
        ],
        behavior_correct=behavior_correct,
        technique_result=technique,
        overall_correct=overall,
    )
