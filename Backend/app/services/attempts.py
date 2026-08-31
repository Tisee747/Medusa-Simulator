"""Attempt orchestration: evaluate, persist executions, update progress, and score."""

from __future__ import annotations

import threading
from dataclasses import fields
from typing import Any

from app.database import get_attempt, persist_evaluation, prepare_submission_attempt
from app.evaluators.technique import evaluate_technique
from app.ids import new_execution_id
from app.questions.base import EvaluationResult, TechniqueResult
from app.questions.registry import get_question
from app.services.scoring import apply_student_score

_LOCKS_GUARD = threading.Lock()
_ATTEMPT_LOCKS: dict[str, threading.Lock] = {}


def _lock_for(key: str) -> threading.Lock:
    with _LOCKS_GUARD:
        return _ATTEMPT_LOCKS.setdefault(key, threading.Lock())



def check_attempt(requested_attempt_id: str, source_code: str) -> EvaluationResult:
    """Evaluate the current draft without persisting attempts, score, or progress."""

    attempt = get_attempt(requested_attempt_id)
    if not attempt:
        raise KeyError(requested_attempt_id)
    question = get_question(attempt["question_code"])
    result = question.evaluate(source_code, attempt["input_data"])
    _enrich_result(question, result)
    apply_source_technique(question, result, source_code)
    apply_student_score(question, result)
    return result

def evaluate_attempt(
    requested_attempt_id: str,
    source_code: str,
    submission_id: str | None = None,
) -> tuple[dict[str, Any], EvaluationResult]:
    """Evaluate one submission and make duplicate client requests idempotent.

    A repeated ``submission_id`` returns the already-persisted result. Different
    submission IDs remain distinct retries and receive distinct attempts.
    Database uniqueness is the cross-process guard; the in-process lock avoids
    wasting a second evaluation when duplicate HTTP requests arrive together.
    """

    lock_key = submission_id or requested_attempt_id
    with _lock_for(lock_key):
        attempt = prepare_submission_attempt(requested_attempt_id, submission_id)
        if attempt.get("completed_at") is not None:
            return attempt, _result_from_stored_attempt(attempt)

        question = get_question(attempt["question_code"])
        result = question.evaluate(source_code, attempt["input_data"])
        _enrich_result(question, result)
        apply_source_technique(question, result, source_code)
        apply_student_score(question, result)
        stored = persist_evaluation(attempt["attempt_id"], source_code, result)
        # Another process may have committed the same submission first. Always
        # return the canonical persisted result rather than the losing local run.
        persisted = get_attempt(stored["attempt_id"]) or stored
        return persisted, _result_from_stored_attempt(persisted)


def _result_from_stored_attempt(attempt: dict[str, Any]) -> EvaluationResult:
    raw = attempt.get("evaluation_data") or {}
    if not isinstance(raw, dict) or not raw:
        raise RuntimeError(
            f"Attempt {attempt.get('attempt_id')} sudah selesai tetapi evaluation_data tidak tersedia."
        )

    allowed = {item.name for item in fields(EvaluationResult)}
    payload = {key: value for key, value in raw.items() if key in allowed}
    technique = payload.get("technique_result") or {}
    if isinstance(technique, TechniqueResult):
        technique_result = technique
    else:
        technique_result = TechniqueResult(
            required_technique=technique.get("required_technique"),
            passed=bool(technique.get("passed", True)),
            checks=dict(technique.get("checks") or {}),
        )
    payload["technique_result"] = technique_result
    return EvaluationResult(**payload)


