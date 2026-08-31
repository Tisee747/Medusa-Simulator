"""Strict function-return evaluator for H03_RESCUE_PATH_CHECK."""

from __future__ import annotations

from typing import Any

from app.code_runner import FunctionRunResult, run_function
from app.ids import new_execution_id
from app.questions.base import EvaluationResult, TechniqueResult

GRID_ROWS = 5
GRID_COLUMNS = 5
MAX_INPUT_STEPS = 20
MAX_PATH_COORDINATES = 21
OFFICIAL_STEPS = ("UP", "DOWN", "LEFT", "RIGHT")
OFFICIAL_STATUSES = (
    "BERHASIL",
    "MENABRAK_DINDING",
    "KELUAR_GRID",
    "BELUM_SAMPAI",
)
MOVEMENT = {
    "UP": (-1, 0),
    "DOWN": (1, 0),
    "LEFT": (0, -1),
    "RIGHT": (0, 1),
}


def _coord(value: list[int] | tuple[int, int]) -> tuple[int, int]:
    return int(value[0]), int(value[1])


def simulate_expected(
    start: list[int] | tuple[int, int],
    target: list[int] | tuple[int, int],
    walls: list[list[int] | tuple[int, int]],
    steps: list[str],
) -> dict[str, Any]:
    """Independently simulate the official input semantics."""

    current = _coord(start)
    target_coord = _coord(target)
    wall_set = {_coord(item) for item in walls}
    path: list[list[int]] = [[current[0], current[1]]]

    if current == target_coord:
        return {
            "status": "BERHASIL",
            "visited_path": path,
            "terminal_reason": "SUCCESS",
            "terminal_step_index": None,
            "attempted_destination": None,
        }

    for index, token in enumerate(steps):
        dr, dc = MOVEMENT[token]
        candidate = (current[0] + dr, current[1] + dc)
        if not (0 <= candidate[0] < GRID_ROWS and 0 <= candidate[1] < GRID_COLUMNS):
            return {
                "status": "KELUAR_GRID",
                "visited_path": path,
                "terminal_reason": "OUT_OF_GRID",
                "terminal_step_index": index,
                "attempted_destination": [candidate[0], candidate[1]],
            }
        if candidate in wall_set:
            return {
                "status": "MENABRAK_DINDING",
                "visited_path": path,
                "terminal_reason": "WALL",
                "terminal_step_index": index,
                "attempted_destination": [candidate[0], candidate[1]],
            }
        current = candidate
        path.append([current[0], current[1]])
        if current == target_coord:
            return {
                "status": "BERHASIL",
                "visited_path": path,
                "terminal_reason": "SUCCESS",
                "terminal_step_index": index,
                "attempted_destination": None,
            }

    return {
        "status": "BELUM_SAMPAI",
        "visited_path": path,
        "terminal_reason": "INCOMPLETE",
        "terminal_step_index": None,
        "attempted_destination": None,
    }


def _failure(failure_type: str | None = None, path_index: int | None = None, detail: str | None = None) -> dict[str, Any]:
    return {"type": failure_type, "path_index": path_index, "detail": detail}


def _raw_for_persistence(value: Any) -> Any:
    """Retain decoded raw return; database JSON safety is handled centrally."""

    return value


