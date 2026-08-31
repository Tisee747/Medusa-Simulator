"""Per-function state simulation for H02_RIVER_RECURSION."""

from __future__ import annotations

from typing import Any

from app.code_runner import FunctionRunResult, run_function
from app.ids import new_execution_id
from app.questions.base import EvaluationResult, TechniqueResult

_TOKENS = ("SENDIRI", "SERIGALA", "DOMBA", "RUMPUT")
_INDEX = {"SERIGALA": 1, "DOMBA": 2, "RUMPUT": 3}
_ACTORS = {"SENDIRI": ["GEMBALA"], "SERIGALA": ["GEMBALA", "SERIGALA"], "DOMBA": ["GEMBALA", "DOMBA"], "RUMPUT": ["GEMBALA", "RUMPUT"]}


def normalize_river_path(
    returned: Any,
    *,
    start_state: tuple[int, int, int, int],
    goal_state: tuple[int, int, int, int],
    execution_id: str,
    test_id: str,
    test_visibility: str,
) -> dict[str, Any]:
    returned_items: list[dict[str, Any]] = []
    executed_moves: list[dict[str, Any]] = []
    failure = {"type": None, "victim": None, "move_index": None, "detail": None}
    state = tuple(start_state)
    reached_goal = state == tuple(goal_state)

    if returned is None:
        failure = {"type": "NO_PATH", "victim": None, "move_index": None, "detail": "Fungsi mengembalikan None."}
        return _river_result(execution_id, test_id, test_visibility, start_state, goal_state, returned, returned_items, executed_moves, failure, reached_goal, 0)
    if not isinstance(returned, list):
        failure = {"type": "INVALID_RETURN_TYPE", "victim": None, "move_index": None, "detail": "Return harus list."}
        return _river_result(execution_id, test_id, test_visibility, start_state, goal_state, returned, returned_items, executed_moves, failure, reached_goal, 0)

    first_invalid_index: int | None = None
    first_invalid_type: str | None = None
    for index, raw in enumerate(returned, 1):
        normalized: str | None = None
        valid = False
        invalid_type: str | None = None
        if not isinstance(raw, str) or raw.strip() == "":
            invalid_type = "MALFORMED_RETURN_ITEM"
        else:
            candidate = raw.strip().upper()
            if candidate in _TOKENS:
                normalized = candidate
                valid = True
            else:
                invalid_type = "INVALID_TOKEN"
        returned_items.append({
            "index": index, "raw_value": raw, "normalized_token": normalized, "item_valid": valid,
        })
        if first_invalid_index is None and invalid_type:
            first_invalid_index = index
            first_invalid_type = invalid_type

    limit = (first_invalid_index - 1) if first_invalid_index is not None else len(returned_items)
    for offset in range(limit):
        item = returned_items[offset]
        index = item["index"]
        token = item["normalized_token"]
        if reached_goal:
            failure = {
                "type": "EXTRA_MOVES_AFTER_GOAL", "victim": None, "move_index": index,
                "detail": "Jalur masih memiliki perjalanan setelah tujuan tercapai.",
            }
            break
        if index > 10:
            failure = {
                "type": "TOO_MANY_MOVES", "victim": None, "move_index": index,
                "detail": "Jalur melebihi 10 perjalanan.",
            }
            break
        state_before = state
        shepherd_side = state[0]
        if token != "SENDIRI" and state[_INDEX[token]] != shepherd_side:
            failure = {
                "type": "ACTOR_WRONG_SIDE", "victim": None, "move_index": index,
                "detail": f"{token} tidak berada di sisi yang sama dengan gembala.",
            }
            break
        next_state = list(state)
        destination = 1 - shepherd_side
        next_state[0] = destination
        if token != "SENDIRI":
            next_state[_INDEX[token]] = destination
        state = tuple(next_state)
        victim = _unsafe_victim(state)
        safe = victim is None
        executed_moves.append({
            "index": index,
            "passenger": token,
            "destination_side": _side(destination),
            "actors": _ACTORS[token],
            "state_before": _state_object(state_before),
            "state_after": _state_object(state),
            "legal_move": True,
            "safe_state": safe,
        })
        if not safe:
            failure = {
                "type": "UNSAFE_STATE", "victim": victim, "move_index": index,
                "detail": f"State setelah perjalanan tidak aman untuk {victim}.",
            }
            break
        reached_goal = state == tuple(goal_state)

    if failure["type"] is None and first_invalid_index is not None:
        failure = {
            "type": first_invalid_type,
            "victim": None,
            "move_index": first_invalid_index,
            "detail": "Item return tidak dapat digunakan sebagai token perjalanan.",
        }
    elif failure["type"] is None:
        if reached_goal and len(returned_items) > len(executed_moves):
            failure = {
                "type": "EXTRA_MOVES_AFTER_GOAL", "victim": None,
                "move_index": len(executed_moves) + 1,
                "detail": "Jalur masih memiliki perjalanan setelah tujuan tercapai.",
            }
        elif not reached_goal:
            failure = {
                "type": "INCOMPLETE", "victim": None, "move_index": None,
                "detail": "Jalur legal dan aman, tetapi belum mencapai goal state.",
            }

    return _river_result(
        execution_id, test_id, test_visibility, start_state, goal_state, returned,
        returned_items, executed_moves, failure, reached_goal, len(returned),
    )


