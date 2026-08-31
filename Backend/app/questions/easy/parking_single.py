"""Easy 02: calculate parking fee for all supported vehicle categories."""

from __future__ import annotations

import random
from typing import Any

from app.questions.base import EvaluationResult, QuestionDefinition, evaluate_standard_cases

_RATES = {"MOTOR": 2000, "MOBIL": 5000, "TRUK": 8000}
STARTER_CODE = '''# Baca jenis kendaraan dan jumlah jam parkir.
jenis = input().strip().upper()
jam = int(input())

# Pilih tarif per jam sesuai jenis kendaraan.
tarif = 0

# Hitung lalu tampilkan total biaya parkir.
biaya = tarif * jam
print(biaya)
'''


def create_attempt_data() -> dict[str, Any]:
    cases = []
    for index, (vehicle, rate) in enumerate(_RATES.items(), 1):
        hours = random.randint(1, 8)
        cases.append({
            "test_id": f"VISIBLE-{index}", "animation_case_id": f"VISIBLE-{index}",
            "name": f"Hitung biaya {vehicle}", "input": f"{vehicle}\n{hours}\n", "expected": str(rate * hours),
            "visible": True, "input_data": {"vehicle": vehicle, "hours": hours},
        })
    return {"cases": cases}


def visible_cases(data: dict[str, Any]) -> list[dict[str, Any]]:
    if "cases" not in data:
        return [{"name": "Input aktif", "input": f"{data['vehicle']}\n{data['hours']}", "expected": data.get("expected"), "visible": True}]
    return [{"name": c["name"], "input": c["input"].rstrip(), "expected": c["expected"], "visible": True} for c in data["cases"]]


def evaluate(source_code: str, data: dict[str, Any]) -> EvaluationResult:
    cases = data.get("cases")
    if not cases:
        cases = [{
            "test_id": "VISIBLE-1", "animation_case_id": "VISIBLE-1", "name": "Input aktif",
            "input": f"{data['vehicle']}\n{data['hours']}\n", "expected": str(data["expected"]),
            "visible": True, "input_data": {"vehicle": data["vehicle"], "hours": data["hours"]},
        }]
    return evaluate_standard_cases(source_code, cases)


QUESTION = QuestionDefinition(
    code="E02_PARKING", level="EASY", title='Hitung Biaya Parkir', scene_code="PARKING",
    summary='Sebuah kendaraan akan keluar dari area parkir. Biaya parkir ditentukan oleh jenis kendaraan dan lama kendaraan berada di parkiran. Buatlah program yang menghitung biaya tersebut dengan benar.',
    learning_objectives=(
    'Baca jenis kendaraan dan lama parkir dari input.',
    'Tentukan tarif per jam sesuai jenis kendaraan dengan menggunakan percabangan.',
    'Kalikan tarif dengan lama parkir, kemudian tampilkan total biayanya.',
),
    input_format=(
    'Baris pertama berisi jenis kendaraan: MOTOR, MOBIL, atau TRUK.',
    'Baris kedua berisi lama parkir dalam jam sebagai bilangan bulat.',
),
    output_format=(
    'Tampilkan satu bilangan yang menyatakan total biaya parkir.',
    'Jangan menambahkan Rp, tanda titik ribuan, atau kalimat lain.',
),
    starter_code=STARTER_CODE, create_attempt_data=create_attempt_data, visible_cases=visible_cases,
    evaluate=evaluate, animation_adapter="PARKING_SINGLE", version=5,
    lifecycle_status="LEGACY",
)