def normalize_rescue_result(
    returned: Any,
    *,
    case: dict[str, Any],
    execution_id: str,
) -> dict[str, Any]:
    """Normalize one function return and retain the first actionable failure."""

    expected = simulate_expected(case["start"], case["target"], case["walls"], case["steps"])
    start = _coord(case["start"])
    target = _coord(case["target"])
    wall_set = {_coord(item) for item in case["walls"]}
    visibility = case["test_visibility"]

    actual_status: str | None = None
    actual_items: list[dict[str, Any]] = []
    valid_coords: list[tuple[int, int]] = []
    safe_path: list[list[int]] = []
    failure = _failure()

    def set_failure(kind: str, path_index: int | None, detail: str) -> None:
        nonlocal failure
        if failure["type"] is None:
            failure = _failure(kind, path_index, detail)

    result_is_dict = isinstance(returned, dict) and "__simulator_unsupported__" not in returned
    if not result_is_dict:
        set_failure("INVALID_RETURN_TYPE", None, "Return harus berupa dictionary.")
        return _normalized_case(
            case, execution_id, returned, actual_status, actual_items, safe_path,
            failure, expected, False, animation_case_id=None,
        )

    missing = [key for key in ("status", "visited_path") if key not in returned]
    if missing:
        set_failure("MISSING_RESULT_KEY", None, f"Key wajib tidak tersedia: {missing[0]}.")

    status_value = returned.get("status")
    path_value = returned.get("visited_path")
    if failure["type"] is None and (not isinstance(status_value, str) or not isinstance(path_value, list)):
        invalid_field = "status" if not isinstance(status_value, str) else "visited_path"
        set_failure("INVALID_FIELD_TYPE", None, f"Tipe field {invalid_field} tidak sesuai kontrak.")

    if isinstance(status_value, str):
        actual_status = status_value
    if failure["type"] is None and actual_status not in OFFICIAL_STATUSES:
        set_failure("INVALID_STATUS", None, f"Status tidak dikenal: {actual_status!r}.")

    if isinstance(path_value, list):
        for index, raw_item in enumerate(path_value):
            row: int | None = None
            column: int | None = None
            coordinate_valid = False
            if isinstance(raw_item, (list, tuple)) and len(raw_item) == 2:
                raw_row, raw_column = raw_item
                if (
                    isinstance(raw_row, int) and not isinstance(raw_row, bool)
                    and isinstance(raw_column, int) and not isinstance(raw_column, bool)
                ):
                    row = raw_row
                    column = raw_column
                    coordinate_valid = True
                    valid_coords.append((row, column))
            actual_items.append({
                "index": index,
                "raw_value": raw_item,
                "row": row,
                "column": column,
                "coordinate_valid": coordinate_valid,
            })
            if failure["type"] is None and not coordinate_valid:
                set_failure("INVALID_PATH_ITEM", index, "Coordinate harus list/tuple dua integer dan bool ditolak.")

    # Structural/type failures stop semantic path checks, but raw item evidence remains.
    if failure["type"] is None:
        if not valid_coords or valid_coords[0] != start:
            set_failure("PATH_START_MISMATCH", 0 if valid_coords else None, "visited_path harus dimulai dari start.")
        else:
            safe_path = [[start[0], start[1]]]
            reached_actual_target = start == target
            for index in range(1, len(valid_coords)):
                previous = valid_coords[index - 1]
                current = valid_coords[index]

                if reached_actual_target:
                    set_failure("PATH_CONTINUES_AFTER_TERMINAL", index, "Path berlanjut setelah target tercapai.")
                    break

                if abs(current[0] - previous[0]) + abs(current[1] - previous[1]) != 1:
                    set_failure("NON_ADJACENT_PATH", index, "Transisi path harus berjarak Manhattan 1.")
                    break

                step_index = index - 1
                if step_index >= len(case["steps"]):
                    set_failure("PATH_DIRECTION_MISMATCH", index, "Tidak ada token input untuk transisi tambahan.")
                    break
                token = case["steps"][step_index]
                dr, dc = MOVEMENT[token]
                expected_coordinate = (previous[0] + dr, previous[1] + dc)
                if current != expected_coordinate:
                    set_failure("PATH_DIRECTION_MISMATCH", index, f"Transisi tidak sesuai token {token}.")
                    break

                if not (0 <= current[0] < GRID_ROWS and 0 <= current[1] < GRID_COLUMNS):
                    set_failure("PATH_OUT_OF_GRID", index, "Actual path memuat coordinate di luar grid.")
                    break
                if current in wall_set:
                    set_failure("PATH_ENTERS_WALL", index, "Actual path memasuki wall.")
                    break

                # The expected simulation terminates before illegal destinations and at target.
                expected_path_length = len(expected["visited_path"])
                if index >= expected_path_length:
                    set_failure("PATH_CONTINUES_AFTER_TERMINAL", index, "Path berlanjut setelah terminal input.")
                    break

                safe_path.append([current[0], current[1]])
                if current == target:
                    reached_actual_target = True

    if failure["type"] is None and actual_status != expected["status"]:
        set_failure("WRONG_STATUS", None, f"Expected {expected['status']}, actual {actual_status}.")

    actual_coordinate_path = [[row, column] for row, column in valid_coords]
    if failure["type"] is None and actual_coordinate_path != expected["visited_path"]:
        set_failure("WRONG_VISITED_PATH", None, "visited_path tidak sama dengan hasil simulasi input.")

    if failure["type"] is None and isinstance(path_value, list) and len(path_value) > MAX_PATH_COORDINATES:
        set_failure("PATH_TOO_LONG", MAX_PATH_COORDINATES, "visited_path melebihi 21 coordinate.")

    case_correct = failure["type"] is None
    animation_case_id = None if visibility == "HIDDEN" else str(case.get("animation_case_id") or case["test_id"])
    # Malformed returns with no safe movement must not become animation candidates.
    if len(safe_path) <= 1 and not case_correct:
        animation_case_id = None

    return _normalized_case(
        case, execution_id, returned, actual_status, actual_items, safe_path,
        failure, expected, case_correct, animation_case_id=animation_case_id,
    )


