"""River Soal 1 final: recursive path search across multiple safe state pairs."""

from __future__ import annotations

from typing import Any

from app.evaluators.river_recursion import evaluate_river_recursion
from app.questions.base import EvaluationResult, QuestionDefinition

START_STATE = (0, 0, 0, 0)
GOAL_STATE = (1, 1, 1, 1)

STARTER_CODE = '''START_STATE = (0, 0, 0, 0)
GOAL_STATE = (1, 1, 1, 1)


def cari_jalur(start_state, goal_state):
    # Coba satu perjalanan, lalu panggil fungsi ini lagi dari keadaan baru.
    pass


if __name__ == "__main__":
    jalur = cari_jalur(START_STATE, GOAL_STATE)
    if jalur is not None:
        for penumpang in jalur:
            print(penumpang)
'''


def create_attempt_data() -> dict[str, Any]:
    return {
        "cases": [
            {
                "test_id": "CANONICAL", "name": "Seberangkan semua dari kiri ke kanan",
                "test_visibility": "CANONICAL", "start_state": list(START_STATE), "goal_state": list(GOAL_STATE),
            },
            {
                "test_id": "VISIBLE-SAME-STATE", "name": "Tujuan sudah tercapai sejak awal",
                "test_visibility": "VISIBLE", "start_state": [0, 0, 0, 0], "goal_state": [0, 0, 0, 0],
            },
            {
                "test_id": "VISIBLE-PARTIAL", "name": "Lanjutkan dari keadaan aman di tengah perjalanan",
                "test_visibility": "VISIBLE", "start_state": [0, 1, 0, 0], "goal_state": list(GOAL_STATE),
            },
            {
                "test_id": "HIDDEN-1", "name": "State setelah domba menyeberang",
                "test_visibility": "HIDDEN", "start_state": [0, 0, 1, 0], "goal_state": list(GOAL_STATE),
            },
            {
                "test_id": "HIDDEN-2", "name": "State satu langkah sebelum penjemputan domba",
                "test_visibility": "HIDDEN", "start_state": [1, 1, 0, 1], "goal_state": list(GOAL_STATE),
            },
        ],
        "final_animation_case_id": "canonical",
    }


def visible_cases(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "test_id": case["test_id"], "name": case["name"],
            "input": {"start_state": case["start_state"], "goal_state": case["goal_state"]},
            "expected": "List token perjalanan legal dan aman; [] bila start sama dengan goal.",
            "visible": True,
        }
        for case in data["cases"] if case["test_visibility"] != "HIDDEN"
    ]


def evaluate(source_code: str, data: dict[str, Any]) -> EvaluationResult:
    return evaluate_river_recursion(source_code, data)


QUESTION = QuestionDefinition(
    code="H02_RIVER_RECURSION",
    level="HARD",
    title='Cari Jalur Sungai dengan Rekursi',
    scene_code="RIVER",
    summary='Gembala harus kembali membawa serigala, domba, dan rumput ke seberang sungai dengan aman. Pada soal ini, pencarian perjalanan dilakukan dengan rekursi, yaitu fungsi memanggil dirinya sendiri untuk melanjutkan pencarian dari keadaan berikutnya.',
    learning_objectives=(
    'Buat kondisi dasar: jika keadaan saat ini sudah sama dengan tujuan, kembalikan list kosong.',
    'Coba satu penyeberangan yang aman, kemudian panggil cari_jalur() dari keadaan yang baru.',
    'Hentikan pencarian ketika tujuan tercapai agar tidak ada perjalanan tambahan.',
),
    input_format=(
    'Fungsi yang akan diuji adalah cari_jalur(start_state, goal_state).',
    'start_state adalah keadaan awal, sedangkan goal_state adalah keadaan tujuan.',
    'Setiap keadaan berisi posisi gembala, serigala, domba, dan rumput. Angka 0 berarti sisi kiri dan angka 1 berarti sisi kanan.',
),
    output_format=(
    'Kembalikan list berisi SENDIRI, SERIGALA, DOMBA, atau RUMPUT sesuai urutan perjalanan.',
    'Jika start_state sudah sama dengan goal_state, kembalikan [].',
),
    starter_code=STARTER_CODE,
    create_attempt_data=create_attempt_data,
    visible_cases=visible_cases,
    evaluate=evaluate,
    question_type="REQUIRED_TECHNIQUE",
    required_function="cari_jalur",
    required_technique="RECURSION",
    evaluation_adapter="RIVER_RECURSION",
    animation_adapter="RIVER_RECURSION",
    max_score=100.0,
    active=True,
    version=4,
    lifecycle_status="FINAL",
    contract_version="FINAL-2026-07-31",
    source_document="RIVER_SOAL_1_KONTRAK_FINAL_BACKEND_READY.docx",
)
