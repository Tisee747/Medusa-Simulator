"""Evaluators for Rescue Soal 2 (BFS) and Rescue Soal 3 (best candidate route)."""

from __future__ import annotations

from collections import deque
from copy import deepcopy
from typing import Any

from app.code_runner import FunctionRunResult, run_function
from app.evaluators.technique import evaluate_technique
from app.ids import new_execution_id
from app.questions.base import EvaluationResult, TechniqueResult

GRID_SIZE = 5
DIRECTIONS: dict[str, tuple[int, int]] = {
    "UP": (-1, 0),
    "DOWN": (1, 0),
    "LEFT": (0, -1),
    "RIGHT": (0, 1),
}
_DIRECTION_ORDER = ("UP", "DOWN", "LEFT", "RIGHT")


def _coord(value: Any) -> list[int]:
    return [int(value[0]), int(value[1])]


def _in_grid(value: list[int]) -> bool:
    return 0 <= value[0] < GRID_SIZE and 0 <= value[1] < GRID_SIZE


def shortest_path(start: list[int], target: list[int], walls: list[list[int]]) -> list[str] | None:
    """Reference BFS used only to determine reachability and minimum length."""

    origin = tuple(start)
    goal = tuple(target)
    blocked = {tuple(item) for item in walls}
    if origin == goal:
        return []
    queue: deque[tuple[tuple[int, int], list[str]]] = deque([(origin, [])])
    visited = {origin}
    while queue:
        current, path = queue.popleft()
        for token in _DIRECTION_ORDER:
            dr, dc = DIRECTIONS[token]
            nxt = (current[0] + dr, current[1] + dc)
            if not (0 <= nxt[0] < GRID_SIZE and 0 <= nxt[1] < GRID_SIZE):
                continue
            if nxt in blocked or nxt in visited:
                continue
            next_path = path + [token]
            if nxt == goal:
                return next_path
            visited.add(nxt)
            queue.append((nxt, next_path))
    return None


def simulate_route(
    tokens: list[str],
    *,
    start: list[int],
    target: list[int],
    walls: list[list[int]],
) -> dict[str, Any]:
    """Simulate normalized direction tokens and stop at the first terminal event."""

    current = list(start)
    goal = list(target)
    blocked = {tuple(item) for item in walls}
    visited_path = [list(current)]
    attempted_destination: list[int] | None = None
    failure_type: str | None = None
    failure_index: int | None = None
    reached_target = current == goal

    if reached_target and tokens:
        return {
            "status": "BERHASIL",
            "visited_path": visited_path,
            "safe_executable_path": visited_path,
            "reached_target": True,
            "failure_type": "EXTRA_MOVES_AFTER_TARGET",
            "failure_index": 0,
            "attempted_destination": None,
            "executed_count": 0,
        }

    for index, token in enumerate(tokens):
        if reached_target:
            failure_type = "EXTRA_MOVES_AFTER_TARGET"
            failure_index = index
            break
        delta = DIRECTIONS[token]
        candidate = [current[0] + delta[0], current[1] + delta[1]]
        attempted_destination = candidate
        if not _in_grid(candidate):
            failure_type = "PATH_OUT_OF_GRID"
            failure_index = index
            break
        if tuple(candidate) in blocked:
            failure_type = "PATH_ENTERS_WALL"
            failure_index = index
            break
        current = candidate
        visited_path.append(list(current))
        attempted_destination = None
        if current == goal:
            reached_target = True

    if failure_type == "PATH_OUT_OF_GRID":
        status = "KELUAR_GRID"
    elif failure_type == "PATH_ENTERS_WALL":
        status = "MENABRAK_DINDING"
    elif reached_target:
        status = "BERHASIL"
    else:
        status = "BELUM_SAMPAI"
    return {
        "status": status,
        "visited_path": visited_path,
        "safe_executable_path": visited_path,
        "reached_target": reached_target,
        "failure_type": failure_type,
        "failure_index": failure_index,
        "attempted_destination": attempted_destination,
        "executed_count": len(visited_path) - 1,
    }


