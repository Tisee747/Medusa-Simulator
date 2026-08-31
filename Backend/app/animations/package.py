"""Package animation mappers with dynamic actor labels and exact serializer."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, unquote


class PackageSerializationError(ValueError):
    pass


_ACTORS = {f"PACKAGE_{index}" for index in range(1, 6)}
_SLOTS = {f"SLOT_{index}" for index in range(1, 6)}


def _label_step(package_id: str, text: str) -> str:
    encoded = quote(text, safe="_-.")
    return f"LABEL={package_id},TEXT={encoded}"


def package_sort_labels(input_values: list[Any]) -> list[str]:
    steps = ["LABEL_CLEAR=ALL"]
    for index, value in enumerate(input_values[:5], 1):
        steps.append(_label_step(f"PACKAGE_{index}", f"PACKAGE_{index}\nNILAI: {value}"))
    return steps


def package_data_labels(normalized: dict[str, Any]) -> list[str]:
    steps = ["LABEL_CLEAR=ALL"]
    records = ((normalized.get("input_data") or {}).get("data") or [])
    for record in records:
        if not isinstance(record, (list, tuple)) or len(record) != 3:
            continue
        package_id, category, weight = record
        if package_id in _ACTORS:
            steps.append(_label_step(str(package_id), f"{package_id}\n{category}\n{weight} KG"))
    return steps


def map_package_data(normalized: dict[str, Any], *, include_labels: bool = False) -> list[str]:
    executable = normalized.get("executable") or {}
    steps: list[str] = package_data_labels(normalized) if include_labels else []
    highlight = executable.get("highlight_terberat")
    if highlight:
        steps.append(f"HIGHLIGHT={highlight}")
    for logical_index, package_id in enumerate(executable.get("lolos_package_ids") or [], 1):
        steps.extend([
            f"PACKAGE={package_id},ACTION=PICK",
            f"PACKAGE={package_id},ACTION=MOVE,TARGET=SLOT_{logical_index}",
            f"PACKAGE={package_id},ACTION=DROP",
        ])
    return steps


def map_package_sort(input_values: list[Any], actual_output: str) -> tuple[list[str], dict[str, Any]]:
    """Map the user's actual output order to package actors using a safe prefix."""

    steps = package_sort_labels(input_values)
    actual_tokens = str(actual_output or "").split()
    used: set[int] = set()
    mapped: list[dict[str, Any]] = []
    failure: dict[str, Any] | None = None

    for slot_index, token in enumerate(actual_tokens[:5], 1):
        actor_index: int | None = None
        for index, value in enumerate(input_values[:5], 1):
            if index not in used and str(value) == token:
                actor_index = index
                break
        if actor_index is None:
            failure = {"type": "UNMATCHED_ACTUAL_VALUE", "index": slot_index - 1, "value": token}
            break
        used.add(actor_index)
        package_id = f"PACKAGE_{actor_index}"
        steps.extend([
            f"PACKAGE={package_id},ACTION=PICK",
            f"PACKAGE={package_id},ACTION=MOVE,TARGET=SLOT_{slot_index}",
            f"PACKAGE={package_id},ACTION=DROP",
        ])
        mapped.append({"package_id": package_id, "value": input_values[actor_index - 1], "slot": f"SLOT_{slot_index}"})

    return steps, {
        "input_values": list(input_values),
        "actual_output_tokens": actual_tokens,
        "mapped_actual_prefix": mapped,
        "mapping_failure": failure,
    }


def serialize_package(animation_run_id: str, steps: list[str]) -> str:
    if not animation_run_id or any(char in animation_run_id for char in "|>,="):
        raise PackageSerializationError("Invalid animation_run_id.")
    if not steps:
        raise PackageSerializationError("Package sequence has no safe step.")
    if len(steps) > 40:
        raise PackageSerializationError("Package sequence exceeds 40 steps.")

    movement_seen = False
    labels_seen: set[str] = set()
    for step in steps:
        if ">" in step or "|" in step or "\n" in step or "\r" in step:
            raise PackageSerializationError("Package step contains a protocol delimiter.")
        if step == "LABEL_CLEAR=ALL":
            if movement_seen:
                raise PackageSerializationError("Labels must be reset before movement.")
            continue
        if step.startswith("LABEL="):
            if movement_seen:
                raise PackageSerializationError("Package labels must be sent before movement.")
            parts = dict(part.split("=", 1) for part in step.split(",") if "=" in part)
            package_id = parts.get("LABEL", "")
            encoded = parts.get("TEXT", "")
            if package_id not in _ACTORS or not encoded:
                raise PackageSerializationError("Invalid package label step.")
            decoded = unquote(encoded)
            if any(delimiter in decoded for delimiter in ("|", ">", "\r")) or len(decoded) > 80:
                raise PackageSerializationError("Unsafe package label text.")
            labels_seen.add(package_id)
            continue

        movement_seen = True
        if step.startswith("HIGHLIGHT="):
            if step.split("=", 1)[1] not in _ACTORS:
                raise PackageSerializationError("Invalid package highlight actor.")
            continue
        if step.startswith("PACKAGE="):
            parts = dict(part.split("=", 1) for part in step.split(",") if "=" in part)
            package_id = parts.get("PACKAGE", "")
            if package_id not in _ACTORS:
                raise PackageSerializationError("Invalid package actor.")
            action = parts.get("ACTION")
            if action not in {"PICK", "MOVE", "DROP"}:
                raise PackageSerializationError("Invalid package action.")
            if action == "MOVE" and parts.get("TARGET") not in _SLOTS:
                raise PackageSerializationError("Invalid package slot.")
            continue
        raise PackageSerializationError("Unsupported package step.")

    payload = f"RESULT|PACKAGE|{animation_run_id}|" + ">".join(steps)
    if len(payload) > 1200:
        raise PackageSerializationError("Package payload exceeds 1200 characters.")
    return payload
