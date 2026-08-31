"""Function-return evaluation for M04_PACKAGE_DATA_ANALYSIS."""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.code_runner import FunctionRunResult, run_function
from app.ids import new_execution_id
from app.questions.base import EvaluationResult, TechniqueResult

_REQUIRED_KEYS = ("total_berat", "terberat", "jumlah_target", "kategori", "ditemukan", "lolos")
_ACTORS = {f"PACKAGE_{index}" for index in range(1, 6)}


def build_expected(
    data: list[tuple[str, str, int]],
    kategori_target: str,
    batas_berat: int,
    package_dicari: str,
) -> dict[str, Any]:
    max_weight = max(item[2] for item in data)
    return {
        "total_berat": sum(item[2] for item in data),
        "terberat": next(item[0] for item in data if item[2] == max_weight),
        "jumlah_target": sum(1 for item in data if item[1] == kategori_target),
        "kategori": sorted({item[1] for item in data}),
        "ditemukan": package_dicari if any(item[0] == package_dicari for item in data) else "TIDAK_ADA",
        "lolos": [item[0] for item in data if item[2] <= batas_berat],
    }


def normalize_package_result(
    returned: Any,
    *,
    case: dict[str, Any],
    execution_id: str,
) -> dict[str, Any]:
    expected = case["expected"]
    visible = case["test_visibility"] == "VISIBLE"
    result_is_dict = isinstance(returned, dict) and "__simulator_unsupported__" not in returned
    evaluation_errors: list[dict[str, Any]] = []
    field_results: dict[str, Any] = {}
    actual: dict[str, Any] = {
        "total_berat": None,
        "terberat": None,
        "jumlah_target": None,
        "kategori": None,
        "ditemukan": None,
        "lolos_package_ids": None,
    }
    animation_failure = {"type": None, "field": None, "index": None, "detail": None}

    if not result_is_dict:
        animation_failure = {
            "type": "INVALID_RETURN_TYPE", "field": None, "index": None,
            "detail": f"Return harus dictionary, actual {type(returned).__name__}.",
        }
        evaluation_errors.append({
            "type": "INVALID_FIELD_TYPE", "field": "return", "detail": "Return harus dictionary.",
        })
        for key in _REQUIRED_KEYS:
            field_results[key] = {"present": False, "type_valid": False, "value_correct": False}
        return _normalized_package_case(
            case, execution_id, returned, actual, field_results, {"highlight_terberat": None, "lolos_package_ids": []},
            animation_failure, evaluation_errors, False, None,
        )

    missing = [key for key in _REQUIRED_KEYS if key not in returned]
    for key in missing:
        evaluation_errors.append({"type": "MISSING_RESULT_KEY", "field": key, "detail": key})
    if missing:
        animation_failure = {
            "type": "MALFORMED_RESULT", "field": missing[0], "index": None,
            "detail": "Dictionary kehilangan key wajib.",
        }

    validators = {
        "total_berat": lambda value: isinstance(value, int) and not isinstance(value, bool),
        "terberat": lambda value: isinstance(value, str),
        "jumlah_target": lambda value: isinstance(value, int) and not isinstance(value, bool),
        "kategori": lambda value: isinstance(value, list) and all(isinstance(item, str) for item in value),
        "ditemukan": lambda value: isinstance(value, str),
        "lolos": lambda value: isinstance(value, list) and all(isinstance(item, str) for item in value),
    }
    actual_names = {
        "total_berat": "total_berat", "terberat": "terberat", "jumlah_target": "jumlah_target",
        "kategori": "kategori", "ditemukan": "ditemukan", "lolos": "lolos_package_ids",
    }
    for key in _REQUIRED_KEYS:
        present = key in returned
        type_valid = present and validators[key](returned[key])
        if type_valid:
            actual[actual_names[key]] = returned[key]
        value_correct = type_valid and returned[key] == expected[key]
        field_results[key] = {
            "present": present,
            "type_valid": bool(type_valid),
            "value_correct": bool(value_correct),
        }
        if present and not type_valid:
            evaluation_errors.append({
                "type": "INVALID_FIELD_TYPE", "field": key,
                "detail": f"Tipe field {key} tidak sesuai kontrak.",
            })

    error_map = {
        "total_berat": "WRONG_TOTAL_WEIGHT",
        "terberat": "WRONG_HEAVIEST",
        "jumlah_target": "WRONG_TARGET_COUNT",
        "kategori": "WRONG_UNIQUE_CATEGORIES",
        "ditemukan": "WRONG_SEARCH_RESULT",
    }
    for key, error_type in error_map.items():
        if field_results[key]["type_valid"] and not field_results[key]["value_correct"]:
            evaluation_errors.append({"type": error_type, "field": key, "detail": None})

    if field_results["lolos"]["type_valid"] and not field_results["lolos"]["value_correct"]:
        actual_lolos = list(actual["lolos_package_ids"] or [])
        expected_lolos = list(expected["lolos"])
        evaluation_errors.append({
            "type": "WRONG_FILTER_RESULT", "field": "lolos",
            "detail": f"Expected {len(expected_lolos)} package, actual {len(actual_lolos)} package.",
        })
        expected_counter = Counter(expected_lolos)
        actual_counter = Counter(actual_lolos)
        for package_id in expected_lolos:
            if actual_counter[package_id] < expected_counter[package_id]:
                evaluation_errors.append({"type": "MISSING_PACKAGE", "field": "lolos", "detail": package_id})
        for package_id in actual_lolos:
            if actual_counter[package_id] > expected_counter[package_id]:
                evaluation_errors.append({"type": "EXTRA_PACKAGE", "field": "lolos", "detail": package_id})
        if actual_counter == expected_counter and actual_lolos != expected_lolos:
            evaluation_errors.append({"type": "WRONG_PACKAGE_ORDER", "field": "lolos", "detail": None})

    case_package_ids = {record[0] for record in case["data"]}
    highlight: str | None = None
    if field_results["terberat"]["type_valid"]:
        candidate = actual["terberat"]
        if candidate not in _ACTORS:
            if animation_failure["type"] is None:
                animation_failure = {"type": "INVALID_PACKAGE", "field": "terberat", "index": None, "detail": candidate}
        elif candidate not in case_package_ids:
            if animation_failure["type"] is None:
                animation_failure = {"type": "PACKAGE_NOT_IN_CASE", "field": "terberat", "index": None, "detail": candidate}
        else:
            highlight = candidate

    prefix: list[str] = []
    seen: set[str] = set()
    if field_results["lolos"]["type_valid"]:
        for index, package_id in enumerate(actual["lolos_package_ids"] or []):
            failure_type: str | None = None
            if package_id not in _ACTORS:
                failure_type = "INVALID_PACKAGE"
            elif package_id not in case_package_ids:
                failure_type = "PACKAGE_NOT_IN_CASE"
            elif package_id in seen:
                failure_type = "DUPLICATE_PACKAGE"
            if failure_type:
                if animation_failure["type"] is None:
                    animation_failure = {
                        "type": failure_type, "field": "lolos", "index": index, "detail": package_id,
                    }
                break
            seen.add(package_id)
            prefix.append(package_id)

    executable = {"highlight_terberat": highlight, "lolos_package_ids": prefix}
    correct = (
        result_is_dict
        and not missing
        and all(item["type_valid"] and item["value_correct"] for item in field_results.values())
        and not evaluation_errors
    )
    animation_case_id = case["test_id"] if visible and not missing else None
    return _normalized_package_case(
        case, execution_id, returned, actual, field_results, executable,
        animation_failure, evaluation_errors, correct, animation_case_id,
    )