def _normalize_token_list(raw: Any) -> tuple[list[dict[str, Any]], list[str], dict[str, Any] | None]:
    items: list[dict[str, Any]] = []
    tokens: list[str] = []
    if not isinstance(raw, list):
        return items, tokens, {"type": "INVALID_RETURN_TYPE", "index": None, "detail": "Return harus berupa list arah."}
    for index, value in enumerate(raw):
        normalized: str | None = None
        valid = False
        if isinstance(value, str):
            candidate = value.strip().upper()
            if candidate in DIRECTIONS:
                normalized = candidate
                valid = True
        items.append({
            "index": index,
            "raw_value": value,
            "normalized_token": normalized,
            "item_valid": valid,
        })
        if not valid:
            return items, tokens, {
                "type": "INVALID_DIRECTION_TOKEN",
                "index": index,
                "detail": f"Token arah pada indeks {index} tidak valid.",
            }
        tokens.append(normalized)
    return items, tokens, None


def normalize_bfs_case(
    returned: Any,
    *,
    start: list[int],
    target: list[int],
    walls: list[list[int]],
    execution_id: str,
    test_id: str,
    test_visibility: str,
) -> dict[str, Any]:
    reference = shortest_path(start, target, walls)
    reachable = reference is not None
    minimum_steps = None if reference is None else len(reference)
    failure: dict[str, Any] = {"type": None, "index": None, "detail": None}
    items: list[dict[str, Any]] = []
    tokens: list[str] = []
    simulation = {
        "status": "BELUM_SAMPAI",
        "visited_path": [list(start)],
        "safe_executable_path": [list(start)],
        "reached_target": list(start) == list(target),
        "failure_type": None,
        "failure_index": None,
        "attempted_destination": None,
        "executed_count": 0,
    }

    if returned is None:
        if reachable:
            failure = {"type": "NO_PATH", "index": None, "detail": "Target dapat dicapai, tetapi fungsi mengembalikan None."}
    else:
        items, tokens, token_failure = _normalize_token_list(returned)
        if token_failure:
            failure = token_failure
        else:
            simulation = simulate_route(tokens, start=start, target=target, walls=walls)
            if simulation["failure_type"]:
                failure = {
                    "type": simulation["failure_type"],
                    "index": simulation["failure_index"],
                    "detail": "Jalur berhenti pada langkah ilegal pertama.",
                }
            elif not reachable:
                failure = {
                    "type": "UNREACHABLE_MUST_RETURN_NONE",
                    "index": None,
                    "detail": "Target tidak dapat dicapai. Return yang benar adalah None.",
                }
            elif not simulation["reached_target"]:
                failure = {"type": "INCOMPLETE_PATH", "index": None, "detail": "Jalur belum mencapai target."}
            elif len(tokens) != minimum_steps:
                failure = {
                    "type": "PATH_NOT_SHORTEST",
                    "index": None,
                    "detail": f"Jalur mencapai target dalam {len(tokens)} langkah; minimum {minimum_steps}.",
                }

    correct = (returned is None and not reachable) or (
        isinstance(returned, list)
        and failure["type"] is None
        and reachable
        and simulation["reached_target"]
        and len(tokens) == minimum_steps
    )
    animation_goal_allowed = bool(
        isinstance(returned, list)
        and simulation["reached_target"]
        and simulation["failure_type"] is None
        and len(tokens) == simulation["executed_count"]
    )
    wall_attempt = simulation.get("attempted_destination") if simulation.get("failure_type") == "PATH_ENTERS_WALL" else None
    return {
        "execution_id": execution_id,
        "test_id": test_id,
        "test_visibility": test_visibility,
        "animation_case_id": test_id if test_visibility in {"CANONICAL", "VISIBLE"} else None,
        "start": {"row": start[0], "column": start[1]},
        "target": {"row": target[0], "column": target[1]},
        "walls": [list(item) for item in walls],
        "returned_path_raw": returned,
        "returned_items": items,
        "actual": {
            "tokens": tokens if isinstance(returned, list) else None,
            "status": simulation["status"] if isinstance(returned, list) else None,
            "visited_path": simulation["visited_path"] if isinstance(returned, list) else [],
        },
        "input_steps": tokens,
        "safe_executable_path": simulation["safe_executable_path"] if isinstance(returned, list) else [list(start)],
        "simulation_result": simulation,
        "reachable": reachable,
        "minimum_step_count": minimum_steps,
        "expected_unreachable_return": None,
        "failure": failure,
        "animation_goal_allowed": animation_goal_allowed,
        "animation_wall_attempt": wall_attempt,
        "case_behavior_correct": bool(correct),
    }


