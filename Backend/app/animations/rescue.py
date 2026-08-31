"""Actual-result Rescue mapper and strict production serializer.

The backend is authoritative for the selected case, start/target, safe actual
prefix, and terminal result. The LSL controller only executes validated actions.
"""

from __future__ import annotations

import re
from typing import Any


class RescueSerializationError(ValueError):
    pass


_DELTA_TO_TOKEN = {
    (-1, 0): "UP",
    (1, 0): "DOWN",
    (0, -1): "LEFT",
    (0, 1): "RIGHT",
}
_TOKEN_TO_DELTA = {value: key for key, value in _DELTA_TO_TOKEN.items()}
_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9._:-]+$")
_SAFE_TERMINAL_TOKEN = re.compile(r"[^A-Z0-9_:-]+")
_TERMINAL_PREFIXES = ("GOAL=", "HIT_WALL=", "OUT_OF_GRID=", "INVALID_STEP=")


def _coord(value: Any) -> list[int] | None:
    if isinstance(value, dict):
        row = value.get("row")
        column = value.get("column")
    elif isinstance(value, (list, tuple)) and len(value) == 2:
        row, column = value
    else:
        return None
    if not isinstance(row, int) or isinstance(row, bool):
        return None
    if not isinstance(column, int) or isinstance(column, bool):
        return None
    if not (0 <= row <= 4 and 0 <= column <= 4):
        return None
    return [row, column]


def _terminal_token(value: Any) -> str:
    text = str(value if value is not None else "TIDAK_DIKENAL").strip().upper()
    text = _SAFE_TERMINAL_TOKEN.sub("_", text).strip("_")
    if not text:
        text = "TIDAK_DIKENAL"
    return text[:64]


def _path_moves(safe_path: list[Any]) -> list[str]:
    steps: list[str] = []
    for previous, current in zip(safe_path, safe_path[1:]):
        if not (
            isinstance(previous, (list, tuple)) and len(previous) == 2
            and isinstance(current, (list, tuple)) and len(current) == 2
        ):
            break
        delta = (current[0] - previous[0], current[1] - previous[1])
        token = _DELTA_TO_TOKEN.get(delta)
        if token is None:
            break
        steps.append(f"MOVE={token}")
    return steps


def _invalid_raw_token(normalized: dict[str, Any], failure_index: int | None) -> Any:
    if failure_index is None:
        return None
    returned_items = normalized.get("returned_items") or []
    for item in returned_items:
        if item.get("index") == failure_index:
            return item.get("raw_value")
    actual = normalized.get("actual") or {}
    selected = actual.get("selected_path")
    if isinstance(selected, list) and 0 <= failure_index < len(selected):
        return selected[failure_index]
    returned = normalized.get("returned_path_raw")
    if isinstance(returned, list) and 0 <= failure_index < len(returned):
        return returned[failure_index]
    return None


def _next_input_direction(normalized: dict[str, Any], safe_path: list[Any], index: int | None = None) -> str | None:
    input_steps = normalized.get("input_steps") or []
    if index is None:
        index = max(0, len(safe_path) - 1)
    if 0 <= index < len(input_steps):
        token = str(input_steps[index]).strip().upper()
        if token in _TOKEN_TO_DELTA:
            return token
    return None


