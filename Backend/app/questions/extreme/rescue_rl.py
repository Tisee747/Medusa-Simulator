"""Extreme 01: implement the core decisions used by a Q-learning rescue agent."""

from __future__ import annotations

import json
from typing import Any

from app.code_runner import run_source
from app.questions.base import EvaluationResult, QuestionDefinition

STARTER_CODE = '''def update_q_value(old_q, reward, best_next_q, alpha, gamma):
    # Perbarui catatan Q-value dari hadiah sekarang dan peluang hadiah berikutnya.
    return old_q


def pilih_aksi(q_values, epsilon, random_value, random_action):
    # Pilih apakah robot mencoba aksi acak atau memakai aksi dengan Q-value terbesar.
    return random_action
'''

_HARNESS = r'''
import json as _json
import random as _random

_MARKER = "__SIMULATOR_RESULT__"
_ACTIONS = [(-1, 0), (1, 0), (0, -1), (0, 1)]
_ACTION_NAMES = ["U", "D", "L", "R"]
_MAPS = [
    ["S....", ".##..", "...#.", ".#...", "....T"],
    ["S.#..", "..#..", "..#..", ".....", ".###T"],
    ["S....", "###..", ".....", "..###", "....T"],
    ["S..#.", ".#.#.", ".#...", ".###.", "....T"],
    ["S....", ".###.", "...#.", ".#...", "...#T"],
]

# This is the fixed 5x5 maze that exists in Firestorm. Animation must use
# a policy trained on this exact layout, never a path from another hidden maze.
_DEMO_MAP = [
    "S.#..",
    "..#..",
    "#...#",
    ".##..",
    "....T",
]


def _find(grid, token):
    for r, row in enumerate(grid):
        for c, value in enumerate(row):
            if value == token:
                return (r, c)
    raise ValueError(token)


def _step(grid, state, action):
    dr, dc = _ACTIONS[action]
    nr, nc = state[0] + dr, state[1] + dc
    if nr < 0 or nc < 0 or nr >= len(grid) or nc >= len(grid[0]) or grid[nr][nc] == "#":
        return state, -15.0, False
    next_state = (nr, nc)
    target = _find(grid, "T")
    if next_state == target:
        return next_state, 100.0, True
    return next_state, -1.0, False


def _train(grid, seed):
    rng = _random.Random(seed)
    start = _find(grid, "S")
    q = {}

    def values(state):
        return q.setdefault(state, [0.0, 0.0, 0.0, 0.0])

    for episode in range(700):
        state = start
        epsilon = max(0.05, 1.0 - episode / 600.0)
        for _ in range(80):
            action = pilih_aksi(values(state)[:], epsilon, rng.random(), rng.randrange(4))
            if not isinstance(action, int) or action < 0 or action > 3:
                raise ValueError("pilih_aksi() harus mengembalikan integer 0 sampai 3.")
            next_state, reward, done = _step(grid, state, action)
            old_q = values(state)[action]
            best_next = max(values(next_state))
            values(state)[action] = float(update_q_value(old_q, reward, best_next, 0.7, 0.9))
            state = next_state
            if done:
                break

    state = start
    path = []
    visited = {}
    for _ in range(60):
        q_values = values(state)
        action = max(range(4), key=lambda index: q_values[index])
        next_state, _, done = _step(grid, state, action)
        path.append(_ACTION_NAMES[action])
        state = next_state
        visited[state] = visited.get(state, 0) + 1
        if done:
            return True, path
        if visited[state] > 8:
            break
    return False, path

visible = []
hidden_passed = 0
hidden_total = 6
error = ""
paths = []

try:
    update_visible = [
        ((0.0, 10.0, 4.0, 0.5, 0.9), 6.8),
        ((5.0, -1.0, 3.0, 0.2, 0.8), 4.28),
    ]
    for index, (args, expected) in enumerate(update_visible, 1):
        actual = float(update_q_value(*args))
        visible.append({
            "name": f"Rumus Q-learning {index}",
            "input": str(args),
            "expected": f"{expected:.4f}",
            "actual": f"{actual:.4f}",
            "passed": abs(actual - expected) < 1e-6,
        })

    choose_visible = [
        (([1.0, 4.0, 2.0, 3.0], 0.1, 0.9, 0), 1),
        (([1.0, 4.0, 2.0, 3.0], 0.5, 0.2, 3), 3),
    ]
    for index, (args, expected) in enumerate(choose_visible, 1):
        actual = pilih_aksi(*args)
        visible.append({
            "name": f"Pemilihan aksi {index}",
            "input": str(args),
            "expected": str(expected),
            "actual": str(actual),
            "passed": actual == expected,
        })

    hidden_updates = [
        (2.0, 0.0, 5.0, 1.0, 0.5, 2.5),
        (-3.0, 7.0, 2.0, 0.3, 0.9, 0.54),
    ]
    for old, reward, best, alpha, gamma, expected in hidden_updates:
        actual = float(update_q_value(old, reward, best, alpha, gamma))
        hidden_passed += abs(actual - expected) < 1e-6

    hidden_passed += pilih_aksi([5.0, 5.0, 1.0, 0.0], 0.0, 0.9, 3) in (0, 1)
    hidden_passed += pilih_aksi([0.0, 0.0, 0.0, 0.0], 1.0, 0.1, 2) == 2

    successful = 0
    total_steps = 0
    for seed, grid in enumerate(_MAPS, 101):
        ok, path = _train(grid, seed)
        paths.append({"seed": seed, "success": ok, "path": path})
        if ok:
            successful += 1
            total_steps += len(path)

    demo_success, demo_path = _train(_DEMO_MAP, 777)
    hidden_passed += successful >= 4
    hidden_passed += successful == 5
except Exception as exc:
    demo_success = False
    demo_path = []
    error = str(exc)

visible_passed = sum(1 for item in visible if item["passed"])
unit_score = 40.0 * (visible_passed + min(hidden_passed, 4)) / 8.0
success_count = sum(1 for item in paths if item["success"])
success_score = 40.0 * success_count / 5.0
successful_paths = [item["path"] for item in paths if item["success"]]
average_steps = (
    sum(len(path) for path in successful_paths) / len(successful_paths)
    if successful_paths else 999.0
)
efficiency_score = max(0.0, 20.0 - max(0.0, average_steps - 12.0) * 1.5)
score = round(min(100.0, unit_score + success_score + efficiency_score), 1)

best = next((item for item in paths if item["success"]), {"seed": 0, "path": []})
payload = {
    "visible": visible,
    "hidden_passed": hidden_passed,
    "hidden_total": hidden_total,
    "success_count": success_count,
    "maze_total": 5,
    "average_steps": round(average_steps, 1),
    "score": score,
    "best_seed": best["seed"],
    "best_path": best["path"],
    "demo_success": demo_success,
    "demo_path": demo_path,
    "error": error,
}
print(_MARKER + _json.dumps(payload, ensure_ascii=False))
'''


