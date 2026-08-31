"""Hard 01: solve the wolf, sheep, and grass river puzzle with state search."""

from __future__ import annotations

import json
from typing import Any

from app.code_runner import run_source
from app.questions.base import EvaluationResult, QuestionDefinition

STARTER_CODE = '''from collections import deque

MUATAN = ("SENDIRI", "SERIGALA", "DOMBA", "RUMPUT")


def aman(state):
    # Return True jika domba tetap aman dari serigala dan rumput.
    return True


def pindah(state, muatan):
    # Pindahkan gembala dan muatan, lalu return keadaan baru yang aman.
    return None


def cari_solusi():
    # Gunakan BFS: periksa kemungkinan penyeberangan lapis demi lapis.
    antrean = deque()
    dikunjungi = set()
    return []
'''

_HARNESS = r'''
import json as _json

_MARKER = "__SIMULATOR_RESULT__"


def _ref_aman(state):
    g, w, s, r = state
    return not ((w == s and g != w) or (s == r and g != s))


def _ref_pindah(state, muatan):
    posisi = list(state)
    sisi = posisi[0]
    indeks = {"SERIGALA": 1, "DOMBA": 2, "RUMPUT": 3}
    if muatan == "SENDIRI":
        posisi[0] = 1 - posisi[0]
    elif muatan in indeks and posisi[indeks[muatan]] == sisi:
        posisi[0] = 1 - posisi[0]
        posisi[indeks[muatan]] = 1 - posisi[indeks[muatan]]
    else:
        return None
    hasil = tuple(posisi)
    return hasil if _ref_aman(hasil) else None


def _uji_solusi(actions):
    if not isinstance(actions, list):
        return False, "cari_solusi() harus mengembalikan list."
    if len(actions) > 7:
        return False, "Jalur valid, tetapi belum merupakan solusi terpendek."
    state = (0, 0, 0, 0)
    for action in actions:
        if action not in ("SENDIRI", "SERIGALA", "DOMBA", "RUMPUT"):
            return False, "Solusi berisi nama muatan yang tidak dikenal."
        state = _ref_pindah(state, action)
        if state is None:
            return False, "Solusi menghasilkan perpindahan atau keadaan berbahaya."
    return state == (1, 1, 1, 1), "Solusi belum mencapai sisi kanan."

visible_safe = [
    ((0, 0, 0, 0), True),
    ((1, 0, 1, 0), True),
    ((1, 0, 0, 0), False),
    ((0, 1, 1, 1), False),
]
hidden_safe = [
    ((0, 1, 0, 1), True),
    ((1, 1, 0, 1), True),
    ((0, 0, 1, 0), True),
    ((1, 0, 1, 1), True),
    ((0, 1, 1, 0), False),
    ((1, 0, 0, 1), False),
]
visible_move = [
    ((0, 0, 0, 0), "DOMBA", (1, 0, 1, 0)),
    ((1, 0, 1, 0), "SENDIRI", (0, 0, 1, 0)),
]
hidden_move = [
    ((0, 0, 0, 0), "SERIGALA", None),
    ((0, 0, 0, 0), "RUMPUT", None),
    ((0, 0, 1, 0), "SERIGALA", (1, 1, 1, 0)),
    ((1, 1, 1, 0), "DOMBA", (0, 1, 0, 0)),
    ((0, 1, 0, 0), "RUMPUT", (1, 1, 0, 1)),
    ((1, 1, 0, 1), "SERIGALA", (0, 0, 0, 1)),
]

payload = {
    "visible": [],
    "hidden_passed": 0,
    "hidden_total": len(hidden_safe) + len(hidden_move) + 1,
    "path": [],
    "error": "",
}

try:
    for index, (state, expected) in enumerate(visible_safe, 1):
        actual = bool(aman(state))
        payload["visible"].append({
            "name": f"Validasi state {index}",
            "input": str(state),
            "expected": str(expected),
            "actual": str(actual),
            "passed": actual == expected,
        })

    for index, (state, action, expected) in enumerate(visible_move, 1):
        actual = pindah(state, action)
        payload["visible"].append({
            "name": f"Perpindahan {index}",
            "input": f"{state} + {action}",
            "expected": str(expected),
            "actual": str(actual),
            "passed": actual == expected,
        })

    for state, expected in hidden_safe:
        payload["hidden_passed"] += bool(aman(state)) == expected

    for state, action, expected in hidden_move:
        payload["hidden_passed"] += pindah(state, action) == expected

    actions = cari_solusi()
    valid, reason = _uji_solusi(actions)
    payload["hidden_passed"] += bool(valid)
    payload["path"] = actions if isinstance(actions, list) else []
    if not valid:
        payload["error"] = reason
except Exception as exc:
    payload["error"] = str(exc)

print(_MARKER + _json.dumps(payload, ensure_ascii=False))
'''


def create_attempt_data() -> dict[str, Any]:
    """Return fixed visible examples and hidden-test information."""

    return {
        "visible_examples": [
            {"state": "(0, 0, 0, 0)", "safe": True},
            {"state": "(1, 0, 0, 0)", "safe": False},
            {"move": "(0, 0, 0, 0) + DOMBA", "result": "(1, 0, 1, 0)"},
        ],
        "hidden_count": 13,
    }