def _normalized_case(
    case: dict[str, Any],
    execution_id: str,
    returned: Any,
    actual_status: str | None,
    actual_items: list[dict[str, Any]],
    safe_path: list[list[int]],
    failure: dict[str, Any],
    expected: dict[str, Any],
    case_correct: bool,
    *,
    animation_case_id: str | None,
) -> dict[str, Any]:
    return {
        "execution_id": execution_id,
        "test_id": case["test_id"],
        "test_visibility": case["test_visibility"],
        "animation_case_id": animation_case_id,
        "maze_version": case.get("maze_version"),
        "start": {"row": case["start"][0], "column": case["start"][1]},
        "target": {"row": case["target"][0], "column": case["target"][1]},
        "walls": [list(item) for item in case["walls"]],
        "input_steps": list(case["steps"]),
        "returned_result_raw": _raw_for_persistence(returned),
        "actual": {
            "status": actual_status,
            "visited_path": actual_items,
        },
        "safe_executable_path": safe_path,
        "failure": failure,
        "expected_terminal_reason": expected["terminal_reason"],
        "expected_status": expected["status"],
        "case_behavior_correct": case_correct,
    }


def _execution_status(run: FunctionRunResult) -> str:
    if run.validation_error:
        return "SYNTAX_ERROR" if run.validation_error.startswith("SyntaxError") else "RUNTIME_ERROR"
    if run.timed_out:
        return "TIMEOUT"
    if run.output_limit_exceeded or run.return_limit_exceeded:
        return "RUNTIME_ERROR"
    return "COMPLETED" if run.ok else "RUNTIME_ERROR"


def _execution_error(run: FunctionRunResult) -> tuple[str | None, str | None]:
    status = _execution_status(run)
    if status == "COMPLETED":
        return None, None
    if run.validation_error:
        return status, run.validation_error
    if run.timed_out:
        return "TIMEOUT", "Function melewati batas waktu."
    if run.return_limit_exceeded:
        return "RETURN_TOO_LARGE", run.function_error or "Return object melebihi batas aman."
    if run.output_limit_exceeded:
        return "OUTPUT_TOO_LARGE", "Stdout/stderr melebihi batas aman."
    return "RUNTIME_ERROR", run.function_error or run.stderr.strip() or "Function berhenti dengan error."


