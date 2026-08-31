"""Exact stdout parser and evaluator for Traffic Soal 1."""

from __future__ import annotations

from typing import Any

from app.code_runner import run_source
from app.ids import new_execution_id
from app.questions.base import EvaluationResult, TechniqueResult

_RECOGNIZED = {"BERHENTI", "HATI_HATI", "JALAN", "TIDAK_VALID"}


def parse_traffic_stdout(stdout_raw: str, *, expected_action: str) -> dict[str, Any]:
    parse_text = stdout_raw
    if parse_text.endswith("\r\n"):
        parse_text = parse_text[:-2]
    elif parse_text.endswith("\n") or parse_text.endswith("\r"):
        parse_text = parse_text[:-1]
    parse_text = parse_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [] if parse_text == "" else parse_text.split("\n")

    line_present = bool(lines)
    single_line = len(lines) == 1
    actual_line_raw = lines[0] if single_line else None
    actual_action = actual_line_raw.strip().upper() if actual_line_raw is not None else None
    action_recognized = actual_action in _RECOGNIZED
    action_correct = action_recognized and actual_action == expected_action
    no_extra_output = single_line

    failure_type: str | None = None
    detail: str | None = None
    if not lines:
        failure_type = "EMPTY_OUTPUT"
        detail = "Program tidak mencetak tindakan."
    elif len(lines) != 1:
        failure_type = "MULTIPLE_OUTPUT_LINES"
        detail = "Output harus tepat satu baris tanpa debug print atau blank line tambahan."
    elif actual_action == "":
        failure_type = "MALFORMED_OUTPUT"
        detail = "Baris output kosong setelah whitespace dibersihkan."
    elif not action_recognized:
        failure_type = "MALFORMED_OUTPUT"
        detail = "Tindakan tidak termasuk token yang diterima evaluator."

    correct = (
        line_present
        and single_line
        and action_recognized
        and action_correct
        and no_extra_output
        and failure_type is None
    )
    return {
        "actual_line_raw": actual_line_raw,
        "actual_action": actual_action,
        "line_present": line_present,
        "single_line_output": single_line,
        "action_recognized": action_recognized,
        "action_correct": action_correct,
        "no_extra_output": no_extra_output,
        "case_behavior_correct": correct,
        "parse_failure": {"type": failure_type, "detail": detail},
    }


def evaluate_traffic(source_code: str, data: dict[str, Any]) -> EvaluationResult:
    executions: list[dict[str, Any]] = []
    normalized_cases: list[dict[str, Any]] = []
    visible_results: list[dict[str, Any]] = []
    case_results: list[dict[str, Any]] = []
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []

    for case in data["cases"]:
        execution_id = new_execution_id()
        run = run_source(source_code, stdin_text=case["input_raw"] + "\n")
        parsed = parse_traffic_stdout(run.stdout, expected_action=case["expected_action"])
        if run.output_limit_exceeded:
            parsed.update({
                "actual_line_raw": None,
                "actual_action": None,
                "action_recognized": False,
                "action_correct": False,
                "case_behavior_correct": False,
                "parse_failure": {"type": "OUTPUT_TOO_LONG", "detail": "Output melewati batas runner."},
            })
        if not run.ok:
            parsed["case_behavior_correct"] = False

        if run.validation_error:
            status = "SYNTAX_ERROR" if run.validation_error.startswith("SyntaxError") else "RUNTIME_ERROR"
            error_detail = run.validation_error
        elif run.timed_out:
            status = "TIMEOUT"
            error_detail = "Program melewati batas waktu."
        elif run.output_limit_exceeded:
            status = "RUNTIME_ERROR"
            error_detail = "Output melewati batas runner."
        elif not run.ok:
            status = "RUNTIME_ERROR"
            error_detail = run.stderr.strip() or "Runtime error."
        else:
            status = "COMPLETED"
            error_detail = parsed["parse_failure"]["detail"]

        normalized = {
            "execution_id": execution_id,
            "test_id": case["test_id"],
            "test_visibility": "VISIBLE",
            "animation_case_id": case["test_id"],
            "input_raw": case["input_raw"],
            "normalized_input_color": case["normalized_input_color"],
            "valid_input": case["valid_input"],
            "stdout_raw": run.stdout,
            "expected_action": case["expected_action"],
            **parsed,
            "input_data": {"color": case["normalized_input_color"]},
        }
        normalized_cases.append(normalized)
        passed = bool(normalized["case_behavior_correct"])
        result_item = {
            "test_id": case["test_id"],
            "name": case["name"],
            "input": case["input_raw"],
            "expected": case["expected_action"],
            "actual": normalized.get("actual_action"),
            "passed": passed,
            "error": error_detail or "",
            "visible": True,
            "execution_id": execution_id,
        }
        visible_results.append(result_item)
        case_results.append({
            "test_id": case["test_id"],
            "execution_id": execution_id,
            "test_visibility": "VISIBLE",
            "case_behavior_correct": passed,
        })
        executions.append({
            "execution_id": execution_id,
            "test_id": case["test_id"],
            "test_visibility": "VISIBLE",
            "status": status,
            "stdout_raw": run.stdout,
            "stderr_raw": run.stderr,
            "return_value_serialized": None,
            "case_behavior_correct": passed,
            "duration_ms": run.duration_ms,
            "error_type": None if status == "COMPLETED" and not parsed["parse_failure"]["type"] else (parsed["parse_failure"]["type"] or status),
            "error_detail": error_detail,
            "feedback": result_item,
            "normalized_result": normalized,
            "evaluation_result": {
                "action_correct": parsed["action_correct"],
                "expected_action": case["expected_action"],
                "actual_action": parsed["actual_action"],
            },
        })
        stdout_parts.append(run.stdout)
        stderr_parts.append(run.stderr)

    passed_count = sum(1 for item in case_results if item["case_behavior_correct"])
    behavior_correct = passed_count == len(case_results)
    score = round(100.0 * passed_count / max(1, len(case_results)), 1)
    first_error = next((item["error"] for item in visible_results if item["error"]), "")
    return EvaluationResult(
        status="CORRECT" if behavior_correct else ("ERROR" if first_error and any(e["status"] != "COMPLETED" for e in executions) else "WRONG"),
        score=score,
        message="Semua empat visible test berhasil." if behavior_correct else f"{passed_count} dari 4 visible test berhasil.",
        program_output=str(normalized_cases[0].get("actual_action") or ""),
        error_message=first_error,
        stdout="\n---\n".join(stdout_parts),
        stderr="\n---\n".join(stderr_parts),
        visible_results=visible_results,
        hidden_summary={"total": 0, "passed": 0},
        executions=executions,
        case_results=case_results,
        normalized_cases=normalized_cases,
        behavior_correct=behavior_correct,
        technique_result=TechniqueResult(None, True, {}),
        overall_correct=behavior_correct,
    )
