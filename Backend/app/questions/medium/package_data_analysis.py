"""Package Soal 1 final: analyze structured package records."""

from __future__ import annotations

from typing import Any

from app.evaluators.package_data import build_expected, evaluate_package_data
from app.questions.base import EvaluationResult, QuestionDefinition

STARTER_CODE = '''def analisis_paket(data, kategori_target, batas_berat, package_dicari):
    hasil = {
        "total_berat": 0,
        "terberat": None,
        "jumlah_target": 0,
        "kategori": [],
        "ditemukan": "TIDAK_ADA",
        "lolos": [],
    }

    # Periksa setiap paket di dalam data.
    # Isi keenam bagian hasil sesuai informasi yang ditemukan.

    return hasil
'''


def _case(
    test_id: str,
    name: str,
    records: list[tuple[str, str, int]],
    kategori_target: str,
    batas_berat: int,
    package_dicari: str,
    visibility: str,
) -> dict[str, Any]:
    expected = build_expected(records, kategori_target, batas_berat, package_dicari)
    return {
        "test_id": test_id,
        "name": name,
        "data": [list(record) for record in records],
        "kategori_target": kategori_target,
        "batas_berat": batas_berat,
        "package_dicari": package_dicari,
        "expected": expected,
        "test_visibility": visibility,
    }


def create_attempt_data() -> dict[str, Any]:
    cases = [
        _case("VISIBLE-1", "Buat ringkasan lima paket", [
            ("PACKAGE_1", "MERAH", 7), ("PACKAGE_2", "BIRU", 4),
            ("PACKAGE_3", "MERAH", 10), ("PACKAGE_4", "HIJAU", 6),
            ("PACKAGE_5", "BIRU", 3),
        ], "MERAH", 5, "PACKAGE_4", "VISIBLE"),
        _case("VISIBLE-2", "Dua paket memiliki berat terbesar yang sama", [
            ("PACKAGE_1", "KUNING", 8), ("PACKAGE_2", "BIRU", 8),
            ("PACKAGE_3", "KUNING", 2),
        ], "KUNING", 8, "PACKAGE_5", "VISIBLE"),
        _case("VISIBLE-3", "Tidak ada paket yang melewati batas berat", [
            ("PACKAGE_1", "MERAH", 5), ("PACKAGE_2", "MERAH", 7),
        ], "HIJAU", 4, "PACKAGE_2", "VISIBLE"),
        _case("VISIBLE-4", "Data hanya berisi satu paket", [
            ("PACKAGE_4", "BIRU", 1),
        ], "BIRU", 1, "PACKAGE_4", "VISIBLE"),
        # Deterministic hidden cases use only the policy explicitly allowed by the final contract.
        _case("HIDDEN-1", "Semua kategori sama dan batas tepat", [
            ("PACKAGE_3", "MERAH", 4), ("PACKAGE_1", "MERAH", 9),
            ("PACKAGE_5", "MERAH", 9), ("PACKAGE_2", "MERAH", 2),
        ], "MERAH", 4, "PACKAGE_5", "HIDDEN"),
        _case("HIDDEN-2", "Seluruh kategori berbeda", [
            ("PACKAGE_5", "UNGU", 3), ("PACKAGE_2", "BIRU", 6),
            ("PACKAGE_4", "HIJAU", 1),
        ], "MERAH", 10, "PACKAGE_1", "HIDDEN"),
        _case("HIDDEN-3", "Tie pertama pada urutan input", [
            ("PACKAGE_4", "KUNING", 12), ("PACKAGE_1", "BIRU", 12),
            ("PACKAGE_2", "HIJAU", 5), ("PACKAGE_3", "BIRU", 7),
            ("PACKAGE_5", "KUNING", 2),
        ], "BIRU", 7, "PACKAGE_3", "HIDDEN"),
        _case("HIDDEN-4", "Tidak ditemukan dan tidak lolos", [
            ("PACKAGE_2", "ABU", 11), ("PACKAGE_1", "PUTIH", 13),
        ], "HITAM", 1, "PACKAGE_5", "HIDDEN"),
    ]
    return {"cases": cases, "final_animation_case_id": "VISIBLE-1"}