def _run_error(run: FunctionRunResult) -> tuple[str | None, str | None]:
    if run.validation_error:
        kind = "SYNTAX_ERROR" if run.validation_error.startswith("SyntaxError") else "RUNTIME_ERROR"
        return kind, run.validation_error
    if run.timed_out:
        return "TIMEOUT", "Fungsi melewati batas waktu."
    if run.return_limit_exceeded:
        return "RETURN_TOO_LARGE", run.function_error
    if not run.ok:
        return "RUNTIME_ERROR", run.function_error or run.stderr.strip() or "Runtime error."
    return None, None


def evaluate_rescue_bfs(source_code: str, data: dict[str, Any]) -> EvaluationResult:
    executions: list[dict[str, Any]] = []
    normalized_cases: list[dict[str, Any]] = []
    visible_results: list[dict[str, Any]] = []
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []

    for case in data["cases"]:
        execution_id = new_execution_id()
        args = [deepcopy(case["start"]), deepcopy(case["target"]), deepcopy(case["walls"])]
        run = run_function(source_code, function_name="cari_jalur", args=args, timeout_seconds=3)
        error_type, error_detail = _run_error(run)
        normalized = normalize_bfs_case(
            run.return_value if error_type is None else None,
            start=case["start"], target=case["target"], walls=case["walls"],
            execution_id=execution_id, test_id=case["test_id"], test_visibility=case["test_visibility"],
        )
        if error_type:
            normalized["failure"] = {"type": error_type, "index": None, "detail": error_detail}
            normalized["case_behavior_correct"] = False
        normalized_cases.append(normalized)
        execution = {
            "execution_id": execution_id,
            "test_id": case["test_id"],
            "test_visibility": case["test_visibility"],
            "status": error_type or "COMPLETED",
            "stdout_raw": run.stdout,
            "stderr_raw": run.stderr,
            "return_value_serialized": run.return_value,
            "case_behavior_correct": bool(normalized["case_behavior_correct"]),
            "duration_ms": run.duration_ms,
            "error_type": error_type or normalized["failure"]["type"],
            "error_detail": error_detail or normalized["failure"]["detail"],
            "feedback": {"failure": normalized["failure"]},
            "normalized_result": normalized,
            "evaluation_result": {
                "minimum_step_count": normalized["minimum_step_count"],
                "reachable": normalized["reachable"],
                "passed": normalized["case_behavior_correct"],
            },
        }
        executions.append(execution)
        stdout_parts.append(run.stdout)
        stderr_parts.append(run.stderr)
        if case["test_visibility"] in {"CANONICAL", "VISIBLE"}:
            visible_results.append({
                "test_id": case["test_id"],
                "name": case["name"],
                "input": {"start": case["start"], "target": case["target"], "walls": case["walls"]},
                "expected": "None" if normalized["minimum_step_count"] is None else f"Jalur minimum {normalized['minimum_step_count']} langkah",
                "actual": run.return_value,
                "passed": bool(normalized["case_behavior_correct"]),
                "error": error_detail or normalized["failure"]["detail"] or "",
                "visible": True,
                "execution_id": execution_id,
            })

    behavior_correct = all(item["case_behavior_correct"] for item in executions)
    technique = evaluate_technique(source_code, "BFS", "cari_jalur")
    overall = behavior_correct and technique.passed
    passed_count = sum(item["case_behavior_correct"] for item in executions)
    hidden = [item for item in executions if item["test_visibility"] == "HIDDEN"]
    first_failure = next((item["normalized_result"]["failure"] for item in executions if not item["case_behavior_correct"]), {"type": None, "detail": None})
    canonical = next((item for item in normalized_cases if item["test_id"] == "VISIBLE-1"), None)
    return EvaluationResult(
        status="CORRECT" if overall else "WRONG",
        score=round(100.0 * passed_count / max(1, len(executions)), 1),
        message="Seluruh jalur terpendek dan teknik BFS berhasil." if overall else f"{passed_count} dari {len(executions)} test behavior berhasil.",
        program_output=str(canonical["returned_path_raw"] if canonical else ""),
        error_message="" if overall else str(first_failure.get("detail") or ("Teknik BFS belum memenuhi kontrak." if behavior_correct else first_failure.get("type") or "Jalur belum benar.")),
        stdout="\n---\n".join(stdout_parts),
        stderr="\n---\n".join(stderr_parts),
        visible_results=visible_results,
        hidden_summary={"total": len(hidden), "passed": sum(item["case_behavior_correct"] for item in hidden)},
        executions=executions,
        case_results=[{
            "test_id": item["test_id"], "execution_id": item["execution_id"],
            "test_visibility": item["test_visibility"], "case_behavior_correct": bool(item["case_behavior_correct"]),
        } for item in executions],
        normalized_cases=normalized_cases,
        behavior_correct=behavior_correct,
        technique_result=technique,
        overall_correct=overall,
    )