def visible_cases(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Show representative state and transition examples."""

    return [
        {
            "name": "Keadaan awal masih aman",
            "input": "(0, 0, 0, 0)",
            "expected": "True",
            "visible": True,
        },
        {
            "name": "Domba berada dalam keadaan berbahaya",
            "input": "(1, 0, 0, 0)",
            "expected": "False",
            "visible": True,
        },
        {
            "name": "Gembala membawa domba menyeberang",
            "input": "(0, 0, 0, 0) + DOMBA",
            "expected": "(1, 0, 1, 0)",
            "visible": True,
        },
    ]


def evaluate(source_code: str, data: dict[str, Any]) -> EvaluationResult:
    """Run visible function checks, hidden checks, and full-solution validation."""

    run = run_source(source_code + "\n" + _HARNESS, timeout_seconds=5)
    if run.validation_error:
        return EvaluationResult(
            status="ERROR",
            score=0,
            message="Kode ditolak oleh pemeriksa keamanan.",
            error_message=run.validation_error,
        )
    if run.timed_out:
        return EvaluationResult(
            status="ERROR",
            score=0,
            message="Program melewati batas waktu.",
            error_message="Periksa loop BFS yang tidak berhenti atau state yang terus berulang.",
            stdout=run.stdout,
            stderr=run.stderr,
        )
    if not run.ok:
        return EvaluationResult(
            status="ERROR",
            score=0,
            message="Program berhenti dengan error.",
            error_message=run.stderr.strip() or "Runtime error.",
            stdout=run.stdout,
            stderr=run.stderr,
        )

    marker_line = next(
        (line for line in reversed(run.stdout.splitlines()) if line.startswith("__SIMULATOR_RESULT__")),
        "",
    )
    if not marker_line:
        return EvaluationResult(
            status="ERROR",
            score=0,
            message="Hasil evaluasi tidak ditemukan.",
            error_message="Jangan menghapus fungsi aman(), pindah(), atau cari_solusi().",
            stdout=run.stdout,
            stderr=run.stderr,
        )

    payload = json.loads(marker_line[len("__SIMULATOR_RESULT__") :])
    visible_passed = sum(1 for item in payload["visible"] if item["passed"])
    visible_total = len(payload["visible"])
    hidden_passed = int(payload["hidden_passed"])
    hidden_total = int(payload["hidden_total"])
    total_passed = visible_passed + hidden_passed
    total = visible_total + hidden_total
    score = round(100 * total_passed / total, 1)
    correct = visible_passed == visible_total and hidden_passed == hidden_total

    return EvaluationResult(
        status="CORRECT" if correct else "WRONG",
        score=score,
        message=(
            "Semua validasi state, perpindahan, dan solusi BFS berhasil."
            if correct
            else f"{total_passed} dari {total} pemeriksaan berhasil."
        ),
        program_output="|".join(payload.get("path", [])),
        error_message=payload.get("error", ""),
        stdout=run.stdout,
        stderr=run.stderr,
        visible_results=payload["visible"],
        hidden_summary={"passed": hidden_passed, "total": hidden_total},
        animation={"path": payload.get("path", [])},
    )


QUESTION = QuestionDefinition(
    code="H01_RIVER_BFS",
    level="HARD",
    title='Menyeberangkan Serigala, Domba, dan Rumput',
    scene_code="RIVER",
    summary='Seorang gembala harus membawa serigala, domba, dan rumput ke seberang sungai. Perahu hanya dapat membawa gembala dan satu penumpang. Susunlah perjalanan yang aman agar seluruhnya sampai di seberang tanpa ada yang dimakan.',
    learning_objectives=(
    'Lengkapi fungsi aman(state) untuk memeriksa keamanan kedua sisi sungai.',
    'Lengkapi fungsi pindah(state, muatan) untuk membentuk keadaan setelah satu penyeberangan.',
    'Gunakan BFS pada cari_solusi() untuk mencoba kemungkinan lapis demi lapis, mulai dari perjalanan yang paling pendek.',
),
    input_format=(
    'Soal ini tidak membaca data dengan input(). Saat diuji, fungsi aman(), pindah(), dan cari_solusi() akan dijalankan secara langsung.',
    'Keadaan ditulis sebagai tuple yang berisi posisi gembala, serigala, domba, dan rumput.',
    'Angka 0 berarti berada di sisi kiri sungai, sedangkan angka 1 berarti berada di sisi kanan.',
),
    output_format=(
    'cari_solusi() harus mengembalikan list berisi penumpang pada setiap perjalanan.',
    'Gunakan token SENDIRI, SERIGALA, DOMBA, atau RUMPUT.',
),
    starter_code=STARTER_CODE,
    create_attempt_data=create_attempt_data,
    visible_cases=visible_cases,
    evaluate=evaluate,
    question_type="TECHNIQUE",
    required_technique="BFS",
    animation_adapter="RIVER_PATH",
    version=5,
    lifecycle_status="LEGACY",
)
