"""Rescue Soal 3 final: select the best valid candidate route."""

from __future__ import annotations

from typing import Any

from app.evaluators.rescue_routes import evaluate_rescue_best_route, expected_best_candidate
from app.questions.base import EvaluationResult, QuestionDefinition
from app.questions.hard.rescue_path_check import CANONICAL_WALLS, MAZE_CHECKSUM_SHA256, MAZE_VERSION

STARTER_CODE = '''def pilih_jalur_terbaik(start, target, walls, candidates):
    # Periksa semua pilihan rute tanpa mengubah isi candidates.
    # Pilih rute aman dengan jumlah langkah paling sedikit.
    # Jika sama pendek, pilih rute yang muncul lebih dulu.
    return {
        "selected_index": None,
        "selected_path": [],
        "step_count": None,
    }
'''


def _case(test_id: str, name: str, visibility: str, start: list[int], target: list[int], walls: list[list[int]], candidates: list[Any]) -> dict[str, Any]:
    return {
        "test_id": test_id,
        "name": name,
        "test_visibility": visibility,
        "start": list(start),
        "target": list(target),
        "walls": [list(item) for item in walls],
        "candidates": candidates,
    }


def create_attempt_data() -> dict[str, Any]:
    cases = [
        _case("VISIBLE-1", "Cari satu-satunya rute yang aman", "CANONICAL", [0, 0], [1, 1], [], [
            ["RIGHT", "DOWN"], ["LEFT"], ["DOWN", "DOWN"],
        ]),
        _case("VISIBLE-2", "Pilih rute yang paling pendek", "VISIBLE", [0, 0], [2, 2], [], [
            ["RIGHT", "DOWN", "LEFT", "DOWN", "RIGHT", "RIGHT"],
            ["DOWN", "DOWN", "RIGHT", "RIGHT"],
            ["RIGHT", "RIGHT", "DOWN", "DOWN"],
        ]),
        _case("VISIBLE-3", "Kalau sama pendek, pilih yang muncul lebih dulu", "VISIBLE", [1, 1], [2, 2], [], [
            ["RIGHT", "DOWN"], ["DOWN", "RIGHT"], ["UP"],
        ]),
        _case("VISIBLE-4", "Tidak ada rute yang bisa dipakai", "VISIBLE", [0, 0], [0, 2], [[0, 1]], [
            ["RIGHT", "RIGHT"], ["UP"], ["DOWN"],
        ]),
        _case("VISIBLE-5", "Robot sudah berada di target", "VISIBLE", [2, 2], [2, 2], [], [
            [], ["RIGHT", "LEFT"], ["UP"],
        ]),
        _case("HIDDEN-1", "Menabrak dinding", "HIDDEN", [0, 0], [2, 0], [[1, 0]], [["DOWN"], ["RIGHT", "DOWN", "DOWN", "LEFT"]]),
        _case("HIDDEN-2", "Keluar grid", "HIDDEN", [0, 0], [0, 1], [], [["UP"], ["RIGHT"]]),
        _case("HIDDEN-3", "Target terlalu awal", "HIDDEN", [0, 0], [0, 1], [], [["RIGHT", "DOWN"], ["DOWN", "RIGHT", "UP"]]),
        _case("HIDDEN-4", "Token tidak dikenal", "HIDDEN", [0, 0], [1, 0], [], [["MAJU"], ["DOWN"]]),
        _case("HIDDEN-5", "Candidates kosong", "HIDDEN", [0, 0], [4, 4], CANONICAL_WALLS, []),
        _case("HIDDEN-6", "Hardcode visible tidak cukup", "HIDDEN", [4, 0], [4, 4], [], [["RIGHT"] * 4, ["UP"]]),
        _case("HIDDEN-7", "Urutan input dipertahankan", "HIDDEN", [3, 3], [1, 3], [[2, 3]], [["UP", "UP"], ["LEFT", "UP", "UP", "RIGHT"]]),
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
        result.append({
            "test_id": case["test_id"],
            "name": case["name"],
            "input": {
                "start": case["start"], "target": case["target"],
                "walls": case["walls"], "candidates": case["candidates"],
            },
            "expected": expected_best_candidate(case["start"], case["target"], case["walls"], case["candidates"]),
            "visible": True,
        })
    return result


def evaluate(source_code: str, data: dict[str, Any]) -> EvaluationResult:
    return evaluate_rescue_best_route(source_code, data)


QUESTION = QuestionDefinition(
    code="X02_RESCUE_BEST_ROUTE",
    semantic_code="rescue.best_candidate_route",
    level="EXTREME",
    title='Pilih Rute Penyelamatan Terbaik',
    scene_code="RESCUE",
    summary='Robot penyelamat harus mencapai target. Pusat komando telah menyediakan beberapa pilihan rute, tetapi tidak semuanya aman. Buatlah fungsi yang memeriksa seluruh rute dan memilih rute aman dengan jumlah langkah paling sedikit. Jika dua rute sama pendek, pilih rute yang muncul lebih dahulu.',
    learning_objectives=(
    'Buat fungsi pilih_jalur_terbaik(start, target, walls, candidates).',
    'Periksa semua rute di dalam candidates dari urutan pertama hingga terakhir tanpa mengubah isi atau urutannya.',
    'Abaikan rute yang tidak aman, kemudian kembalikan informasi rute terbaik dalam satu dictionary.',
),
    input_format=(
    'start adalah posisi awal robot dalam bentuk [baris, kolom].',
    'target adalah posisi tujuan robot.',
    'walls adalah daftar posisi dinding yang tidak boleh dimasuki.',
    'candidates adalah daftar pilihan rute. Setiap rute berisi arah UP, DOWN, LEFT, atau RIGHT.',
),
    output_format=(
    'Kembalikan dictionary dengan tepat tiga key: selected_index, selected_path, dan step_count.',
    'selected_index adalah indeks rute yang dipilih. Indeks list Python dimulai dari 0.',
    'selected_path adalah isi rute yang dipilih, sedangkan step_count adalah jumlah langkahnya.',
    'Jika tidak ada rute yang aman, kembalikan {"selected_index": None, "selected_path": [], "step_count": None}.',
),
    starter_code=STARTER_CODE,
    create_attempt_data=create_attempt_data,
    visible_cases=visible_cases,
    evaluate=evaluate,
    question_type="FREE",
    required_function="pilih_jalur_terbaik",
    required_technique=None,
    evaluation_adapter="RESCUE_BEST_ROUTE",
    animation_adapter="RESCUE_BEST_ROUTE",
    max_score=100.0,
    active=True,
    version=3,
    lifecycle_status="FINAL",
    contract_version="FINAL-2026-08-02",
    source_document="Backend final Rescue Soal 3",
    metadata={
        "grid": {"rows": 5, "columns": 5},
        "movement_tokens": ["UP", "DOWN", "LEFT", "RIGHT"],
        "strict_result_keys": ["selected_index", "selected_path", "step_count"],
        "input_mutation_forbidden": True,
        "maze_version": MAZE_VERSION,
        "maze_checksum_sha256": MAZE_CHECKSUM_SHA256,
    },
)