def analyze_candidate(candidate: Any, *, start: list[int], target: list[int], walls: list[list[int]]) -> dict[str, Any]:
    items, tokens, token_failure = _normalize_token_list(candidate)
    if token_failure:
        return {
            "candidate_valid": False, "items": items, "tokens": tokens,
            "simulation": {"status": None, "visited_path": [list(start)], "safe_executable_path": [list(start)], "reached_target": False, "failure_type": token_failure["type"], "failure_index": token_failure["index"], "attempted_destination": None, "executed_count": 0},
            "failure": token_failure,
        }
    simulation = simulate_route(tokens, start=start, target=target, walls=walls)
    failure = {"type": simulation["failure_type"], "index": simulation["failure_index"], "detail": None}
    if failure["type"] is None and not simulation["reached_target"]:
        failure = {"type": "INCOMPLETE_PATH", "index": None, "detail": "Kandidat tidak mencapai target."}
    valid = isinstance(candidate, list) and failure["type"] is None and simulation["reached_target"] and len(tokens) == simulation["executed_count"]
    return {"candidate_valid": valid, "items": items, "tokens": tokens, "simulation": simulation, "failure": failure}


def expected_best_candidate(start: list[int], target: list[int], walls: list[list[int]], candidates: list[Any]) -> dict[str, Any]:
    best_index: int | None = None
    best_path: list[str] = []
    for index, candidate in enumerate(candidates):
        result = analyze_candidate(candidate, start=start, target=target, walls=walls)
        if not result["candidate_valid"]:
            continue
        path = list(result["tokens"])
        if best_index is None or len(path) < len(best_path):
            best_index = index
            best_path = path
    return {
        "selected_index": best_index,
        "selected_path": best_path if best_index is not None else [],
        "step_count": len(best_path) if best_index is not None else None,
    }


