"""Traffic Soal 1 final: one exact action for each visible color input."""

from __future__ import annotations

from typing import Any

from app.evaluators.traffic import evaluate_traffic
from app.questions.base import EvaluationResult, QuestionDefinition

STARTER_CODE = '''# Baca warna lampu, rapikan spasi, lalu ubah menjadi huruf besar.
warna = input().strip().upper()

# Isi warna dan tindakan yang tepat pada setiap kondisi.
if warna == "_____":
    tindakan = "_____"
elif warna == "_____":
    tindakan = "_____"
elif warna == "_____":
    tindakan = "_____"
else:
    tindakan = "TIDAK_VALID"

print(tindakan)
'''

_CASES = (
    ("VISIBLE-RED", "MERAH", "MERAH", "BERHENTI", True),
    ("VISIBLE-YELLOW", "kuning", "KUNING", "HATI_HATI", True),
    ("VISIBLE-GREEN", "hijau", "HIJAU", "JALAN", True),
    ("VISIBLE-INVALID", "BIRU", "BIRU", "TIDAK_VALID", False),
)


def create_attempt_data() -> dict[str, Any]:
    return {
        "cases": [
            {
                "test_id": test_id,
                "animation_case_id": test_id,
                "name": {
                    "VISIBLE-RED": "Lampu merah: mobil harus berhenti",
                    "VISIBLE-YELLOW": "Lampu kuning: mobil harus hati-hati",
                    "VISIBLE-GREEN": "Lampu hijau: mobil boleh jalan",
                    "VISIBLE-INVALID": "Warna tidak dikenal",
                }[test_id],
                "input_raw": input_raw,
                "normalized_input_color": normalized,
                "expected_action": expected,
                "valid_input": valid,
                "visible": True,
            }
            for test_id, input_raw, normalized, expected, valid in _CASES
        ],
        "final_animation_case_id": "TRAFFIC-MAIN-SEQUENCE",
    }


def visible_cases(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "test_id": case["test_id"],
            "name": case["name"],
            "input": case["input_raw"],
            "expected": case["expected_action"],
            "visible": True,
        }
        for case in data["cases"]
    ]


def evaluate(source_code: str, data: dict[str, Any]) -> EvaluationResult:
    return evaluate_traffic(source_code, data)


QUESTION = QuestionDefinition(
    code="E01_TRAFFIC",
    semantic_code="traffic.single_light_action",
    level="EASY",
    title='Lampu Lalu Lintas',
    scene_code="TRAFFIC",
    summary='Sebuah kendaraan sedang berada di persimpangan dan harus mengikuti warna lampu lalu lintas. Buatlah program yang membaca warna lampu, kemudian menampilkan tindakan yang tepat agar kendaraan dapat bergerak dengan aman.',
    learning_objectives=(
    'Baca warna lampu dari input, lalu rapikan spasi dan ubah tulisannya menjadi huruf kapital.',
    'Tentukan tindakan kendaraan dengan percabangan berdasarkan warna yang diberikan.',
    'Tampilkan tepat satu tindakan tanpa kalimat atau baris tambahan.',
),
    input_format=(
    'Program menerima satu warna lampu, misalnya MERAH, KUNING, atau HIJAU.',
    'Penulisan huruf besar dan kecil dapat berbeda. Spasi di awal atau akhir input juga mungkin ada.',
    'Warna yang tidak termasuk MERAH, KUNING, atau HIJAU harus dianggap tidak dikenal.',
),
    output_format=(
    'Tampilkan BERHENTI untuk lampu MERAH.',
    'Tampilkan HATI_HATI untuk lampu KUNING dan JALAN untuk lampu HIJAU.',
    'Jika warna tidak dikenal, tampilkan TIDAK_VALID.',
),
    starter_code=STARTER_CODE,
    create_attempt_data=create_attempt_data,
    visible_cases=visible_cases,
    evaluate=evaluate,
    question_type="FREE",
    required_function=None,
    required_technique=None,
    evaluation_adapter="TRAFFIC_EXACT",
    animation_adapter="TRAFFIC_SEQUENCE",
    max_score=100.0,
    active=True,
    version=5,
    lifecycle_status="FINAL",
    contract_version="FINAL-2026-07-31",
    source_document="traffic_soal1_kontrak_final_backend_ready.docx",
)