def map_rescue_path(
    normalized: dict[str, Any],
    *,
    technique_required: str | None = None,
    technique_passed: bool = True,
) -> list[str]:
    """Build one START + actual safe prefix + terminal sequence.

    Expected paths are never consulted. Malformed returns without a trustworthy
    start coordinate are not animatable.
    """

    start = _coord(normalized.get("start"))
    if start is None:
        return []

    safe_path = normalized.get("safe_executable_path") or []
    if not safe_path:
        return []
    first = _coord(safe_path[0])
    if first != start:
        return []

    steps = [f"START={start[0]},{start[1]}"]
    steps.extend(_path_moves(safe_path))

    actual = normalized.get("actual") or {}
    target = _coord(normalized.get("target"))
    simulation = normalized.get("simulation_result") or {}
    failure = normalized.get("failure") or {}
    failure_type = simulation.get("failure_type") or failure.get("type")
    failure_index = simulation.get("failure_index")
    if failure_index is None:
        failure_index = failure.get("index")
    if failure_index is None:
        failure_index = failure.get("path_index")

    # Physical wall collision is only emitted when the actual selected case
    # provides an in-grid attempted wall coordinate.
    wall_attempt = normalized.get("animation_wall_attempt")
    walls = {tuple(item) for item in normalized.get("walls") or [] if isinstance(item, (list, tuple)) and len(item) == 2}
    if _coord(wall_attempt) is not None and tuple(wall_attempt) in walls:
        steps.append(f"HIT_WALL={wall_attempt[0]},{wall_attempt[1]}")
        return steps

    actual_status = actual.get("status")
    if actual_status == "MENABRAK_DINDING":
        direction = _next_input_direction(normalized, safe_path, failure_index)
        if direction:
            current = safe_path[-1]
            dr, dc = _TOKEN_TO_DELTA[direction]
            attempted = [current[0] + dr, current[1] + dc]
            if _coord(attempted) is not None and tuple(attempted) in walls:
                steps.append(f"HIT_WALL={attempted[0]},{attempted[1]}")
                return steps

    if failure_type in {"PATH_OUT_OF_GRID"} or actual_status == "KELUAR_GRID":
        direction = _next_input_direction(normalized, safe_path, failure_index)
        if direction:
            steps.append(f"OUT_OF_GRID={direction}")
            return steps

    if failure_type in {"INVALID_DIRECTION_TOKEN", "INVALID_TOKEN", "MALFORMED_RETURN_ITEM"}:
        steps.append(f"INVALID_STEP={_terminal_token(_invalid_raw_token(normalized, failure_index))}")
        return steps

    goal_allowed = bool(normalized.get("animation_goal_allowed"))
    if normalized.get("animation_goal_allowed") is None:
        goal_allowed = bool(
            actual_status == "BERHASIL"
            and target is not None
            and safe_path[-1] == target
            and failure_type is None
        )

    if goal_allowed and target is not None and safe_path[-1] == target:
        if technique_required == "BFS" and not technique_passed:
            steps.append("INVALID_STEP=TEKNIK_BFS_BELUM_TERPENUHI")
        else:
            steps.append(f"GOAL={target[0]},{target[1]}")
        return steps

    # A valid actual path that simply stops early remains visible and ends with
    # an explicit incomplete status. This also covers wrong selected_index with
    # a safe selected_path that does not reach the target.
    steps.append("INCOMPLETE")
    return steps


def map_rescue_legacy(
    *,
    path: list[Any],
    start: list[int],
    target: list[int],
    walls: list[list[int]],
) -> tuple[list[str], dict[str, Any]]:
    """Adapt legacy U/D/L/R output into the same actual-result envelope."""

    start_coord = _coord(start)
    target_coord = _coord(target)
    if start_coord is None or target_coord is None:
        return [], {}
    wall_set = {tuple(item) for item in walls}
    current = list(start_coord)
    safe_path = [list(current)]
    terminal = "INCOMPLETE"
    normalized_tokens: list[str] = []

    aliases = {"U": "UP", "D": "DOWN", "L": "LEFT", "R": "RIGHT"}
    for raw in path:
        token = str(raw).strip().upper()
        token = aliases.get(token, token)
        if token not in _TOKEN_TO_DELTA:
            terminal = f"INVALID_STEP={_terminal_token(raw)}"
            break
        normalized_tokens.append(token)
        dr, dc = _TOKEN_TO_DELTA[token]
        candidate = [current[0] + dr, current[1] + dc]
        if not (0 <= candidate[0] <= 4 and 0 <= candidate[1] <= 4):
            terminal = f"OUT_OF_GRID={token}"
            break
        if tuple(candidate) in wall_set:
            terminal = f"HIT_WALL={candidate[0]},{candidate[1]}"
            break
        current = candidate
        safe_path.append(list(current))
        if current == target_coord:
            terminal = f"GOAL={target_coord[0]},{target_coord[1]}"
            break

    steps = [f"START={start_coord[0]},{start_coord[1]}"] + _path_moves(safe_path) + [terminal]
    return steps, {
        "start": start_coord,
        "target": target_coord,
        "walls": [list(item) for item in walls],
        "actual_path": list(path),
        "normalized_tokens": normalized_tokens,
        "safe_executable_path": safe_path,
        "terminal": terminal,
    }


