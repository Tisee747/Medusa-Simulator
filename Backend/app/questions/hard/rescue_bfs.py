"""Rescue Soal 2 final: shortest path with real BFS."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.evaluators.rescue_routes import evaluate_rescue_bfs, shortest_path
from app.questions.base import EvaluationResult, QuestionDefinition
from app.questions.hard.rescue_path_check import CANONICAL_WALLS, MAZE_CHECKSUM_SHA256, MAZE_VERSION

STARTER_CODE = '''from collections import deque


def cari_jalur(start, target, walls):
    # Gunakan antrean (queue) untuk mencoba posisi yang paling dekat lebih dulu.
    # Simpan posisi yang sudah diperiksa agar tidak diulang.
    # Return None jika target tidak dapat dicapai.
    pass
'''


def _case(test_id: str, name: str, visibility: str, start: list[int], target: list[int], walls: list[list[int]]) -> dict[str, Any]:
    return {
        "test_id": test_id,
        "name": name,
        "test_visibility": visibility,
        "start": list(start),
        "target": list(target),
        "walls": [list(item) for item in walls],
    }


def create_attempt_data() -> dict[str, Any]:
    cases = [
        _case("VISIBLE-1", "Temukan rute terpendek pada papan utama", "CANONICAL", [0, 0], [4, 4], CANONICAL_WALLS),
        _case("VISIBLE-2", "Jalur lurus tanpa dinding", "VISIBLE", [0, 0], [0, 4], []),
        _case("VISIBLE-3", "Robot harus memutar menghindari dinding", "VISIBLE", [0, 0], [2, 2], [[0, 1], [1, 1]]),
        _case("VISIBLE-4", "Robot sudah berada di target", "VISIBLE", [2, 2], [2, 2], [[0, 0]]),
        _case("VISIBLE-5", "Target tertutup dan tidak dapat dicapai", "VISIBLE", [0, 0], [0, 2], [[0, 1], [1, 0], [1, 1], [1, 2]]),
        _case("HIDDEN-1", "Start berbeda", "HIDDEN", [4, 0], [0, 4], [[3, 1], [2, 1], [1, 3]]),
        _case("HIDDEN-2", "Target berbeda", "HIDDEN", [0, 4], [4, 0], [[1, 4], [2, 2], [3, 0]]),
        _case("HIDDEN-3", "Koridor sempit", "HIDDEN", [0, 0], [4, 4], [[0, 1], [1, 1], [2, 1], [3, 1]]),
        _case("HIDDEN-4", "Dua jalur sama pendek", "HIDDEN", [1, 1], [3, 3], [[2, 2]]),
        _case("HIDDEN-5", "Tidak terjangkau tertutup", "HIDDEN", [4, 4], [0, 0], [[3, 4], [4, 3]]),
        _case("HIDDEN-6", "Tanpa dinding", "HIDDEN", [3, 0], [0, 3], []),
    ]
    return {
        "cases": cases,
        "final_animation_case_id": "VISIBLE-1",
        "maze_version": MAZE_VERSION,
        "maze_checksum_sha256": MAZE_CHECKSUM_SHA256,
        "unreachable_output": None,
    }


def visible_cases(data: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for case in data["cases"]:
        if case["test_visibility"] == "HIDDEN":
            continue
        reference = shortest_path(case["start"], case["target"], case["walls"])
        result.append({
            "test_id": case["test_id"],
            "name": case["name"],
            "input": {"start": case["start"], "target": case["target"], "walls": case["walls"]},
            "expected": None if reference is None else f"List arah terpendek ({len(reference)} langkah)",
            "visible": True,
        })
    return result


def evaluate(source_code: str, data: dict[str, Any]) -> EvaluationResult:
    return evaluate_rescue_bfs(source_code, data)


QUESTION = QuestionDefinition(
    code="H04_RESCUE_BFS",
    semantic_code="rescue.shortest_path_bfs",
    level="HARD",
    title='Cari Jalur Terpendek Robot Penyelamat',
    scene_code="RESCUE",
    summary='Robot penyelamat harus bergerak dari posisi awal menuju target tanpa keluar dari papan atau menabrak dinding. Buatlah fungsi yang mencari rute aman dengan jumlah langkah paling sedikit menggunakan Breadth-First Search atau BFS.',
    learning_objectives=(
    'Buat fungsi cari_jalur(start, target, walls).',
    'Gunakan antrean untuk menyimpan posisi yang akan diperiksa. BFS memeriksa posisi yang paling dekat terlebih dahulu.',
    'Catat posisi yang sudah pernah diperiksa agar posisi yang sama tidak dimasukkan ke antrean berulang kali.',
    'Kembalikan urutan arah pada rute aman yang paling pendek.',
),
    input_format=(
    'start adalah posisi awal robot dan target adalah posisi tujuan, keduanya ditulis sebagai [baris, kolom].',
    'walls adalah daftar posisi dinding pada papan berukuran 5 × 5.',
    'Robot hanya dapat bergerak dengan arah UP, DOWN, LEFT, dan RIGHT.',
),
    output_format=(
    'Kembalikan list arah pada rute terpendek, misalnya ["RIGHT", "DOWN"].',
    'Jika target tidak dapat dicapai, kembalikan None.',
    'Jika posisi awal sudah sama dengan target, kembalikan [].',
),
    starter_code=STARTER_CODE,
    create_attempt_data=create_attempt_data,
    visible_cases=visible_cases,
    evaluate=evaluate,
    question_type="REQUIRED_TECHNIQUE",
    required_function="cari_jalur",
    required_technique="BFS",
    evaluation_adapter="RESCUE_BFS",
    animation_adapter="RESCUE_BFS",
    max_score=100.0,
    active=True,
    version=4,
    lifecycle_status="FINAL",
    contract_version="FINAL-2026-08-02",
    source_document="Backend final Rescue Soal 2",
    metadata={
        "grid": {"rows": 5, "columns": 5},
        "movement_tokens": ["UP", "DOWN", "LEFT", "RIGHT"],
        "unreachable_output": None,
        "maze_version": MAZE_VERSION,
        "maze_checksum_sha256": MAZE_CHECKSUM_SHA256,
    },
)
