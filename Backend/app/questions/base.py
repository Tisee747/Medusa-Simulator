"""Shared question contracts and serializable evaluation structures."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from app.code_runner import normalize_output, run_source
from app.ids import new_execution_id


@dataclass(slots=True)
class TechniqueResult:
    required_technique: str | None = None
    passed: bool = True
    checks: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EvaluationResult:
    """Result returned by question evaluators and persisted by the service layer."""

    status: str
    score: float
    message: str
    functional_score: float = 0.0
    score_breakdown: list[dict[str, Any]] = field(default_factory=list)
    program_output: str = ""
    error_message: str = ""
    stdout: str = ""
    stderr: str = ""
    visible_results: list[dict[str, Any]] = field(default_factory=list)
    hidden_summary: dict[str, Any] = field(default_factory=dict)
    animation: dict[str, Any] = field(default_factory=dict)
    executions: list[dict[str, Any]] = field(default_factory=list)
    case_results: list[dict[str, Any]] = field(default_factory=list)
    normalized_cases: list[dict[str, Any]] = field(default_factory=list)
    behavior_correct: bool = False
    technique_result: TechniqueResult = field(default_factory=TechniqueResult)
    overall_correct: bool = False

    def finalize(self) -> "EvaluationResult":
        if not self.case_results and self.executions:
            self.case_results = [
                {
                    "test_id": item["test_id"],
                    "execution_id": item["execution_id"],
                    "case_behavior_correct": bool(item.get("case_behavior_correct")),
                }
                for item in self.executions
                if item.get("test_visibility") == "VISIBLE"
            ]
        if self.case_results:
            self.behavior_correct = all(
                bool(item.get("case_behavior_correct")) for item in self.case_results
            )
        self.overall_correct = self.behavior_correct and self.technique_result.passed
        if self.overall_correct:
            self.status = "CORRECT"
        elif self.status == "CORRECT":
            self.status = "WRONG"
        return self

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


@dataclass(frozen=True, slots=True)
class QuestionDefinition:
    """Metadata and callbacks used by editor, evaluator, persistence, and animation."""

    code: str
    level: str
    title: str
    scene_code: str
    summary: str
    learning_objectives: tuple[str, ...]
    input_format: tuple[str, ...]
    output_format: tuple[str, ...]
    starter_code: str
    create_attempt_data: Callable[[], dict[str, Any]]
    visible_cases: Callable[[dict[str, Any]], list[dict[str, Any]]]
    evaluate: Callable[[str, dict[str, Any]], EvaluationResult]
    question_type: str = "FREE"
    required_technique: str | None = None
    evaluation_adapter: str = "LEGACY"
    animation_adapter: str | None = None
    max_score: float = 100.0
    active: bool = True
    version: int = 1
    semantic_code: str | None = None
    required_function: str | None = None
    lifecycle_status: str = "LEGACY"
    replacement_status: str | None = None
    contract_version: str | None = None
    source_document: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _execution_status(run: Any) -> str:
    if run.validation_error:
        if run.validation_error.startswith("SyntaxError"):
            return "SYNTAX_ERROR"
        return "RUNTIME_ERROR"
    if run.timed_out:
        return "TIMEOUT"
    return "COMPLETED" if run.ok else "RUNTIME_ERROR"


def evaluate_standard_cases(
    source_code: str,
    cases: list[dict[str, Any]],
    *,
    animation_from_case: int = 0,
    timeout_seconds: float | None = None,
) -> EvaluationResult:
    """Execute each case once and retain immutable execution-level evidence."""

    results: list[dict[str, Any]] = []
    executions: list[dict[str, Any]] = []
    normalized_cases: list[dict[str, Any]] = []
    combined_stdout: list[str] = []
    combined_stderr: list[str] = []
    first_output = ""

    for index, case in enumerate(cases):
        execution_id = new_execution_id()
        run = run_source(
            source_code,
            stdin_text=case["input"],
            timeout_seconds=timeout_seconds,
        )
        actual = normalize_output(run.stdout)
        expected = normalize_output(str(case["expected"]))
        passed = run.ok and actual == expected
        test_id = str(case.get("test_id") or f"TEST-{index + 1}")
        visibility = "VISIBLE" if bool(case.get("visible", True)) else "HIDDEN"

        if index == animation_from_case:
            first_output = actual

        if run.validation_error:
            error = run.validation_error
        elif run.timed_out:
            error = "Program melewati batas waktu. Periksa kemungkinan loop tanpa akhir."
        elif not run.ok:
            error = normalize_output(run.stderr) or "Program berhenti dengan error."
        else:
            error = ""

        visible_result = {
            "test_id": test_id,
            "name": case.get("name", f"Test {index + 1}"),
            "input": case["input"].rstrip(),
            "expected": expected,
            "actual": actual,
            "passed": passed,
            "error": error,
            "visible": visibility == "VISIBLE",
            "execution_id": execution_id,
        }
        results.append(visible_result)
        normalized = {
            "animation_case_id": str(case.get("animation_case_id") or test_id),
            "execution_id": execution_id,
            "test_id": test_id,
            "test_visibility": visibility,
            "actual_raw": run.stdout,
            "actual": actual,
            "expected": expected,
            "case_behavior_correct": passed,
            "input_data": case.get("input_data", {}),
        }
        normalized_cases.append(normalized)
        executions.append(
            {
                "execution_id": execution_id,
                "test_id": test_id,
                "test_visibility": visibility,
                "status": _execution_status(run),
                "stdout_raw": run.stdout,
                "stderr_raw": run.stderr,
                "return_value_serialized": None,
                "case_behavior_correct": passed if run.ok else False,
                "duration_ms": run.duration_ms,
                "error_type": _execution_status(run) if not run.ok else None,
                "error_detail": error or None,
                "feedback": visible_result,
                "normalized_result": normalized,
                "evaluation_result": {
                    "expected": expected,
                    "actual": actual,
                    "passed": passed,
                },
            }
        )
        combined_stdout.append(run.stdout)
        combined_stderr.append(run.stderr)

    visible = [item for item in results if item["visible"]]
    hidden = [item for item in results if not item["visible"]]
    all_passed = len(results) == len(cases) and all(item["passed"] for item in results)
    passed_count = sum(1 for item in results if item["passed"])
    score = round(100.0 * passed_count / max(1, len(cases)), 1)

    first_error = next((item["error"] for item in results if item["error"]), "")
    status = "CORRECT" if all_passed else ("ERROR" if first_error else "WRONG")
    message = (
        "Semua test case berhasil."
        if all_passed
        else f"{passed_count} dari {len(cases)} test case berhasil."
    )

    return EvaluationResult(
        status=status,
        score=score,
        message=message,
        program_output=first_output,
        error_message=first_error,
        stdout="\n---\n".join(combined_stdout),
        stderr="\n---\n".join(combined_stderr),
        visible_results=visible,
        hidden_summary={
            "total": len(hidden),
            "passed": sum(1 for item in hidden if item["passed"]),
        },
        executions=executions,
        normalized_cases=normalized_cases,
        case_results=[
            {
                "test_id": item["test_id"],
                "execution_id": item["execution_id"],
                "case_behavior_correct": item["passed"],
            }
            for item in visible
        ],
        behavior_correct=all_passed,
        overall_correct=all_passed,
    )
