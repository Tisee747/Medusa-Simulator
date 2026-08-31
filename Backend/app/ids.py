"""Qualified globally unique identifiers used by the backend."""

from __future__ import annotations

import uuid


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex.upper()}"


def new_attempt_id(question_code: str) -> str:
    stem = question_code.split("_", 1)[0][:8]
    return f"{stem}-{uuid.uuid4().hex[:24].upper()}"


def new_execution_id() -> str:
    return _id("EXE")


def new_animation_run_id() -> str:
    return _id("ANM")
