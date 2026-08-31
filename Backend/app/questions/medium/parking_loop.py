"""Medium 01: process a parking session until the SELESAI sentinel."""

from __future__ import annotations

import random
from typing import Any

from app.questions.base import EvaluationResult, QuestionDefinition, evaluate_standard_cases

_RATES = {"MOTOR": 2000, "MOBIL": 5000, "TRUK": 8000}

STARTER_CODE = '''# Total biaya dimulai dari nol.
total_pendapatan = 0
jenis = input().strip().upper()

# Ulangi selama pengguna belum menulis SELESAI.
while jenis != "SELESAI":
    jam = int(input())

    # Pilih tarif, lalu hitung biaya kendaraan ini.
    biaya = 0
    total_pendapatan += biaya

    # Baca kendaraan berikutnya untuk menentukan apakah loop berlanjut.
    jenis = input().strip().upper()

print(total_pendapatan)
'''


def _make_case(name: str, count: int) -> dict[str, Any]:
    vehicles: list[dict[str, Any]] = []
    lines: list[str] = []
    total = 0
    for _ in range(count):
        vehicle = random.choice(tuple(_RATES))
        hours = random.randint(1, 6)
        vehicles.append({"vehicle": vehicle, "hours": hours})
        lines.extend([vehicle, str(hours)])
        total += _RATES[vehicle] * hours
    lines.append("SELESAI")
    return {
        "name": name,
        "input": "\n".join(lines) + "\n",
        "expected": str(total),
        "visible": True,
        "vehicles": vehicles,
    }


def create_attempt_data() -> dict[str, Any]:
    """Generate several fully visible parking-session tests."""

    cases = [
        _make_case("Sesi dengan tiga kendaraan", 3),
        _make_case("Sesi dengan satu kendaraan", 1),
        _make_case("Sesi dengan empat kendaraan", 4),
        {
            "name": "Sesi langsung selesai tanpa kendaraan",
            "input": "SELESAI\n",
            "expected": "0",
            "visible": True,
            "vehicles": [],
        },
    ]
    return {"cases": cases, "animation_case": 0}


def visible_cases(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Expose every Medium test, including its expected total."""

    return [
        {
            "name": case["name"],
            "input": case["input"].rstrip(),
            "expected": case["expected"],
            "visible": True,
        }
        for case in data["cases"]
    ]


def evaluate(source_code: str, data: dict[str, Any]) -> EvaluationResult:
    """Require the program to pass all visible sentinel-loop tests."""

    result = evaluate_standard_cases(source_code, data["cases"])
    animation_case = data["cases"][data["animation_case"]]
    result.animation = {
        "vehicles": animation_case["vehicles"],
        "total": int(animation_case["expected"]),
    }
    return result


QUESTION = QuestionDefinition(
    code="M01_PARKING_LOOP",
    level="MEDIUM",
    title='Hitung Total Sesi Parkir',
    scene_code="PARKING",
    summary='Kendaraan datang ke area parkir satu per satu. Jumlah kendaraan tidak diketahui sejak awal. Buatlah program yang terus membaca data kendaraan sampai pengguna menulis SELESAI, kemudian menghitung total biaya seluruh kendaraan.',
    learning_objectives=(
    'Gunakan perulangan while untuk membaca data kendaraan berulang kali.',
    'Hitung biaya setiap kendaraan berdasarkan jenis dan lama parkirnya.',
    'Tambahkan setiap biaya ke total, lalu tampilkan total setelah sesi berakhir.',
),
    input_format=(
    'Setiap kendaraan ditulis dalam dua baris: jenis kendaraan, kemudian lama parkir dalam jam.',
    'Setelah kendaraan terakhir, pengguna menulis SELESAI. Kata tersebut tidak diikuti lama parkir.',
),
    output_format=(
    'Tampilkan satu bilangan yang merupakan jumlah biaya seluruh kendaraan dalam sesi tersebut.',
    'Pada soal ini, biaya setiap kendaraan tidak perlu ditampilkan satu per satu.',
),
    starter_code=STARTER_CODE,
    create_attempt_data=create_attempt_data,
    visible_cases=visible_cases,
    evaluate=evaluate,
    question_type="TECHNIQUE",
    required_technique="WHILE",
    animation_adapter="PARKING_LOOP",
    version=5,
    lifecycle_status="LEGACY",
)