def normalize_best_route_case(
    returned: Any,
    *,
    arguments_after: Any,
    original_args: list[Any],
    user_stdout: str,
    start: list[int],
    target: list[int],
    walls: list[list[int]],
    candidates: list[Any],
    execution_id: str,
    test_id: str,
    test_visibility: str,
) -> dict[str, Any]:
    expected = expected_best_candidate(start, target, walls, candidates)
    failure = {"type": None, "field": None, "detail": None}
    required_keys = {"selected_index", "selected_path", "step_count"}
    actual_index: int | None = None
    actual_path: list[Any] | None = None
    actual_step_count: int | None = None

    if not isinstance(returned, dict):
        failure = {"type": "INVALID_RETURN_TYPE", "field": None, "detail": "Return harus dictionary."}
    else:
        keys = set(returned)
        if keys != required_keys:
            missing = sorted(required_keys - keys)
            extra = sorted(keys - required_keys)
            failure = {"type": "INVALID_RESULT_KEYS", "field": None, "detail": f"Missing={missing}; extra={extra}."}
        else:
            index_value = returned["selected_index"]
            path_value = returned["selected_path"]
            count_value = returned["step_count"]
            if index_value is not None and (not isinstance(index_value, int) or isinstance(index_value, bool)):
                failure = {"type": "INVALID_FIELD_TYPE", "field": "selected_index", "detail": "selected_index harus integer atau null."}
            elif not isinstance(path_value, list):
                failure = {"type": "INVALID_FIELD_TYPE", "field": "selected_path", "detail": "selected_path harus list."}
            elif count_value is not None and (not isinstance(count_value, int) or isinstance(count_value, bool)):
                failure = {"type": "INVALID_FIELD_TYPE", "field": "step_count", "detail": "step_count harus integer atau null."}
            else:
                actual_index = index_value
                actual_path = path_value
                actual_step_count = count_value

    mutation_detected = False
    if arguments_after is not None:
        mutation_detected = arguments_after != original_args
    if failure["type"] is None and mutation_detected:
        failure = {"type": "INPUT_MUTATED", "field": "candidates", "detail": "Fungsi mengubah input candidates."}
    if failure["type"] is None and user_stdout.strip():
        failure = {"type": "EXTRA_OUTPUT", "field": None, "detail": "Fungsi tidak boleh mencetak output tambahan."}

    animation_analysis = analyze_candidate(actual_path, start=start, target=target, walls=walls) if isinstance(actual_path, list) else {
        "candidate_valid": False, "tokens": [],
        "simulation": {"status": None, "visited_path": [list(start)], "safe_executable_path": [list(start)], "reached_target": False, "failure_type": None, "failure_index": None, "attempted_destination": None, "executed_count": 0},
        "failure": {"type": None, "index": None, "detail": None},
    }

    if failure["type"] is None:
        if actual_index != expected["selected_index"]:
            failure = {"type": "WRONG_SELECTED_INDEX", "field": "selected_index", "detail": "Index kandidat terpilih belum benar."}
        elif actual_path != expected["selected_path"]:
            failure = {"type": "WRONG_SELECTED_PATH", "field": "selected_path", "detail": "selected_path harus sama persis dengan kandidat terbaik."}
        elif actual_step_count != expected["step_count"]:
            failure = {"type": "WRONG_STEP_COUNT", "field": "step_count", "detail": "step_count belum sesuai panjang selected_path."}

    simulation = animation_analysis["simulation"]
    correct = failure["type"] is None
    wall_attempt = simulation.get("attempted_destination") if simulation.get("failure_type") == "PATH_ENTERS_WALL" else None
    return {
        "execution_id": execution_id,
        "test_id": test_id,
        "test_visibility": test_visibility,
        "animation_case_id": test_id if test_visibility in {"CANONICAL", "VISIBLE"} else None,
        "start": {"row": start[0], "column": start[1]},
        "target": {"row": target[0], "column": target[1]},
        "walls": [list(item) for item in walls],
        "candidates": deepcopy(candidates),
        "returned_result_raw": returned,
        "actual": {
            "selected_index": actual_index,
            "selected_path": actual_path,
            "step_count": actual_step_count,
            "status": simulation.get("status"),
            "visited_path": simulation.get("visited_path", []),
        },
        "expected": expected,
        "input_steps": animation_analysis.get("tokens", []),
        "safe_executable_path": simulation.get("safe_executable_path", [list(start)]),
        "simulation_result": simulation,
        "mutation_detected": mutation_detected,
        "failure": failure,
        "animation_goal_allowed": bool(animation_analysis.get("candidate_valid")),
        "animation_wall_attempt": wall_attempt,
        "case_behavior_correct": bool(correct),
    }