def _enrich_result(question: Any, result: EvaluationResult) -> None:
    if not result.executions:
        _build_legacy_executions(result)
    if question.evaluation_adapter != "M03_PARKING_SESSION_TOTAL":
        result.technique_result = evaluate_technique(
            "" if result.status == "ERROR" else _source_from_result(result),
            question.required_technique,
            question.required_function,
        )
        # _source_from_result is replaced by caller below when a technique exists.
    if not result.case_results:
        result.case_results = [
            {
                "test_id": item["test_id"],
                "execution_id": item["execution_id"],
                "case_behavior_correct": bool(item.get("case_behavior_correct")),
            }
            for item in result.executions
            if item.get("test_visibility") in {"VISIBLE", "CANONICAL", "HIDDEN"}
        ]
    if int((result.hidden_summary or {}).get("total", 0) or 0) > 0:
        result.behavior_correct = result.status == "CORRECT"
    elif result.case_results:
        result.behavior_correct = all(item["case_behavior_correct"] for item in result.case_results)
    else:
        result.behavior_correct = result.status == "CORRECT"
    result.overall_correct = result.behavior_correct and result.technique_result.passed
    if result.overall_correct:
        result.status = "CORRECT"
    elif result.status == "CORRECT":
        result.status = "WRONG"
        result.message = "Behavior benar, tetapi teknik wajib belum terpenuhi."
        result.error_message = "Teknik wajib tidak digunakan sesuai ketentuan soal."


def apply_source_technique(question: Any, result: EvaluationResult, source_code: str) -> None:
    if question.evaluation_adapter == "M03_PARKING_SESSION_TOTAL":
        return
    result.technique_result = evaluate_technique(
        source_code,
        question.required_technique,
        question.required_function,
    )
    result.overall_correct = result.behavior_correct and result.technique_result.passed
    if result.overall_correct:
        result.status = "CORRECT"
    elif result.status == "CORRECT":
        result.status = "WRONG"
        result.message = "Behavior benar, tetapi teknik wajib belum terpenuhi."
        result.error_message = "Teknik wajib tidak digunakan sesuai ketentuan soal."


def _source_from_result(result: EvaluationResult) -> str:
    return ""


def _build_legacy_executions(result: EvaluationResult) -> None:
    executions = []
    normalized_cases = []
    for index, item in enumerate(result.visible_results, 1):
        execution_id = new_execution_id()
        test_id = str(item.get("test_id") or f"VISIBLE-{index}")
        passed = bool(item.get("passed"))
        normalized = {
            "animation_case_id": test_id,
            "execution_id": execution_id,
            "test_id": test_id,
            "test_visibility": "VISIBLE",
            "actual_raw": str(item.get("actual", "")),
            "actual": str(item.get("actual", "")),
            "expected": str(item.get("expected", "")),
            "case_behavior_correct": passed,
            "input_data": {"input": item.get("input", "")},
        }
        normalized_cases.append(normalized)
        executions.append(
            {
                "execution_id": execution_id,
                "test_id": test_id,
                "test_visibility": "VISIBLE",
                "status": "COMPLETED" if not item.get("error") else "RUNTIME_ERROR",
                "stdout_raw": result.stdout,
                "stderr_raw": result.stderr,
                "return_value_serialized": None,
                "case_behavior_correct": passed,
                "duration_ms": None,
                "error_type": "RUNTIME_ERROR" if item.get("error") else None,
                "error_detail": item.get("error") or None,
                "feedback": item,
                "normalized_result": normalized,
                "evaluation_result": {"passed": passed},
            }
        )
    if not executions:
        execution_id = new_execution_id()
        passed = result.status == "CORRECT"
        normalized = {
            "animation_case_id": "VISIBLE-1",
            "execution_id": execution_id,
            "test_id": "VISIBLE-1",
            "test_visibility": "VISIBLE",
            "actual_raw": result.program_output,
            "actual": result.program_output,
            "expected": "",
            "case_behavior_correct": passed,
            "input_data": {},
        }
        normalized_cases.append(normalized)
        executions.append(
            {
                "execution_id": execution_id,
                "test_id": "VISIBLE-1",
                "test_visibility": "VISIBLE",
                "status": "COMPLETED" if passed else "RUNTIME_ERROR",
                "stdout_raw": result.stdout,
                "stderr_raw": result.stderr,
                "return_value_serialized": None,
                "case_behavior_correct": passed,
                "duration_ms": None,
                "error_type": None if passed else "EVALUATION_FAILED",
                "error_detail": result.error_message or None,
                "feedback": {},
                "normalized_result": normalized,
                "evaluation_result": {"passed": passed},
            }
        )
    result.executions = executions
    result.normalized_cases = normalized_cases
