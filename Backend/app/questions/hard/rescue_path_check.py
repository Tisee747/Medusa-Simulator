"""Rescue Soal 1 final: validate robot paths on Rescue Maze V1."""

from __future__ import annotations

from typing import Any

from app.evaluators.rescue_path import evaluate_rescue_path, simulate_expected
from app.questions.base import EvaluationResult, QuestionDefinition

MAZE_VERSION = "RESCUE_MAZE_V1"
MAZE_CHECKSUM_SHA256 = "20eaad27c6c5512374d40b976471cb2cb4e939f3dbaf96644b613c98c93964a7"
CANONICAL_WALLS = [[0, 2], [1, 2], [2, 0], [2, 4], [3, 1], [3, 2]]
OPEN_CELLS = [
    [0, 1], [0, 3], [0, 4], [1, 0], [1, 1], [1, 3], [1, 4],
    [2, 1], [2, 2], [2, 3], [3, 0], [3, 3], [3, 4],
    [4, 0], [4, 1], [4, 2], [4, 3],
]
CANONICAL_STEPS = ["DOWN", "RIGHT", "DOWN", "RIGHT", "RIGHT", "DOWN", "DOWN", "RIGHT"]

STARTER_CODE = '''def periksa_jalur(start, target, walls, langkah):
    posisi = [start[0], start[1]]
    visited_path = [[posisi[0], posisi[1]]]

    # Ikuti setiap arah satu per satu.
    # Sebelum bergerak, periksa batas papan dan posisi dinding.
    # Berhenti saat keluar papan, menabrak dinding, atau mencapai target.

    return {
        "status": "BELUM_SAMPAI",
        "visited_path": visited_path,
    }
'''


def _case(
    test_id: str,
    name: str,
    visibility: str,
    start: list[int],
    target: list[int],
    walls: list[list[int]],
    steps: list[str],
    *,
    animation_case_id: str | None = None,
    maze_version: str | None = None,
) -> dict[str, Any]:
    return {
        "test_id": test_id,
        "name": name,
        "test_visibility": visibility,
        "animation_case_id": animation_case_id,
        "maze_version": maze_version,
        "start": list(start),
        "target": list(target),
        "walls": [list(item) for item in walls],
        "steps": list(steps),
    }


def create_attempt_data() -> dict[str, Any]:
    cases = [
        _case(
            "VISIBLE-1", "Robot mencapai target", "CANONICAL",
            [0, 0], [4, 4], CANONICAL_WALLS, CANONICAL_STEPS,
            animation_case_id="canonical", maze_version=MAZE_VERSION,
        ),
        _case(
            "VISIBLE-2", "Robot mencoba masuk ke dinding", "VISIBLE",
            [0, 0], [4, 4], CANONICAL_WALLS, ["RIGHT", "RIGHT", "DOWN"],
            animation_case_id="VISIBLE-2", maze_version=MAZE_VERSION,
        ),
        _case(
            "VISIBLE-3", "Robot mencoba keluar dari papan", "VISIBLE",
            [0, 0], [4, 4], CANONICAL_WALLS, ["UP", "RIGHT"],
            animation_case_id="VISIBLE-3", maze_version=MAZE_VERSION,
        ),
        _case(
            "VISIBLE-4", "Robot berhenti sebelum target", "VISIBLE",
            [0, 0], [4, 4], CANONICAL_WALLS, ["RIGHT"],
            animation_case_id="VISIBLE-4", maze_version=MAZE_VERSION,
        ),
        # Hidden cases are deterministic, valid 5x5 inputs, and never animation candidates.
        _case("HIDDEN-START-DIFFERENT", "Start berbeda", "HIDDEN", [4, 0], [4, 4], [], ["RIGHT", "RIGHT", "RIGHT", "RIGHT"]),
        _case("HIDDEN-TARGET-DIFFERENT", "Target berbeda", "HIDDEN", [0, 0], [1, 1], [], ["RIGHT", "DOWN", "RIGHT"]),
        _case("HIDDEN-WALLS-DIFFERENT", "Walls berbeda", "HIDDEN", [0, 0], [2, 2], [[1, 0]], ["DOWN", "RIGHT", "DOWN"]),
        _case("HIDDEN-SAME", "Start sama target", "HIDDEN", [2, 2], [2, 2], [[0, 0]], ["UP", "LEFT"]),
        _case("HIDDEN-REVISIT", "Kembali ke sel lama", "HIDDEN", [1, 1], [1, 3], [], ["RIGHT", "LEFT", "RIGHT", "RIGHT"]),
        _case("HIDDEN-EARLY-GOAL", "Target tercapai sebelum input habis", "HIDDEN", [0, 0], [0, 1], [], ["RIGHT", "DOWN", "LEFT"]),
        _case("HIDDEN-LATE-WALL", "Collision setelah langkah legal", "HIDDEN", [4, 0], [0, 4], [[4, 3]], ["RIGHT", "RIGHT", "RIGHT", "UP"]),
        _case("HIDDEN-LATE-OUT", "Keluar grid setelah langkah legal", "HIDDEN", [2, 2], [4, 4], [], ["UP", "UP", "UP", "RIGHT"]),
        _case("HIDDEN-INCOMPLETE", "Legal tetapi belum sampai", "HIDDEN", [4, 0], [0, 4], [], ["RIGHT", "RIGHT"]),
        _case(
            "HIDDEN-MAX-20", "Maksimal dua puluh langkah", "HIDDEN",
            [2, 2], [4, 4], [],
            ["LEFT", "RIGHT"] * 10,
        ),
    ]
    return {
        "cases": cases,
        "final_animation_case_id": "VISIBLE-1",
        "maze_version": MAZE_VERSION,
        "maze_checksum_sha256": MAZE_CHECKSUM_SHA256,
    }


