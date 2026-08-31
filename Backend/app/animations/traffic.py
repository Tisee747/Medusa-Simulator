"""Traffic final animation selector support and exact serializers."""

from __future__ import annotations

from typing import Any


class TrafficSerializationError(ValueError):
    pass


def safe_traffic_action(normalized: dict[str, Any]) -> str:
    if not normalized.get("action_recognized"):
        return "UNKNOWN"
    actual = normalized.get("actual_action")
    if actual in {"BERHENTI", "HATI_HATI", "JALAN"}:
        return str(actual)
    return "UNKNOWN"


def serialize_main_sequence(animation_run_id: str, cases: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    if not animation_run_id or any(char in animation_run_id for char in "|;~"):
        raise TrafficSerializationError("Invalid animation_run_id.")
    required = ("VISIBLE-YELLOW", "VISIBLE-RED", "VISIBLE-GREEN")
    if any(test_id not in cases for test_id in required):
        raise TrafficSerializationError("Traffic main sequence requires yellow, red, and green executions.")
    ordered = [
        ("KUNING", cases["VISIBLE-YELLOW"], "HATI_HATI"),
        ("MERAH", cases["VISIBLE-RED"], "BERHENTI"),
        ("HIJAU", cases["VISIBLE-GREEN"], "JALAN"),
    ]
    steps: list[dict[str, Any]] = []
    encoded: list[str] = []
    for color, normalized, expected in ordered:
        actual = safe_traffic_action(normalized)
        if any(char in value for value in (color, actual, expected) for char in "|;~"):
            raise TrafficSerializationError("Traffic field contains a protocol delimiter.")
        steps.append({"color": color, "actual": actual, "expected": expected})
        encoded.append(f"{color}~{actual}~{expected}")
    payload = f"RESULT_SEQ|{animation_run_id}|3|" + ";".join(encoded)
    if len(payload) > 900:
        raise TrafficSerializationError("Traffic payload exceeds 900 characters.")
    return payload, {"steps": steps, "source": "actual_execution_results"}


def serialize_invalid_preview(animation_run_id: str, normalized: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if not animation_run_id or "|" in animation_run_id:
        raise TrafficSerializationError("Invalid animation_run_id.")
    actual = safe_traffic_action(normalized)
    payload = f"RESULT|E01_TRAFFIC|TRAFFIC|{animation_run_id}|BIRU|{actual}|TIDAK_VALID"
    if len(payload) > 900:
        raise TrafficSerializationError("Traffic payload exceeds 900 characters.")
    return payload, {"steps": [{"color": "BIRU", "actual": actual, "expected": "TIDAK_VALID"}], "source": "actual_execution_result"}