def _normalized_package_case(
    case: dict[str, Any], execution_id: str, returned: Any, actual: dict[str, Any],
    field_results: dict[str, Any], executable: dict[str, Any], animation_failure: dict[str, Any],
    evaluation_errors: list[dict[str, Any]], correct: bool, animation_case_id: str | None,
) -> dict[str, Any]:
    return {
        "execution_id": execution_id,
        "test_id": case["test_id"],
        "test_visibility": case["test_visibility"],
        "animation_case_id": animation_case_id,
        "returned_result_raw": returned,
        "actual": actual,
        "field_results": field_results,
        "executable": executable,
        "animation_failure": animation_failure,
        "evaluation_errors": evaluation_errors,
        "case_behavior_correct": bool(correct),
        "input_data": {
            "data": [list(record) for record in case["data"]],
            "kategori_target": case["kategori_target"],
            "batas_berat": case["batas_berat"],
            "package_dicari": case["package_dicari"],
        },
    }


def evaluate_package_data(source_code: str, data: dict[str, Any]) -> EvaluationResult:
    executions: list[dict[str, Any]] = []
    normalized_cases: list[dict[str, Any]] = []
    case_results: list[dict[str, Any]] = []
    visible_results: list[dict[str, Any]] = []
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []

    for case in data["cases"]:
        execution_id = new_execution_id()
        args = [
            [tuple(record) for record in case["data"]],
            case["kategori_target"], case["batas_berat"], case["package_dicari"],
        ]
        run = run_function(source_code, function_name="analisis_paket", args=args)
        normalized = normalize_package_result(run.return_value, case=case, execution_id=execution_id)
        if not run.ok:
            normalized["case_behavior_correct"] = False
        normalized_cases.append(normalized)

        status, error_type, error_detail = _function_status(run)
        passed = bool(normalized["case_behavior_correct"])
        case_results.append({
            "test_id": case["test_id"], "execution_id": execution_id,
            "test_visibility": case["test_visibility"], "case_behavior_correct": passed,
        })
        feedback = {
            "test_id": case["test_id"], "name": case["name"],
            "input": str(args), "expected": case["expected"], "actual": normalized["actual"],
            "passed": passed, "error": error_detail or normalized["evaluation_errors"],
            "visible": case["test_visibility"] == "VISIBLE", "execution_id": execution_id,
        }
        if case["test_visibility"] == "VISIBLE":
            visible_results.append(feedback)
        executions.append({
            "execution_id": execution_id,
            "test_id": case["test_id"],
            "test_visibility": case["test_visibility"],
            "status": status,
            "stdout_raw": run.stdout,
            "stderr_raw": run.stderr,
            "return_value_serialized": run.return_value,
            "case_behavior_correct": passed,
            "duration_ms": run.duration_ms,
            "error_type": error_type,
            "error_detail": error_detail,
            "feedback": feedback,
            "normalized_result": normalized,
            "evaluation_result": {
                "field_results": normalized["field_results"],
                "evaluation_errors": normalized["evaluation_errors"],
            },
        })
        stdout_parts.append(run.stdout)
        stderr_parts.append(run.stderr)

    passed_count = sum(1 for item in case_results if item["case_behavior_correct"])
    behavior_correct = passed_count == len(case_results)
    hidden = [item for item in case_results if item["test_visibility"] == "HIDDEN"]
    first_runtime_error = next((item["error_detail"] for item in executions if item["status"] != "COMPLETED"), "")
    canonical = normalized_cases[0].get("actual", {}) if normalized_cases else {}
    return EvaluationResult(
        status="CORRECT" if behavior_correct else ("ERROR" if first_runtime_error else "WRONG"),
        score=round(100.0 * passed_count / max(1, len(case_results)), 1),
        message="Seluruh visible dan hidden function test berhasil." if behavior_correct else f"{passed_count} dari {len(case_results)} function test berhasil.",
        program_output=_canonical_editor_output(canonical),
        error_message=first_runtime_error,
        stdout="\n---\n".join(stdout_parts),
        stderr="\n---\n".join(stderr_parts),
        visible_results=visible_results,
        hidden_summary={"total": len(hidden), "passed": sum(1 for item in hidden if item["case_behavior_correct"])},
        executions=executions,
        case_results=case_results,
        normalized_cases=normalized_cases,
        behavior_correct=behavior_correct,
        technique_result=TechniqueResult(None, True, {}),
        overall_correct=behavior_correct,
    )