def visible_cases(data: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for case in data["cases"]:
        if case["test_visibility"] == "HIDDEN":
            continue
        expected = simulate_expected(case["start"], case["target"], case["walls"], case["steps"])
        result.append({
            "test_id": case["test_id"],
            "name": case["name"],
            "input": {
                "start": case["start"],
                "target": case["target"],
                "walls": case["walls"],
                "langkah": case["steps"],
            },
            "expected": {
                "status": expected["status"],
                "visited_path": expected["visited_path"],
            },
            "visible": True,
        })
    return result


def evaluate(source_code: str, data: dict[str, Any]) -> EvaluationResult:
    return evaluate_rescue_path(source_code, data)


QUESTION = QuestionDefinition(
    code="H03_RESCUE_PATH_CHECK",
    semantic_code="rescue.path_validation",
    level="HARD",
    title='Periksa Jalur Robot Penyelamat',
    scene_code="RESCUE",
    summary='Robot penyelamat menerima daftar arah untuk bergerak pada papan kotak-kotak berukuran 5 × 5. Buatlah fungsi yang mengikuti arah tersebut satu per satu, mencatat posisi yang berhasil ditempati, dan menentukan hasil akhir perjalanan robot.',
    learning_objectives=(
    'Buat fungsi periksa_jalur(start, target, walls, langkah).',
    'Periksa setiap arah secara berurutan dan hentikan perjalanan ketika robot keluar dari papan, menabrak dinding, atau mencapai target.',
    'Kembalikan status perjalanan serta daftar posisi yang benar-benar berhasil ditempati robot.',
),
    input_format=(
    'start adalah posisi awal robot dalam bentuk [baris, kolom].',
    'target adalah posisi tujuan yang harus dicapai robot.',
    'walls adalah daftar posisi dinding yang tidak boleh dimasuki.',
    'langkah adalah list arah UP, DOWN, LEFT, atau RIGHT yang harus diikuti secara berurutan.',
),
    output_format=(
    'Kembalikan dictionary dengan key status dan visited_path.',
    'status berisi BERHASIL, MENABRAK_DINDING, KELUAR_GRID, atau BELUM_SAMPAI.',
    'visited_path harus dimulai dari start dan hanya berisi posisi yang benar-benar berhasil ditempati robot.',
),
    starter_code=STARTER_CODE,
    create_attempt_data=create_attempt_data,
    visible_cases=visible_cases,
    evaluate=evaluate,
    question_type="FREE",
    required_function="periksa_jalur",
    required_technique=None,
    evaluation_adapter="RESCUE_PATH_CHECK",
    animation_adapter="RESCUE_PATH_CHECK",
    max_score=100.0,
    active=True,
    version=4,
    lifecycle_status="FINAL",
    contract_version="FINAL-2026-08-01",
    source_document="RESCUE_SOAL_1_KONTRAK_FINAL_BACKEND_READY.docx",
    metadata={
        "maze": {
            "maze_version": MAZE_VERSION,
            "maze_checksum_sha256": MAZE_CHECKSUM_SHA256,
            "maze_status": "FINAL_VERIFIED_WITH_PARTIAL_VISUAL_EVIDENCE",
            "visual_evidence_complete": False,
            "logical_and_text_verification_complete": True,
            "grid": {"rows": 5, "columns": 5},
            "start": [0, 0],
            "target": [4, 4],
            "walls": CANONICAL_WALLS,
            "open_cells": OPEN_CELLS,
            "movement_mapping": {
                "UP": [-1, 0], "DOWN": [1, 0], "LEFT": [0, -1], "RIGHT": [0, 1],
            },
            "shortest_path": {"length": 8, "moves": CANONICAL_STEPS},
        },
        "rescue_soal_2_status": "NOT_STARTED_WAITING_FOR_APPROVAL",
        "lsl_change_required": False,
        "firestorm_object_change_required": False,
    },
)
