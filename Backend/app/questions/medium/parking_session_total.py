"""Parking Soal 3: one complete parking session with per-transaction output."""

from __future__ import annotations

import random
from typing import Any

from app.evaluators.parking_session import evaluate_parking_session, expected_fee
from app.questions.base import EvaluationResult, QuestionDefinition

_RATES = {"MOTOR": 2000, "MOBIL": 5000, "TRUK": 8000}

# Derived from the existing M01 Parking while question because the final data
# contract does not provide a replacement starter-code block.
STARTER_CODE = '''# Simpan jumlah biaya seluruh kendaraan dalam sesi ini.
total_pendapatan = 0
jenis = input().strip().upper()

while jenis != "SELESAI":
    jam = int(input())

    # Pilih tarif, hitung biaya, lalu cetak jenis dan biayanya.
    biaya = 0
    print(jenis, biaya)
    total_pendapatan += biaya

    # Baca kendaraan berikutnya atau kata SELESAI.
    jenis = input().strip().upper()

# Baris terakhir selalu berisi TOTAL dan jumlah seluruh biaya.
print("TOTAL", total_pendapatan)
'''


def _make_case(test_id: str, name: str, count: int) -> dict[str, Any]:
    vehicles: list[dict[str, Any]] = []
    input_lines: list[str] = []
    output_lines: list[str] = []
    total = 0
    for _ in range(count):
        vehicle = random.choice(tuple(_RATES))
        hours = random.randint(1, 6)
        fee = expected_fee(vehicle, hours)
        vehicles.append({"vehicle": vehicle, "hours": hours})
        input_lines.extend([vehicle, str(hours)])
        output_lines.append(f"{vehicle} {fee}")
        total += fee
    input_lines.append("SELESAI")
    output_lines.append(f"TOTAL {total}")
    return {
        "test_id": test_id,
        "animation_case_id": test_id,
        "name": name,
        "input": "\n".join(input_lines) + "\n",
        "vehicles": vehicles,
        "expected_output": "\n".join(output_lines),
        "visible": True,
    }


def create_attempt_data() -> dict[str, Any]:
    return {
        "cases": [
            _make_case("VISIBLE-1", "Cetak tiga transaksi dan totalnya", 3),
            _make_case("VISIBLE-2", "Cetak satu transaksi dan totalnya", 1),
            _make_case("VISIBLE-3", "Cetak empat transaksi dan totalnya", 4),
            _make_case("VISIBLE-4", "Sesi selesai tanpa kendaraan", 0),
        ],
        "final_animation_case_id": "VISIBLE-3",
    }


def visible_cases(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "test_id": case["test_id"],
            "name": case["name"],
            "input": case["input"].rstrip(),
            "expected": case["expected_output"],
            "visible": True,
        }
        for case in data["cases"]
    ]


def evaluate(source_code: str, data: dict[str, Any]) -> EvaluationResult:
    return evaluate_parking_session(source_code, data)


QUESTION = QuestionDefinition(
    code="M03_PARKING_SESSION_TOTAL",
    level="MEDIUM",
    title='Buat Laporan Sesi Parkir',
    scene_code="PARKING",
    summary='Petugas parkir membutuhkan laporan untuk satu sesi. Setiap kendaraan harus dicatat bersama biaya parkirnya. Ketika pengguna menulis SELESAI, program harus menampilkan total biaya seluruh kendaraan pada baris terakhir.',
    learning_objectives=(
    'Gunakan perulangan while untuk membaca kendaraan sampai pengguna menulis SELESAI.',
    'Hitung biaya setiap kendaraan, kemudian tampilkan jenis kendaraan dan biayanya pada satu baris.',
    'Jumlahkan seluruh biaya dan tampilkan TOTAL pada akhir laporan.',
),
    input_format=(
    'Setiap kendaraan ditulis dalam dua baris: jenis kendaraan, kemudian lama parkir dalam jam.',
    'Input SELESAI menandakan bahwa tidak ada kendaraan berikutnya.',
),
    output_format=(
    'Untuk setiap kendaraan, tampilkan JENIS BIAYA. Contoh: MOTOR 4000.',
    'Pada baris terakhir, tampilkan TOTAL JUMLAH. Contoh: TOTAL 19000.',
    'Jangan menambahkan baris kosong, keterangan, atau hasil debug.',
),
    starter_code=STARTER_CODE,
    create_attempt_data=create_attempt_data,
    visible_cases=visible_cases,
    evaluate=evaluate,
    question_type="TECHNIQUE",
    required_technique="WHILE",
    evaluation_adapter="M03_PARKING_SESSION_TOTAL",
    animation_adapter="M03_PARKING_SESSION_TOTAL",
    max_score=100.0,
    active=True,
    version=5,
    lifecycle_status="FINAL",
    contract_version="FINAL-2026-07-31",
    source_document="parking_soal3_kontrak_final_v2.docx",
    metadata={
        "test_source": "LEGACY_COMPATIBILITY_GENERATOR",
        "starter_source": "M01_PARKING_LOOP_COMPATIBILITY",
        "contract_gap": True,
    },
)
