"""Fault-tolerant registry for all active question modules."""

from __future__ import annotations

from collections import OrderedDict
from importlib import import_module
from typing import Any

from app.questions.base import QuestionDefinition

_MODULES = (
    "app.questions.easy.traffic_light",
    "app.questions.easy.parking_single",
    "app.questions.medium.parking_loop",
    "app.questions.medium.package_sort",
    "app.questions.medium.parking_session_total",
    "app.questions.medium.package_data_analysis",
    "app.questions.hard.river_bfs",
    "app.questions.hard.river_recursion",
    "app.questions.hard.rescue_path_check",
    "app.questions.hard.rescue_bfs",
    "app.questions.extreme.rescue_rl",
    "app.questions.extreme.rescue_best_route",
)

def load_registry(module_names: tuple[str, ...]) -> tuple["OrderedDict[str, QuestionDefinition]", dict[str, str]]:
    questions: "OrderedDict[str, QuestionDefinition]" = OrderedDict()
    errors: dict[str, str] = {}
    for module_name in module_names:
        try:
            module = import_module(module_name)
            question = getattr(module, "QUESTION")
            if not isinstance(question, QuestionDefinition):
                raise TypeError("QUESTION is not a QuestionDefinition")
            if question.code in questions:
                raise ValueError(f"duplicate question code {question.code}")
            if question.lifecycle_status not in {"FINAL", "LEGACY", "DEPRECATED", "BLOCKED"}:
                raise ValueError(f"invalid lifecycle_status {question.lifecycle_status}")
            if question.active:
                questions[question.code] = question
        except Exception as exc:  # one broken module must not crash the server
            errors[module_name] = f"{type(exc).__name__}: {exc}"
    return questions, errors


QUESTIONS, QUESTION_LOAD_ERRORS = load_registry(_MODULES)

QUESTION_CODE_ALIASES: dict[str, str] = {
    "PARKING_SESSION_TOTAL": "M03_PARKING_SESSION_TOTAL",
    "PACKAGE_DATA_ANALYSIS": "M04_PACKAGE_DATA_ANALYSIS",
    "H01_RIVER_RECURSION": "H02_RIVER_RECURSION",
    "H01_RESCUE_PATH_CHECK": "H03_RESCUE_PATH_CHECK",
    "H02_RESCUE_BFS": "H04_RESCUE_BFS",
}

REPLACEMENT_STATUS_ALIASES: dict[str, str] = {
    "REPLACED_BY_H01_RESCUE_PATH_CHECK": "REPLACED_BY_H03_RESCUE_PATH_CHECK",
}


def canonical_question_code(code: str) -> str:
    """Resolve one legacy code to its canonical registry code."""

    normalized = str(code or "").strip()
    return QUESTION_CODE_ALIASES.get(normalized, normalized)


def canonical_replacement_status(value: str | None) -> str | None:
    if value is None:
        return None
    return REPLACEMENT_STATUS_ALIASES.get(value, value)


LEVEL_ORDER = ("EASY", "MEDIUM", "HARD", "EXTREME")
LEVEL_DESCRIPTIONS = {
    "EASY": "Basic input, output, numbers, and decisions.",
    "MEDIUM": "Loops, lists, functions, and multi-step problems.",
    "HARD": "Search, recursion, BFS, and complex state problems.",
    "EXTREME": "Advanced challenges that combine several coding skills.",
}


def get_question(code: str) -> QuestionDefinition:
    canonical = canonical_question_code(code)
    try:
        return QUESTIONS[canonical]
    except KeyError as exc:
        raise KeyError(f"Question code not registered: {code}") from exc


def questions_for_level(level: str) -> list[QuestionDefinition]:
    normalized = level.upper()
    return [question for question in QUESTIONS.values() if question.level == normalized]


def registry_status() -> dict[str, Any]:
    active = list(QUESTIONS.values())
    final_count = sum(question.lifecycle_status == "FINAL" for question in active)
    legacy_count = sum(question.lifecycle_status == "LEGACY" for question in active)
    blocked_count = sum(
        question.lifecycle_status == "BLOCKED" or (question.replacement_status or "").startswith("BLOCKED")
        for question in active
    )
    active_extreme = sum(question.level == "EXTREME" for question in active)
    final_extreme = sum(question.level == "EXTREME" and question.lifecycle_status == "FINAL" for question in active)
    return {
        "active_count": len(active),
        "active_question_count": len(active),
        "active_codes": [question.code for question in active],
        "final_contract_count": final_count,
        "legacy_active_count": legacy_count,
        "blocked_question_count": blocked_count,
        "active_extreme_count": active_extreme,
        "final_extreme_count": final_extreme,
        "legacy_extreme_count": sum(question.level == "EXTREME" and question.lifecycle_status == "LEGACY" for question in active),
        "has_active_legacy_extreme": any(question.level == "EXTREME" and question.lifecycle_status == "LEGACY" for question in active),
        "has_final_extreme_question": final_extreme > 0,
        "questions": [
            {
                "question_code": question.code,
                "semantic_code": question.semantic_code,
                "title": question.title,
                "scene": question.scene_code,
                "difficulty": question.level,
                "lifecycle_status": question.lifecycle_status,
                "replacement_status": question.replacement_status,
                "contract_version": question.contract_version,
                "source_document": question.source_document,
                "active": question.active,
            }
            for question in active
        ],
        "load_errors": QUESTION_LOAD_ERRORS,
        "rescue_soal_2_status": "FINAL",
        "rescue_soal_3_status": "FINAL",
    }