def _river_result(
    execution_id: str, test_id: str, test_visibility: str,
    start_state: tuple[int, int, int, int], goal_state: tuple[int, int, int, int],
    returned: Any, returned_items: list[dict[str, Any]], executed_moves: list[dict[str, Any]],
    failure: dict[str, Any], reached_goal: bool, returned_count: int,
) -> dict[str, Any]:
    correct = (
        isinstance(returned, list)
        and all(item["item_valid"] for item in returned_items)
        and all(item["legal_move"] and item["safe_state"] for item in executed_moves)
        and reached_goal
        and len(returned_items) == len(executed_moves)
        and len(returned_items) <= 10
        and failure["type"] is None
    )
    canonical = test_visibility == "CANONICAL"
    return {
        "execution_id": execution_id,
        "test_id": test_id,
        "test_visibility": test_visibility,
        "animation_case_id": "canonical" if canonical else None,
        "animation_source": "canonical_function_return" if canonical else None,
        "start_state": _state_object(start_state),
        "goal_state": _state_object(goal_state),
        "returned_path_raw": returned,
        "returned_items": returned_items,
        "executed_moves": executed_moves,
        "failure": failure,
        "reached_goal": reached_goal,
        "returned_move_count": returned_count,
        "executed_move_count": len(executed_moves),
        "case_behavior_correct": correct,
        "input_data": {"start_state": list(start_state), "goal_state": list(goal_state)},
    }


def evaluate_river_recursion(source_code: str, data: dict[str, Any]) -> EvaluationResult:
    executions: list[dict[str, Any]] = []
    normalized_cases: list[dict[str, Any]] = []
    case_results: list[dict[str, Any]] = []
    visible_results: list[dict[str, Any]] = []
    stdout_parts: list[str] = []
    stderr_parts: list[str] = []

    for case in data["cases"]:
        execution_id = new_execution_id()
        start = tuple(case["start_state"])
        goal = tuple(case["goal_state"])
        run = run_function(source_code, function_name="cari_jalur", args=[start, goal])
        normalized = normalize_river_path(
            run.return_value,
            start_state=start,
            goal_state=goal,
            execution_id=execution_id,
            test_id=case["test_id"],
            test_visibility=case["test_visibility"],
        )
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
            "input": {"start_state": list(start), "goal_state": list(goal)},
            "expected": "Jalur legal, aman, <=10, dan mencapai goal tepat pada akhir list.",
            "actual": run.return_value,
            "passed": passed,
            "error": error_detail or normalized["failure"],
            "visible": case["test_visibility"] != "HIDDEN",
            "execution_id": execution_id,
        }
        if case["test_visibility"] != "HIDDEN":
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
            "error_type": error_type or normalized["failure"]["type"],
            "error_detail": error_detail or normalized["failure"]["detail"],
            "feedback": feedback,
            "normalized_result": normalized,
            "evaluation_result": {
                "failure": normalized["failure"], "reached_goal": normalized["reached_goal"],
            },
        })
        stdout_parts.append(run.stdout)
        stderr_parts.append(run.stderr)

    passed_count = sum(1 for item in case_results if item["case_behavior_correct"])
    behavior_correct = passed_count == len(case_results)
    hidden = [item for item in case_results if item["test_visibility"] == "HIDDEN"]
    first_runtime_error = next((item["error_detail"] for item in executions if item["status"] != "COMPLETED"), "")
    canonical = next((case for case in normalized_cases if case["test_visibility"] == "CANONICAL"), None)
    canonical_path = canonical.get("returned_path_raw") if canonical else []
    program_output = "\n".join(canonical_path) if isinstance(canonical_path, list) and all(isinstance(x, str) for x in canonical_path) else ""
    return EvaluationResult(
        status="CORRECT" if behavior_correct else ("ERROR" if first_runtime_error else "WRONG"),
        score=round(100.0 * passed_count / max(1, len(case_results)), 1),
        message="Seluruh canonical, visible, dan hidden behavior test berhasil." if behavior_correct else f"{passed_count} dari {len(case_results)} function test berhasil.",
        program_output=program_output,
        error_message=first_runtime_error,
        stdout="\n---\n".join(stdout_parts),
        stderr="\n---\n".join(stderr_parts),
        visible_results=visible_results,
        hidden_summary={"total": len(hidden), "passed": sum(1 for item in hidden if item["case_behavior_correct"])},
        executions=executions,
        case_results=case_results,
        normalized_cases=normalized_cases,
        behavior_correct=behavior_correct,
        technique_result=TechniqueResult("RECURSION", False, {
            "recursive_call_exists": False, "reachable_from_required_function": False,
        }),
        overall_correct=False,
    )


def _unsafe_victim(state: tuple[int, int, int, int]) -> str | None:
    gembala, serigala, domba, rumput = state
    if serigala == domba and gembala != domba:
        return "DOMBA"
    if domba == rumput and gembala != domba:
        return "RUMPUT"
    return None


def _state_object(state: tuple[int, int, int, int]) -> dict[str, str]:
    return {
        "gembala": _side(state[0]), "serigala": _side(state[1]),
        "domba": _side(state[2]), "rumput": _side(state[3]),
    }


def _side(value: int) -> str:
    return "RIGHT" if int(value) == 1 else "LEFT"


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