def create_attempt_data() -> dict[str, Any]:
    """Describe the visible units and randomized performance evaluation."""

    return {
        "visible_unit_tests": 4,
        "hidden_unit_tests": 4,
        "seeded_mazes": 5,
        "passing_score": 75,
        "animation_case": {
            "start": [0, 0],
            "target": [4, 4],
            "walls": [[0, 2], [1, 2], [2, 0], [2, 4], [3, 1], [3, 2]],
        },
    }


def visible_cases(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Show representative formula and epsilon-greedy examples."""

    return [
        {
            "name": "Perbarui Q-value dari satu pengalaman",
            "input": "old=0, reward=10, next=4, alpha=0.5, gamma=0.9",
            "expected": "6.8000",
            "visible": True,
        },
        {
            "name": "Robot memilih aksi dengan nilai terbaik",
            "input": "q=[1,4,2,3], epsilon=0.1, random=0.9",
            "expected": "aksi 1",
            "visible": True,
        },
        {
            "name": "Robot mencoba aksi acak",
            "input": "q=[1,4,2,3], epsilon=0.5, random=0.2, random_action=3",
            "expected": "aksi 3",
            "visible": True,
        },
    ]


def evaluate(source_code: str, data: dict[str, Any]) -> EvaluationResult:
    """Evaluate Q-learning units and train the agent on seeded hidden mazes."""

    run = run_source(source_code + "\n" + _HARNESS, timeout_seconds=8)
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
            message="Pelatihan melewati batas waktu.",
            error_message="Periksa fungsi yang terlalu lambat atau loop yang tidak berhenti.",
            stdout=run.stdout,
            stderr=run.stderr,
        )
    if not run.ok:
        return EvaluationResult(
            status="ERROR",
            score=0,
            message="Program berhenti saat evaluasi agen.",
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
            message="Hasil evaluasi RL tidak ditemukan.",
            error_message="Jangan menghapus fungsi update_q_value() atau pilih_aksi().",
            stdout=run.stdout,
            stderr=run.stderr,
        )

    payload = json.loads(marker_line[len("__SIMULATOR_RESULT__") :])
    visible_passed = sum(1 for item in payload["visible"] if item["passed"])
    unit_ok = visible_passed == len(payload["visible"])
    correct = (
        unit_ok
        and payload["hidden_passed"] == payload["hidden_total"]
        and payload["score"] >= data["passing_score"]
        and payload["success_count"] >= 4
        and payload.get("demo_success")
        and not payload.get("error")
    )

    return EvaluationResult(
        status="CORRECT" if correct else ("ERROR" if payload.get("error") else "WRONG"),
        score=float(payload["score"]),
        message=(
            "Agen memenuhi unit test dan target performa."
            if correct
            else f"Agen berhasil pada {payload['success_count']} dari {payload['maze_total']} maze."
        ),
        program_output="".join(payload.get("demo_path", [])),
        error_message=payload.get("error", ""),
        stdout=run.stdout,
        stderr=run.stderr,
        visible_results=payload["visible"],
        hidden_summary={
            "passed": payload["hidden_passed"],
            "total": payload["hidden_total"],
            "success_count": payload["success_count"],
            "maze_total": payload["maze_total"],
            "average_steps": payload["average_steps"],
            "demo_success": bool(payload.get("demo_success")),
        },
        animation={
            "seed": 777,
            "path": payload.get("demo_path", []),
            "score": payload["score"],
            "maze": "FIRESTORM_DEMO_V1",
        },
    )


QUESTION = QuestionDefinition(
    code="X01_RESCUE_RL",
    level="EXTREME",
    title='Latih Robot dengan Q-Learning',
    scene_code="RESCUE_RL",
    summary='Robot penyelamat belajar memilih arah berdasarkan pengalaman. Setiap tindakan menghasilkan reward berupa hadiah atau hukuman. Q-value menyimpan perkiraan seberapa baik suatu tindakan. Lengkapilah dua fungsi yang digunakan robot untuk memperbarui Q-value dan memilih tindakan.',
    learning_objectives=(
    'Lengkapi update_q_value() untuk menghitung Q-value yang baru dari nilai lama, reward, dan nilai terbaik pada keadaan berikutnya.',
    'Pahami alpha sebagai besar pengaruh pengalaman baru dan gamma sebagai besar pengaruh kemungkinan reward berikutnya.',
    'Lengkapi pilih_aksi() dengan aturan epsilon-greedy. Epsilon menentukan peluang robot mencoba tindakan acak; jika tidak, robot memilih Q-value terbesar.',
),
    input_format=(
    'Soal ini tidak membaca data dengan input(). Saat diuji, fungsi update_q_value() dan pilih_aksi() akan dijalankan secara langsung.',
    'update_q_value menerima old_q, reward, best_next_q, alpha, dan gamma.',
    'pilih_aksi menerima q_values, epsilon, random_value, dan random_action.',
    'Contoh: old_q=0, reward=10, best_next_q=4, alpha=0.5, dan gamma=0.9 menghasilkan Q-value baru 6.8.',
),
    output_format=(
    'update_q_value() mengembalikan satu angka yang merupakan Q-value baru.',
    'pilih_aksi() mengembalikan index tindakan 0, 1, 2, atau 3.',
),
    starter_code=STARTER_CODE,
    create_attempt_data=create_attempt_data,
    visible_cases=visible_cases,
    evaluate=evaluate,
    animation_adapter="RESCUE_RL_LEGACY",
    version=6,
    lifecycle_status="LEGACY",
    replacement_status="REPLACED_BY_H03_RESCUE_PATH_CHECK",
    metadata={"final_contract_available": False, "legacy_extreme": True},
)