def _function_status(run: FunctionRunResult) -> tuple[str, str | None, str | None]:
    if run.validation_error:
        kind = "SYNTAX_ERROR" if run.validation_error.startswith("SyntaxError") else "RUNTIME_ERROR"
        return kind, kind, run.validation_error
    if run.timed_out:
        return "TIMEOUT", "TIMEOUT", "Function call melewati batas waktu."
    if run.output_limit_exceeded:
        return "RUNTIME_ERROR", "OUTPUT_TOO_LONG", "Stdout atau stderr melewati batas."
    if run.return_limit_exceeded:
        return "RUNTIME_ERROR", "RETURN_TOO_LARGE", run.function_error
    if not run.ok:
        return "RUNTIME_ERROR", "RUNTIME_ERROR", run.function_error or run.stderr.strip() or "Runtime error."
    return "COMPLETED", None, None


def _canonical_editor_output(actual: dict[str, Any]) -> str:
    if not actual:
        return ""
    kategori = " ".join(actual.get("kategori") or [])
    lolos = " ".join(actual.get("lolos_package_ids") or [])
    return "\n".join([
        f"TOTAL_BERAT {actual.get('total_berat')}",
        f"TERBERAT {actual.get('terberat')}",
        f"JUMLAH_TARGET {actual.get('jumlah_target')}",
        f"KATEGORI {kategori}".rstrip(),
        f"DITEMUKAN {actual.get('ditemukan')}",
        f"LOLOS {lolos}".rstrip(),
    ])