def _parse_coordinate(value: str, action: str) -> tuple[int, int]:
    parts = value.split(",")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise RescueSerializationError(f"Invalid {action} coordinate.")
    row, column = map(int, parts)
    if not (0 <= row <= 4 and 0 <= column <= 4):
        raise RescueSerializationError(f"{action} coordinate is outside the board.")
    return row, column


def serialize_rescue(animation_run_id: str, steps: list[str]) -> str:
    if not animation_run_id or not _SAFE_RUN_ID.fullmatch(animation_run_id):
        raise RescueSerializationError("Invalid animation_run_id.")
    if not steps:
        raise RescueSerializationError("Rescue sequence has no safe action.")
    if len(steps) > 60:
        raise RescueSerializationError("Rescue sequence exceeds 60 steps.")
    if not steps[0].startswith("START="):
        raise RescueSerializationError("Rescue sequence must begin with START.")

    terminal_seen = False
    start_seen = False
    for index, step in enumerate(steps):
        if any(delimiter in step for delimiter in ("|", ">", "\n", "\r")):
            raise RescueSerializationError("Rescue step contains a protocol delimiter.")
        if terminal_seen:
            raise RescueSerializationError("No action is allowed after a terminal action.")

        if step.startswith("START="):
            if index != 0 or start_seen:
                raise RescueSerializationError("START must appear exactly once as the first action.")
            _parse_coordinate(step.split("=", 1)[1], "START")
            start_seen = True
        elif step.startswith("MOVE="):
            if not start_seen:
                raise RescueSerializationError("MOVE cannot appear before START.")
            if step.split("=", 1)[1] not in _TOKEN_TO_DELTA:
                raise RescueSerializationError("Invalid MOVE token.")
        elif step.startswith("GOAL="):
            _parse_coordinate(step.split("=", 1)[1], "GOAL")
            terminal_seen = True
        elif step.startswith("HIT_WALL="):
            _parse_coordinate(step.split("=", 1)[1], "HIT_WALL")
            terminal_seen = True
        elif step.startswith("OUT_OF_GRID="):
            if step.split("=", 1)[1] not in _TOKEN_TO_DELTA:
                raise RescueSerializationError("Invalid OUT_OF_GRID direction.")
            terminal_seen = True
        elif step.startswith("INVALID_STEP="):
            token = step.split("=", 1)[1]
            if not token or _SAFE_TERMINAL_TOKEN.search(token):
                raise RescueSerializationError("Invalid INVALID_STEP token.")
            terminal_seen = True
        elif step == "INCOMPLETE":
            terminal_seen = True
        else:
            raise RescueSerializationError(f"Unsupported Rescue action at index {index}.")

    if not terminal_seen:
        raise RescueSerializationError("Rescue sequence must end with a terminal action.")

    payload = f"RESULT|RESCUE|{animation_run_id}|" + ">".join(steps)
    if len(payload) > 1600:
        raise RescueSerializationError("Rescue payload exceeds 1600 characters.")
    if payload.count("|") != 3:
        raise RescueSerializationError("Rescue payload must contain exactly four fields.")
    return payload
