"""River recursion animation mapper and exact serializer."""

from __future__ import annotations

from typing import Any


class RiverSerializationError(ValueError):
    pass


def map_river_recursion(normalized: dict[str, Any]) -> list[str]:
    steps: list[str] = []
    for move in normalized.get("executed_moves") or []:
        actors = "+".join(move["actors"])
        steps.extend([
            f"LOAD={actors}",
            f"BOAT={move['destination_side']}",
            f"UNLOAD={actors}",
        ])
    failure = (normalized.get("failure") or {}).get("type")
    victim = (normalized.get("failure") or {}).get("victim")
    if failure == "UNSAFE_STATE" and victim in {"DOMBA", "RUMPUT"}:
        steps.append(f"INVALID={victim}")
    elif normalized.get("case_behavior_correct") and normalized.get("reached_goal") and failure is None:
        steps.append("SUCCESS")
    return steps


def serialize_river(animation_run_id: str, steps: list[str]) -> str:
    if not animation_run_id or any(char in animation_run_id for char in "|>"):
        raise RiverSerializationError("Invalid animation_run_id.")
    if not steps:
        raise RiverSerializationError("River sequence has no animation step.")
    if len(steps) > 40:
        raise RiverSerializationError("River sequence exceeds 40 steps.")
    invalid_positions = [index for index, step in enumerate(steps) if step.startswith("INVALID=")]
    if invalid_positions and invalid_positions != [len(steps) - 1]:
        raise RiverSerializationError("INVALID must be the final step.")
    if any(step == "INVALID=" for step in steps):
        raise RiverSerializationError("Empty INVALID is forbidden.")
    if "SUCCESS" in steps and steps[-1] != "SUCCESS":
        raise RiverSerializationError("SUCCESS must be final.")
    payload = f"RESULT|RIVER|{animation_run_id}|" + ">".join(steps)
    if len(payload) > 1200:
        raise RiverSerializationError("River payload exceeds 1200 characters.")
    return payload