def visible_cases(data: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "test_id": case["test_id"], "name": case["name"],
            "input": {
                "data": case["data"], "kategori_target": case["kategori_target"],
                "batas_berat": case["batas_berat"], "package_dicari": case["package_dicari"],
            },
            "expected": case["expected"], "visible": True,
            "editor_legend": [
                {"package_id": item[0], "kategori": item[1], "berat": item[2]}
                for item in case["data"]
            ],
            "slot_visual_order": "LEFT_TO_RIGHT",
        }
        for case in data["cases"] if case["test_visibility"] == "VISIBLE"
    ]


def evaluate(source_code: str, data: dict[str, Any]) -> EvaluationResult:
    return evaluate_package_data(source_code, data)


QUESTION = QuestionDefinition(
    code="M04_PACKAGE_DATA_ANALYSIS",
    level="MEDIUM",
    title='Buat Ringkasan Data Paket',
    scene_code="PACKAGE",
    summary='Supervisor gudang memberikan daftar paket yang berisi ID, kategori, dan berat. Buatlah fungsi yang membaca seluruh data tersebut, kemudian menghasilkan ringkasan yang dapat digunakan untuk memeriksa kondisi paket di gudang.',
    learning_objectives=(
    'Buat fungsi analisis_paket(data, kategori_target, batas_berat, package_dicari).',
    'Hitung jumlah seluruh berat, tentukan paket paling berat, dan hitung banyak paket pada kategori yang diminta.',
    'Buat daftar kategori, cari paket tertentu, dan tentukan paket yang beratnya tidak melebihi batas.',
),
    input_format=(
    'data adalah list paket. Setiap paket berisi ID, kategori, dan berat. Contoh: ["PACKAGE_1", "MERAH", 7].',
    'kategori_target adalah kategori yang ingin dihitung jumlah paketnya.',
    'batas_berat adalah berat maksimum agar sebuah paket masuk ke daftar lolos.',
    'package_dicari adalah ID paket yang ingin dicari di dalam data.',
),
    output_format=(
    'Kembalikan dictionary dengan enam key: total_berat, terberat, jumlah_target, kategori, ditemukan, dan lolos.',
    'total_berat berisi jumlah seluruh berat. terberat berisi ID paket paling berat. Jika beratnya sama, pilih paket yang muncul lebih dahulu.',
    'jumlah_target berisi banyak paket dengan kategori_target. kategori berisi kategori yang berbeda dan diurutkan sesuai abjad.',
    'ditemukan berisi package_dicari jika paket tersedia, atau TIDAK_ADA jika tidak ditemukan.',
    'lolos berisi ID paket dengan berat kurang dari atau sama dengan batas_berat, sesuai urutan data awal.',
),
    starter_code=STARTER_CODE,
    create_attempt_data=create_attempt_data,
    visible_cases=visible_cases,
    evaluate=evaluate,
    question_type="FREE",
    required_function="analisis_paket",
    required_technique=None,
    evaluation_adapter="M04_PACKAGE_DATA_ANALYSIS",
    animation_adapter="M04_PACKAGE_DATA_ANALYSIS",
    max_score=100.0,
    active=True,
    version=5,
    lifecycle_status="FINAL",
    contract_version="FINAL-V2-2026-08-01",
    source_document="PACKAGE_SOAL_1_KONTRAK_FINAL_BACKEND_READY_V2.docx",
    metadata={
        "visual_contract": {
            "slot_order_confirmed": True,
            "slot_order": "LEFT_TO_RIGHT",
            "slot_actor_home_alignment": {
                "SLOT_1": "PACKAGE_1",
                "SLOT_2": "PACKAGE_2",
                "SLOT_3": "PACKAGE_3",
                "SLOT_4": "PACKAGE_4",
                "SLOT_5": "PACKAGE_5",
            },
            "slot_visual_positions": {
                "SLOT_1": "paling kiri",
                "SLOT_2": "kedua dari kiri",
                "SLOT_3": "tengah",
                "SLOT_4": "kedua dari kanan",
                "SLOT_5": "paling kanan",
            },
            "package_labels_visible": False,
            "package_id_visibility": {
                "PACKAGE_1": "NOT_VISIBLE",
                "PACKAGE_2": "NOT_VISIBLE",
                "PACKAGE_3": "NOT_VISIBLE",
                "PACKAGE_4": "NOT_VISIBLE",
                "PACKAGE_5": "NOT_VISIBLE",
            },
            "editor_legend_required": True,
            "package_identity_must_be_shown_in_editor": True,
        },
        "slot_order": ["SLOT_1", "SLOT_2", "SLOT_3", "SLOT_4", "SLOT_5"],
        "visual_confirmation_status": "COMPLETE",
    },
)
