"""Parking animation mapper and serializer with barrier safety enforcement."""

from __future__ import annotations

from typing import Any


class AnimationSerializationError(ValueError):
    pass


_ERROR_ROLES = {"ERROR_STATUS", "TECHNIQUE_STATUS", "TOTAL_ERROR_STATUS"}


def _display(text: str, *, role: str = "OUTPUT") -> dict[str, Any]:
    return {"command": "DISPLAY", "text": text, "role": role}


def _closed_barrier(*, reason: str) -> dict[str, Any]:
    return {"command": "BARRIER", "state": "CLOSE", "safety_reason": reason}


def _failed_transaction_steps(item: dict[str, Any], status_text: str) -> list[dict[str, Any]]:
    actor = item["vehicle"]
    return [
        {"command": "SHOW", "actor": actor, "at": "START", "transaction_correct": False},
        {"command": "APPROACH", "actor": actor, "direction": "EXIT", "transaction_correct": False},
        {"command": "STOP", "actor": actor, "transaction_correct": False},
        _display(item.get("actual_line_display_text") or "OUTPUT_TIDAK_VALID"),
        {"command": "WAIT", "seconds": "1.0"},
        _display(status_text, role="ERROR_STATUS"),
        {"command": "WAIT", "seconds": "1.0"},
        _closed_barrier(reason="TRANSACTION_FAILED"),
    ]


def _successful_vehicle_steps(actor: str, display: str | None = None) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = [
        {"command": "SHOW", "actor": actor, "at": "START", "transaction_correct": True},
        {"command": "APPROACH", "actor": actor, "direction": "EXIT", "transaction_correct": True},
        {"command": "STOP", "actor": actor, "transaction_correct": True},
    ]
    if display is not None:
        steps.extend([_display(display), {"command": "WAIT", "seconds": "1.0"}])
    steps.extend([
        {"command": "BARRIER", "state": "OPEN", "transaction_correct": True},
        {"command": "EXIT", "actor": actor, "transaction_correct": True},
        {"command": "BARRIER", "state": "CLOSE", "transaction_correct": True},
        {"command": "HIDE", "actor": actor, "transaction_correct": True},
    ])
    return steps


def map_parking_single(normalized: dict[str, Any]) -> list[dict[str, Any]]:
    """Map E02 using actual output and block the barrier when the case is wrong."""

    input_data = normalized.get("input_data") or {}
    actor = str(input_data.get("vehicle") or "MOTOR").upper()
    actual = str(normalized.get("actual") or "OUTPUT_TIDAK_VALID").strip() or "OUTPUT_TIDAK_VALID"
    display = f"{actor}_{actual}"
    item = {"vehicle": actor, "actual_line_display_text": display}
    if not bool(normalized.get("case_behavior_correct")):
        return _failed_transaction_steps(item, "JAWABAN_TRANSAKSI_SALAH")
    return _successful_vehicle_steps(actor, display)


def map_parking_loop(
    normalized: dict[str, Any],
    *,
    vehicles: list[dict[str, Any]],
    technique_passed: bool = True,
) -> list[dict[str, Any]]:
    """Map M01 without opening the barrier for behavior or technique failure."""

    actual = str(normalized.get("actual") or "OUTPUT_TIDAK_VALID").strip() or "OUTPUT_TIDAK_VALID"
    case_correct = bool(normalized.get("case_behavior_correct"))

    if not technique_passed or not case_correct:
        status = "TEKNIK_WHILE_BELUM_DIPENUHI" if not technique_passed else "JAWABAN_SESI_SALAH"
        if vehicles:
            actor = str(vehicles[0].get("vehicle") or "MOTOR").upper()
            return _failed_transaction_steps(
                {"vehicle": actor, "actual_line_display_text": actual},
                status,
            )
        return [
            _display(actual),
            {"command": "WAIT", "seconds": "1.0"},
            _display(status, role="TECHNIQUE_STATUS" if not technique_passed else "ERROR_STATUS"),
            {"command": "WAIT", "seconds": "1.0"},
            _closed_barrier(reason="TECHNIQUE_FAILED" if not technique_passed else "SESSION_FAILED"),
        ]

    steps: list[dict[str, Any]] = []
    for vehicle in vehicles:
        actor = str(vehicle.get("vehicle") or "MOTOR").upper()
        steps.extend(_successful_vehicle_steps(actor))
    steps.extend([_display(actual), {"command": "WAIT", "seconds": "1.5"}])
    return steps