def evaluate_rescue_best_route(source_code: str, data: dict[str, Any]) -> EvaluationResult:
    executions: list[dict[str, Any]] = []
    normalized_cases: list[dict[str, Any]] = []
    visible_results: list[dict[str, Any]] = []
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []

    for case in data["cases"]:
        execution_id = new_execution_id()
        original_args = [deepcopy(case["start"]), deepcopy(case["target"]), deepcopy(case["walls"]), deepcopy(case["candidates"])]
        run = run_function(source_code, function_name="pilih_jalur_terbaik", args=deepcopy(original_args), timeout_seconds=3)
        error_type, error_detail = _run_error(run)
        normalized = normalize_best_route_case(
            run.return_value if error_type is None else None,
            arguments_after=run.arguments_after,
            original_args=original_args,
            user_stdout=run.stdout,
            start=case["start"], target=case["target"], walls=case["walls"], candidates=case["candidates"],
            execution_id=execution_id, test_id=case["test_id"], test_visibility=case["test_visibility"],
        )
        if error_type:
            normalized["failure"] = {"type": error_type, "field": None, "detail": error_detail}
            normalized["case_behavior_correct"] = False
        normalized_cases.append(normalized)
        execution = {
            "execution_id": execution_id,
            "test_id": case["test_id"],
            "test_visibility": case["test_visibility"],
            "status": error_type or "COMPLETED",
            "stdout_raw": run.stdout,
            "stderr_raw": run.stderr,
            "return_value_serialized": run.return_value,
            "case_behavior_correct": bool(normalized["case_behavior_correct"]),
            "duration_ms": run.duration_ms,
            "error_type": error_type or normalized["failure"]["type"],
            "error_detail": error_detail or normalized["failure"]["detail"],
            "feedback": {"failure": normalized["failure"]},
            "normalized_result": normalized,
            "evaluation_result": {"expected": normalized["expected"], "passed": normalized["case_behavior_correct"]},
        }
        executions.append(execution)
        stdout_parts.append(run.stdout)
        stderr_parts.append(run.stderr)
        if case["test_visibility"] in {"CANONICAL", "VISIBLE"}:
            visible_results.append({
                "test_id": case["test_id"], "name": case["name"],
                "input": {"start": case["start"], "target": case["target"], "walls": case["walls"], "candidates": case["candidates"]},
                "expected": normalized["expected"], "actual": run.return_value,
                "passed": bool(normalized["case_behavior_correct"]),
                "error": error_detail or normalized["failure"]["detail"] or "",
                "visible": True, "execution_id": execution_id,
            })

    behavior_correct = all(item["case_behavior_correct"] for item in executions)
    passed_count = sum(item["case_behavior_correct"] for item in executions)
    hidden = [item for item in executions if item["test_visibility"] == "HIDDEN"]
    first_failure = next((item["normalized_result"]["failure"] for item in executions if not item["case_behavior_correct"]), {"type": None, "detail": None})
    canonical = next((item for item in normalized_cases if item["test_id"] == "VISIBLE-1"), None)
    technique = TechniqueResult(required_technique=None, passed=True, checks={})
    return EvaluationResult(
        status="CORRECT" if behavior_correct else "WRONG",
        score=round(100.0 * passed_count / max(1, len(executions)), 1),
        message="Seluruh kandidat rute dianalisis dengan benar." if behavior_correct else f"{passed_count} dari {len(executions)} test berhasil.",
        program_output=str(canonical["returned_result_raw"] if canonical else ""),
        error_message="" if behavior_correct else str(first_failure.get("detail") or first_failure.get("type") or "Pilihan rute belum benar."),
        stdout="\n---\n".join(stdout_parts), stderr="\n---\n".join(stderr_parts),
        visible_results=visible_results,
        hidden_summary={"total": len(hidden), "passed": sum(item["case_behavior_correct"] for item in hidden)},
        executions=executions,
        case_results=[{
            "test_id": item["test_id"], "execution_id": item["execution_id"],
            "test_visibility": item["test_visibility"], "case_behavior_correct": bool(item["case_behavior_correct"]),
        } for item in executions],
        normalized_cases=normalized_cases,
        behavior_correct=behavior_correct, technique_result=technique, overall_correct=behavior_correct,
    )
