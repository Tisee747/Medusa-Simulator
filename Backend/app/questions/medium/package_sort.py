"""Medium 02: sort package weights using a list and a helper function."""

from __future__ import annotations

import random
from typing import Any

from app.questions.base import EvaluationResult, QuestionDefinition, evaluate_standard_cases

STARTER_CODE = '''# Fungsi ini harus mengembalikan berat paket dari kecil ke besar.
def urutkan_paket(data):
    # Susun isi data tanpa menghilangkan angka yang sama.
    return data

# Baca jumlah paket dan daftar beratnya.
jumlah = int(input())
berat = list(map(int, input().split()))
hasil = urutkan_paket(berat[:jumlah])
print(*hasil)
'''


def _case(test_id: str, name: str, values: list[int]) -> dict[str, Any]:
    return {
        "test_id": test_id,
        "animation_case_id": test_id,
        "name": name,
        "input": f"{len(values)}\n{' '.join(map(str, values))}\n",
        "expected": " ".join(map(str, sorted(values))),
        "visible": True,
        "values": values,
        "input_data": {"values": values},
    }


def create_attempt_data() -> dict[str, Any]:
    """Create normal, sorted, reverse, and duplicate-value tests."""

    normal = random.sample(range(2, 20), 5)
    ascending = sorted(random.sample(range(1, 15), 4))
    reverse = sorted(random.sample(range(5, 25), 5), reverse=True)
    duplicate = [4, 2, 4, 1, 2]
    return {
        "cases": [
            _case("VISIBLE-1", "Paket dengan berat acak", normal),
            _case("VISIBLE-2", "Paket sudah tersusun", ascending),
            _case("VISIBLE-3", "Paket tersusun dari berat terbesar", reverse),
            _case("VISIBLE-4", "Ada beberapa paket dengan berat sama", duplicate),
        ],
        "animation_case": 0,
    }


def visible_cases(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Expose all Medium sorting tests and expected output."""

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
    """Require correct output for all visible sorting tests."""

    result = evaluate_standard_cases(source_code, data["cases"])
    case = data["cases"][data["animation_case"]]
    result.animation = {
        "input": case["values"],
        "sorted": sorted(case["values"]),
    }
    return result


QUESTION = QuestionDefinition(
    code="M02_PACKAGE_SORT",
    level="MEDIUM",
    title='Urutkan Berat Paket',
    scene_code="PACKAGE_SORT",
    summary='Robot gudang menerima beberapa paket dengan berat yang berbeda-beda. Agar paket mudah disusun, buatlah program yang mengurutkan seluruh berat paket dari yang paling ringan hingga yang paling berat.',
    learning_objectives=(
    'Baca seluruh data berat paket yang diberikan.',
    'Lengkapi fungsi urutkan_paket(data) agar menghasilkan urutan dari nilai terkecil ke nilai terbesar.',
    'Tampilkan semua berat paket sesuai urutan yang telah dibuat.',
),
    input_format=(
    'Baris pertama berisi jumlah paket.',
    'Baris kedua berisi berat setiap paket yang dipisahkan oleh spasi.',
),
    output_format=(
    'Tampilkan seluruh berat paket dari yang paling kecil hingga yang paling besar.',
    'Pisahkan setiap angka dengan satu spasi dan jangan menghilangkan berat yang sama.',
),
    starter_code=STARTER_CODE,
    create_attempt_data=create_attempt_data,
    visible_cases=visible_cases,
    evaluate=evaluate,
    question_type="TECHNIQUE",
    required_technique="FUNCTION",
    animation_adapter="PACKAGE_SORT",
    version=5,
    lifecycle_status="LEGACY",
)