def evaluate_rescue_path(source_code: str, attempt_data: dict[str, Any]) -> EvaluationResult:
    executions: list[dict[str, Any]] = []
    normalized_cases: list[dict[str, Any]] = []
    visible_results: list[dict[str, Any]] = []
    combined_stdout: list[str] = []
    combined_stderr: list[str] = []

    for case in attempt_data["cases"]:
        execution_id = new_execution_id()
        run = run_function(
            source_code,
            function_name="periksa_jalur",
            args=[case["start"], case["target"], case["walls"], case["steps"]],
        )
        normalized = normalize_rescue_result(run.return_value, case=case, execution_id=execution_id)
        if not run.ok:
            normalized["case_behavior_correct"] = False
            if normalized["failure"]["type"] is None:
                normalized["failure"] = _failure("INVALID_RETURN_TYPE", None, run.function_error or "Function gagal dijalankan.")
            if len(normalized.get("safe_executable_path") or []) <= 1:
                normalized["animation_case_id"] = None

        error_type, error_detail = _execution_error(run)
        execution = {
            "execution_id": execution_id,
            "test_id": case["test_id"],
            "test_visibility": case["test_visibility"],
            "status": _execution_status(run),
            "stdout_raw": run.stdout,
            "stderr_raw": run.stderr,
            "return_value_serialized": run.return_value,
            "case_behavior_correct": bool(normalized["case_behavior_correct"]),
            "duration_ms": run.duration_ms,
            "error_type": error_type,
            "error_detail": error_detail,
            "feedback": {
                "failure": normalized["failure"],
                "expected_status": normalized["expected_status"],
                "actual_status": normalized["actual"]["status"],
            },
            "normalized_result": normalized,
            "evaluation_result": {
                "expected_status": normalized["expected_status"],
                "expected_terminal_reason": normalized["expected_terminal_reason"],
                "passed": bool(normalized["case_behavior_correct"]),
            },
        }
        executions.append(execution)
        normalized_cases.append(normalized)
        combined_stdout.append(run.stdout)
        combined_stderr.append(run.stderr)

        if case["test_visibility"] != "HIDDEN":
            visible_results.append({
                "test_id": case["test_id"],
                "name": case["name"],
                "input": {
                    "start": case["start"],
                    "target": case["target"],
                    "walls": case["walls"],
                    "langkah": case["steps"],
                },
                "expected": {
                    "status": normalized["expected_status"],
                    "visited_path": simulate_expected(case["start"], case["target"], case["walls"], case["steps"])["visited_path"],
                },
                "actual": {
                    "status": normalized["actual"]["status"],
                    "visited_path": [
                        [item["row"], item["column"]]
                        for item in normalized["actual"]["visited_path"]
                        if item["coordinate_valid"]
                    ],
                },
                "passed": bool(normalized["case_behavior_correct"]),
                "error": error_detail or normalized["failure"]["detail"] or "",
                "visible": True,
                "execution_id": execution_id,
            })

    behavior_correct = all(bool(item["case_behavior_correct"]) for item in executions)
    passed_count = sum(bool(item["case_behavior_correct"]) for item in executions)
    score = round(100.0 * passed_count / max(1, len(executions)), 1)
    first_failure = next(
        (
            item["normalized_result"]["failure"]
            for item in executions
            if not item["case_behavior_correct"]
        ),
        _failure(),
    )
    hidden = [item for item in executions if item["test_visibility"] == "HIDDEN"]
    canonical = next((item for item in normalized_cases if item["test_id"] == "VISIBLE-1"), None)

    return EvaluationResult(
        status="CORRECT" if behavior_correct else "WRONG",
        score=score,
        message="Seluruh test jalur berhasil." if behavior_correct else f"{passed_count} dari {len(executions)} test berhasil.",
        program_output="" if canonical is None else str(canonical["actual"]),
        error_message="" if behavior_correct else str(first_failure.get("detail") or first_failure.get("type") or "Jalur belum benar."),
        stdout="\n---\n".join(combined_stdout),
        stderr="\n---\n".join(combined_stderr),
        visible_results=visible_results,
        hidden_summary={
            "total": len(hidden),
            "passed": sum(bool(item["case_behavior_correct"]) for item in hidden),
        },
        executions=executions,
        case_results=[
            {
                "test_id": item["test_id"],
                "execution_id": item["execution_id"],
                "test_visibility": item["test_visibility"],
                "case_behavior_correct": bool(item["case_behavior_correct"]),
            }
            for item in executions
        ],
        normalized_cases=normalized_cases,
        behavior_correct=behavior_correct,
        technique_result=TechniqueResult(required_technique=None, passed=True, checks={}),
        overall_correct=behavior_correct,
    )