def map_parking_session(
    normalized: dict[str, Any],
    *,
    technique_passed: bool = True,
) -> list[dict[str, Any]]:
    """Map actual normalized output without allowing a failed vehicle to exit.

    Correct transactions retain the established storyboard. The first failed
    transaction stops the sequence with the barrier closed. A technique-only
    failure is visualized as a failed first transaction and never opens the
    barrier.
    """

    vehicles = list(normalized.get("vehicles") or [])
    steps: list[dict[str, Any]] = []

    if not technique_passed:
        if vehicles:
            steps.extend(_failed_transaction_steps(vehicles[0], "TEKNIK_WHILE_BELUM_DIPENUHI"))
        else:
            steps.extend([
                _display("TEKNIK_WHILE_BELUM_DIPENUHI", role="TECHNIQUE_STATUS"),
                {"command": "WAIT", "seconds": "1.5"},
                _closed_barrier(reason="TECHNIQUE_FAILED"),
            ])
        return steps

    for item in vehicles:
        actor = item["vehicle"]
        display = item.get("actual_line_display_text") or "OUTPUT_TIDAK_VALID"
        if not bool(item.get("correct", True)):
            steps.extend(_failed_transaction_steps(item, "JAWABAN_TRANSAKSI_SALAH"))
            return steps

        steps.extend(
            [
                {"command": "SHOW", "actor": actor, "at": "START", "transaction_correct": True},
                {"command": "APPROACH", "actor": actor, "direction": "EXIT", "transaction_correct": True},
                {"command": "STOP", "actor": actor, "transaction_correct": True},
                _display(display),
                {"command": "WAIT", "seconds": "1.0"},
                {"command": "BARRIER", "state": "OPEN", "transaction_correct": True},
                {"command": "EXIT", "actor": actor, "transaction_correct": True},
                {"command": "BARRIER", "state": "CLOSE", "transaction_correct": True},
                {"command": "HIDE", "actor": actor, "transaction_correct": True},
            ]
        )

    steps.extend(
        [
            _display(normalized.get("actual_total_line_display_text") or "OUTPUT_TIDAK_VALID"),
            {"command": "WAIT", "seconds": "1.5"},
        ]
    )

    total_correct = bool(
        normalized.get("output_structure_correct", True)
        and normalized.get("total_value_correct", True)
        and normalized.get("total_label_correct", True)
    )
    if not total_correct:
        steps.extend([
            _display("TOTAL_SESI_SALAH", role="TOTAL_ERROR_STATUS"),
            {"command": "WAIT", "seconds": "1.0"},
            _closed_barrier(reason="TOTAL_FAILED"),
        ])
    return steps


def serialize_parking(animation_run_id: str, steps: list[dict[str, Any]]) -> str:
    validate_parking_sequence(animation_run_id, steps)
    sequence = ">".join(_serialize_step(step) for step in steps)
    payload = f"RESULT|PARKING|{animation_run_id}|{sequence}"
    if len(sequence) > 900:
        raise AnimationSerializationError("Parking sequence exceeds 900 characters.")
    return payload


def validate_parking_sequence(animation_run_id: str, steps: list[dict[str, Any]]) -> None:
    if not animation_run_id:
        raise AnimationSerializationError("animation_run_id is required.")
    if not steps:
        raise AnimationSerializationError("Parking sequence is empty.")
    if len(steps) > 40:
        raise AnimationSerializationError("Parking sequence exceeds 40 steps.")

    supported = {"SHOW", "APPROACH", "STOP", "DISPLAY", "WAIT", "BARRIER", "EXIT", "HIDE"}
    current_transaction_correct: bool | None = None
    failure_seen = False
    for step in steps:
        command = step.get("command")
        if command not in supported:
            raise AnimationSerializationError(f"Unsupported Parking command: {command}.")
        if command == "DISPLAY" and len(str(step.get("text", ""))) > 80:
            raise AnimationSerializationError("Parking display exceeds 80 characters.")
        if command == "SHOW":
            if not step.get("at"):
                raise AnimationSerializationError("SHOW requires AT.")
            current_transaction_correct = step.get("transaction_correct")
            if current_transaction_correct is False:
                failure_seen = True
        if command == "APPROACH" and step.get("direction") != "EXIT":
            raise AnimationSerializationError("APPROACH requires DIRECTION=EXIT.")
        if command == "DISPLAY" and step.get("role") in _ERROR_ROLES:
            failure_seen = True
        if command == "BARRIER":
            if step.get("state") not in {"OPEN", "CLOSE"}:
                raise AnimationSerializationError("Parking barrier state must be OPEN or CLOSE.")
            if step.get("state") == "OPEN" and (failure_seen or current_transaction_correct is not True):
                raise AnimationSerializationError("Barrier OPEN is forbidden after a failed transaction or technique.")
        if command == "EXIT" and (failure_seen or current_transaction_correct is not True):
            raise AnimationSerializationError("Vehicle EXIT is forbidden after a failed transaction or technique.")

    # Preserve the established successful 9-step vehicle storyboard.
    index = 0
    while index + 8 < len(steps):
        if steps[index].get("command") != "SHOW":
            break
        block = steps[index:index + 9]
        commands = [item.get("command") for item in block]
        if commands == ["SHOW", "APPROACH", "STOP", "DISPLAY", "WAIT", "BARRIER", "EXIT", "BARRIER", "HIDE"]:
            if block[5].get("state") != "OPEN" or block[7].get("state") != "CLOSE":
                raise AnimationSerializationError("Parking barrier order is invalid.")
            index += 9
        else:
            break

    sequence = ">".join(_serialize_step(step) for step in steps)
    if len(sequence) > 900:
        raise AnimationSerializationError("Parking sequence exceeds 900 characters.")


def _serialize_step(step: dict[str, Any]) -> str:
    command = step["command"]
    ordered_keys = {
        "SHOW": ("actor", "at"),
        "APPROACH": ("actor", "direction"),
        "STOP": ("actor",),
        "DISPLAY": ("text",),
        "WAIT": ("seconds",),
        "BARRIER": ("state",),
        "EXIT": ("actor",),
        "HIDE": ("actor",),
    }[command]
    labels = {
        "actor": "ACTOR", "at": "AT", "direction": "DIRECTION", "text": "TEXT",
        "seconds": "SECONDS", "state": "STATE",
    }
    values = [command]
    for key in ordered_keys:
        values.append(f"{labels[key]}={step[key]}")
    return ",".join(values)
