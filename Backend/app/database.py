"""MariaDB persistence with a SQLite test adapter.

Production remains MariaDB. SQLite exists only so automated tests can run without
requiring a database daemon in the source package environment.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from app.config import (
    ANIMATION_ACK_TIMEOUT_SECONDS,
    DB_ENGINE,
    DB_HOST,
    DB_NAME,
    DB_PASSWORD,
    DB_PORT,
    DB_USER,
    SQLITE_PATH,
    STATION_CODE,
)
from app.ids import new_attempt_id


def _utcnow() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def connection() -> Iterator[Any]:
    if DB_ENGINE == "sqlite":
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
    else:
        try:
            import pymysql
            from pymysql.cursors import DictCursor
        except ImportError as exc:
            raise RuntimeError("PyMySQL belum terinstal. Jalankan pip install -r requirements.txt") from exc
        conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset="utf8mb4",
            cursorclass=DictCursor,
            autocommit=False,
        )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _sql(sql: str) -> str:
    return sql.replace("%s", "?") if DB_ENGINE == "sqlite" else sql


def _execute(conn: Any, sql: str, params: tuple[Any, ...] = ()) -> Any:
    cursor = conn.cursor()
    cursor.execute(_sql(sql), params)
    return cursor


def _row(row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def ping_database() -> bool:
    try:
        with connection() as conn:
            row = _row(_execute(conn, "SELECT 1 AS ok").fetchone())
        return bool(row and row["ok"] == 1)
    except Exception:
        return False


def _canonical_question_code(value: Any) -> str:
    from app.questions.registry import canonical_question_code

    return canonical_question_code(str(value or ""))


def _canonical_replacement_status(value: Any) -> str | None:
    from app.questions.registry import canonical_replacement_status

    return canonical_replacement_status(None if value is None else str(value))


def _question_code_candidates(value: Any) -> list[str]:
    from app.questions.registry import QUESTION_CODE_ALIASES

    canonical = _canonical_question_code(value)
    legacy = [old for old, new in QUESTION_CODE_ALIASES.items() if new == canonical]
    return [canonical, *legacy]


def create_attempt(record: dict[str, Any]) -> None:
    canonical_code = _canonical_question_code(record["question_code"])
    question = get_question_record(canonical_code)
    question_id = question["id"] if question else None
    version_id = question.get("current_version_id") if question else None
    sql = """
        INSERT INTO attempts (
            attempt_id, root_attempt_id, client_submission_id, question_code, question_id, question_version_id,
            scene_code, avatar_uuid, avatar_name, input_data, expected_output, result_status
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'WAITING')
    """
    values = (
        record["attempt_id"], record.get("root_attempt_id") or record["attempt_id"],
        record.get("client_submission_id"), canonical_code, question_id, version_id,
        record["scene_code"], record["avatar_uuid"], record["avatar_name"], _json(record["input_data"]),
        record.get("expected_output", "Generated and validated by the question module."),
    )
    with connection() as conn:
        _execute(conn, sql, values)


def _decode_attempt_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    for name, fallback in (
        ("input_data", {}), ("evaluation_data", {}), ("technique_checks", {}),
    ):
        row[name] = _decode_json(row.get(name), fallback)
    if row.get("question_code"):
        row["question_code"] = _canonical_question_code(row["question_code"])
    return row


def get_attempt(attempt_id: str) -> dict[str, Any] | None:
    with connection() as conn:
        row = _row(_execute(conn, "SELECT * FROM attempts WHERE attempt_id = %s LIMIT 1", (attempt_id,)).fetchone())
    return _decode_attempt_row(row)


def get_attempt_by_submission_id(submission_id: str) -> dict[str, Any] | None:
    with connection() as conn:
        row = _row(_execute(conn, "SELECT * FROM attempts WHERE client_submission_id=%s LIMIT 1", (submission_id,)).fetchone())
    return _decode_attempt_row(row)


def prepare_submission_attempt(attempt_id: str, submission_id: str | None = None) -> dict[str, Any]:
    """Claim a draft or clone a completed attempt; same submission_id is idempotent."""

    if submission_id:
        existing = get_attempt_by_submission_id(submission_id)
        if existing:
            existing["_idempotent_replay"] = existing.get("completed_at") is not None
            return existing

    current = get_attempt(attempt_id)
    if not current:
        raise KeyError(attempt_id)
    if current.get("completed_at") is None and current.get("result_status") == "WAITING":
        if submission_id:
            with connection() as conn:
                cursor = _execute(
                    conn,
                    "UPDATE attempts SET client_submission_id=%s WHERE attempt_id=%s AND client_submission_id IS NULL",
                    (submission_id, attempt_id),
                )
                if cursor.rowcount == 0:
                    claimed = _row(_execute(conn, "SELECT * FROM attempts WHERE client_submission_id=%s", (submission_id,)).fetchone())
                    if claimed:
                        decoded = _decode_attempt_row(claimed) or claimed
                        decoded["_idempotent_replay"] = decoded.get("completed_at") is not None
                        return decoded
                    # Another distinct submission claimed the original draft first.
                    # Reload below and clone instead of evaluating against the same row.
            current = get_attempt(attempt_id) or current
            if current.get("client_submission_id") not in (None, submission_id):
                pass
            else:
                return current
        else:
            return current

    new_id = new_attempt_id(current["question_code"])
    record = {
        "attempt_id": new_id,
        "root_attempt_id": current.get("root_attempt_id") or current["attempt_id"],
        "client_submission_id": submission_id,
        "question_code": current["question_code"],
        "scene_code": current["scene_code"],
        "avatar_uuid": current["avatar_uuid"],
        "avatar_name": current["avatar_name"],
        "input_data": current["input_data"],
        "expected_output": current.get("expected_output", ""),
    }
    create_attempt(record)
    return get_attempt(new_id) or record

def persist_evaluation(attempt_id: str, source_code: str, result: Any) -> dict[str, Any]:
    data = result.to_dict()
    technique = data.get("technique_result") or {}
    now = _utcnow()
    with connection() as conn:
        attempt = _row(_execute(conn, "SELECT * FROM attempts WHERE attempt_id = %s FOR UPDATE" if DB_ENGINE != "sqlite" else "SELECT * FROM attempts WHERE attempt_id = %s", (attempt_id,)).fetchone())
        if not attempt:
            raise KeyError(attempt_id)
        if attempt.get("completed_at") is not None:
            return get_attempt(attempt_id) or attempt

        for execution in data.get("executions", []):
            _execute(
                conn,
                """
                INSERT INTO attempt_executions (
                    execution_id, attempt_id, test_id, test_visibility, status,
                    stdout_raw, stderr_raw, return_value, case_behavior_correct,
                    duration_ms, error_type, error_detail, feedback,
                    normalized_result, evaluation_result, started_at, completed_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    execution["execution_id"], attempt_id, execution["test_id"], execution["test_visibility"],
                    execution["status"], execution.get("stdout_raw", ""), execution.get("stderr_raw", ""),
                    _json(execution.get("return_value_serialized")),
                    _bool_db(execution.get("case_behavior_correct")), execution.get("duration_ms"),
                    execution.get("error_type"), execution.get("error_detail"), _json(execution.get("feedback", {})),
                    _json(execution.get("normalized_result", {})), _json(execution.get("evaluation_result", {})),
                    now, now,
                ),
            )

        _execute(
            conn,
            """
            UPDATE attempts SET source_code=%s, program_output=%s, result_status=%s,
                error_message=%s, stdout=%s, stderr=%s, evaluation_data=%s,
                score=%s, behavior_correct=%s, technique_passed=%s, overall_correct=%s,
                required_technique=%s, technique_checks=%s, completed_at=%s
            WHERE attempt_id=%s
            """,
            (
                source_code, data.get("program_output", ""), data.get("status", "ERROR"),
                data.get("error_message") or None, data.get("stdout", ""), data.get("stderr", ""),
                _json(data), float(data.get("score", 0)), _bool_db(data.get("behavior_correct")),
                _bool_db(technique.get("passed", True)), _bool_db(data.get("overall_correct")),
                technique.get("required_technique"), _json(technique.get("checks", {})), now, attempt_id,
            ),
        )
        _apply_progress_and_score(conn, attempt, data, now)
    return get_attempt(attempt_id) or {}


def _apply_progress_and_score(conn: Any, attempt: dict[str, Any], data: dict[str, Any], now: str) -> None:
    """Persist every submitted score and keep one best score per question.

    Correctness remains evaluator-owned. Progress now represents a submitted
    question, while ``best_score`` and the leaderboard keep only the highest
    score reached for that user/question pair.
    """

    if attempt.get("question_id"):
        question = _row(_execute(conn, "SELECT * FROM questions WHERE id=%s", (attempt["question_id"],)).fetchone())
    else:
        question = None
        for code in _question_code_candidates(attempt.get("question_code")):
            question = _row(_execute(conn, "SELECT * FROM questions WHERE question_code=%s", (code,)).fetchone())
            if question:
                break
    if not question:
        raise RuntimeError(f"Question seed missing: {attempt['question_code']}")

    user_id = attempt["avatar_uuid"]
    max_score = float(question.get("max_score") or 100.0)
    submitted_score = max(0.0, min(max_score, float(data.get("score") or 0.0)))
    existing = _row(_execute(
        conn,
        "SELECT * FROM user_progress WHERE user_id=%s AND question_id=%s",
        (user_id, question["id"]),
    ).fetchone())

    if existing:
        best_score = max(float(existing.get("best_score") or 0.0), submitted_score)
        _execute(
            conn,
            """
            UPDATE user_progress SET display_name=%s, is_completed=1, best_score=%s,
                first_completed_at=COALESCE(first_completed_at, %s),
                last_attempt_at=%s, attempt_count=attempt_count+1
            WHERE user_id=%s AND question_id=%s
            """,
            (attempt["avatar_name"], best_score, now, now, user_id, question["id"]),
        )
    else:
        best_score = submitted_score
        _execute(
            conn,
            """
            INSERT INTO user_progress (
                user_id, display_name, question_id, is_completed, best_score,
                first_completed_at, last_attempt_at, attempt_count
            ) VALUES (%s,%s,%s,1,%s,%s,%s,1)
            """,
            (user_id, attempt["avatar_name"], question["id"], best_score, now, now),
        )

    score_delta = _insert_score_event(
        conn,
        user_id,
        attempt["avatar_name"],
        question,
        attempt["attempt_id"],
        now,
        submitted_score=submitted_score,
    )
    _execute(
        conn,
        "UPDATE attempts SET score_awarded=%s, progress_applied=1 WHERE attempt_id=%s",
        (score_delta, attempt["attempt_id"]),
    )


def _insert_score_event(
    conn: Any,
    user_id: str,
    display_name: str,
    question: dict[str, Any],
    attempt_id: str,
    now: str,
    *,
    submitted_score: float | None = None,
) -> float:
    """Insert or improve one best-score event and return leaderboard delta.

    The legacy function name is retained because existing hardening tests and
    operational tooling monkeypatch it to verify transaction rollback.
    """

    score = float(question.get("max_score") or 100.0) if submitted_score is None else float(submitted_score)
    event_key = f"{user_id}:{question['id']}"
    select_sql = "SELECT * FROM score_events WHERE user_id=%s AND question_id=%s"
    if DB_ENGINE != "sqlite":
        select_sql += " FOR UPDATE"
    existing = _row(_execute(conn, select_sql, (user_id, question["id"])).fetchone())

    if not existing:
        if DB_ENGINE == "sqlite":
            cursor = _execute(
                conn,
                """
                INSERT OR IGNORE INTO score_events (
                    score_event_key,user_id,display_name,question_id,attempt_id,score_awarded,created_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (event_key, user_id, display_name, question["id"], attempt_id, score, now),
            )
        else:
            cursor = _execute(
                conn,
                """
                INSERT IGNORE INTO score_events (
                    score_event_key,user_id,display_name,question_id,attempt_id,score_awarded,created_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,
                (event_key, user_id, display_name, question["id"], attempt_id, score, now),
            )
        if cursor.rowcount == 1:
            return score
        existing = _row(_execute(conn, select_sql, (user_id, question["id"])).fetchone()) or {}

    previous = float(existing.get("score_awarded") or 0.0)
    if score > previous:
        _execute(
            conn,
            """
            UPDATE score_events SET display_name=%s, attempt_id=%s, score_awarded=%s, created_at=%s
            WHERE user_id=%s AND question_id=%s
            """,
            (display_name, attempt_id, score, now, user_id, question["id"]),
        )
        return round(score - previous, 2)

    if display_name != existing.get("display_name"):
        _execute(
            conn,
            "UPDATE score_events SET display_name=%s WHERE user_id=%s AND question_id=%s",
            (display_name, user_id, question["id"]),
        )
    return 0.0


def get_executions(attempt_id: str) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = _execute(conn, "SELECT * FROM attempt_executions WHERE attempt_id=%s ORDER BY id", (attempt_id,)).fetchall()
    result = []
    for raw in rows:
        item = dict(raw)
        for field in ("return_value", "feedback", "normalized_result", "evaluation_result"):
            item[field] = _decode_json(item.get(field), {} if field != "return_value" else None)
        result.append(item)
    return result


def get_progress(user_id: str) -> list[dict[str, Any]]:
    with connection() as conn:
        rows = _execute(conn, """
            SELECT q.question_code, q.title, q.scene, q.difficulty, p.is_completed,
                   p.best_score, p.first_completed_at, p.last_attempt_at, p.attempt_count
            FROM questions q LEFT JOIN user_progress p ON p.question_id=q.id AND p.user_id=%s
            WHERE q.is_active=1 ORDER BY q.id
        """, (user_id,)).fetchall()
    result = [dict(row) for row in rows]
    for item in result:
        item["question_code"] = _canonical_question_code(item.get("question_code"))
    return result


def get_leaderboard() -> list[dict[str, Any]]:
    with connection() as conn:
        rows = _execute(conn, """
            SELECT p.user_id, MAX(p.display_name) AS display_name,
                   SUM(p.best_score) AS total_score,
                   SUM(CASE WHEN p.is_completed=1 THEN 1 ELSE 0 END) AS completed_questions,
                   SUM(CASE WHEN p.best_score >= q.max_score THEN 1 ELSE 0 END) AS correct_questions,
                   MAX(p.last_attempt_at) AS last_updated,
                   MAX(p.last_attempt_at) AS reached_current_score_at
            FROM user_progress p JOIN questions q ON q.id=p.question_id
            WHERE q.is_active=1 AND p.is_completed=1
            GROUP BY p.user_id
            ORDER BY total_score DESC, completed_questions DESC,
                     reached_current_score_at ASC, p.user_id ASC
        """).fetchall()
    result = []
    for rank, row in enumerate(rows, 1):
        item = dict(row)
        item["rank"] = rank
        result.append(item)
    return result


def seed_question(question: Any) -> None:
    """Seed one registry definition without mutating an already-hashed version."""

    now = _utcnow()
    test_config = {
        "generated_by": question.code,
        "version": question.version,
        "source_document": question.source_document,
    }
    evaluation_config = {
        "learning_objectives": list(question.learning_objectives),
        "input_format": list(question.input_format),
        "output_format": list(question.output_format),
        "evaluation_adapter": question.evaluation_adapter,
        "required_function": question.required_function,
        "required_technique": question.required_technique,
    }
    animation_config = {
        "adapter": question.animation_adapter,
        "scene": question.scene_code,
    }
    version_payload = {
        "question_code": question.code,
        "version": question.version,
        "starter_code": question.starter_code,
        "test_config": test_config,
        "evaluation_config": evaluation_config,
        "animation_config": animation_config,
        "metadata": question.metadata,
    }
    config_hash = hashlib.sha256(
        json.dumps(version_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    with connection() as conn:
        existing = _row(_execute(conn, "SELECT * FROM questions WHERE question_code=%s", (question.code,)).fetchone())
        values = (
            question.semantic_code, question.title, question.scene_code, question.level,
            question.question_type, question.required_technique, question.max_score,
            _bool_db(question.active), question.lifecycle_status, question.replacement_status,
            question.contract_version, question.source_document, _json(question.metadata), now,
        )
        if existing:
            _execute(conn, """
                UPDATE questions SET semantic_code=%s,title=%s,scene=%s,difficulty=%s,
                    question_type=%s,required_technique=%s,max_score=%s,is_active=%s,
                    lifecycle_status=%s,replacement_status=%s,contract_version=%s,
                    source_document=%s,contract_metadata=%s,updated_at=%s
                WHERE id=%s
            """, values + (existing["id"],))
            question_id = existing["id"]
        else:
            cursor = _execute(conn, """
                INSERT INTO questions (
                    question_code,semantic_code,title,scene,difficulty,question_type,
                    required_technique,max_score,is_active,lifecycle_status,replacement_status,
                    contract_version,source_document,contract_metadata,created_at,updated_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (question.code,) + values[:-1] + (now, now))
            question_id = cursor.lastrowid

        version = _row(_execute(
            conn,
            "SELECT id,config_hash FROM question_versions WHERE question_id=%s AND version=%s",
            (question_id, question.version),
        ).fetchone())
        version_values = (
            question.starter_code, _json(test_config), _json(evaluation_config),
            _json(animation_config), config_hash,
        )
        if version:
            stored_hash = version.get("config_hash")
            if stored_hash and stored_hash != config_hash:
                raise RuntimeError(
                    f"Question version collision for {question.code} v{question.version}: config hash differs."
                )
            version_id = version["id"]
            if not stored_hash:
                _execute(conn, """
                    UPDATE question_versions SET starter_code=%s,test_config=%s,
                        evaluation_config=%s,animation_config=%s,config_hash=%s
                    WHERE id=%s
                """, version_values + (version_id,))
        else:
            cursor = _execute(conn, """
                INSERT INTO question_versions (
                    question_id,version,starter_code,test_config,evaluation_config,
                    animation_config,config_hash,created_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                question_id, question.version, question.starter_code, _json(test_config),
                _json(evaluation_config), _json(animation_config), config_hash, now,
            ))
            version_id = cursor.lastrowid
        _execute(conn, "UPDATE questions SET current_version_id=%s WHERE id=%s", (version_id, question_id))


def get_question_inventory() -> list[dict[str, Any]]:
    with connection() as conn:
        rows = _execute(conn, """
            SELECT question_code,semantic_code,title,scene,difficulty,question_type,
                   required_technique,max_score,is_active,lifecycle_status,replacement_status,
                   contract_version,source_document,current_version_id
            FROM questions ORDER BY id
        """).fetchall()
    result = [dict(row) for row in rows]
    for item in result:
        item["question_code"] = _canonical_question_code(item.get("question_code"))
        item["replacement_status"] = _canonical_replacement_status(item.get("replacement_status"))
    return result


def get_question_metrics() -> dict[str, int]:
    with connection() as conn:
        row = _row(_execute(conn, """
            SELECT
                SUM(CASE WHEN is_active=1 THEN 1 ELSE 0 END) AS active_question_count,
                SUM(CASE WHEN is_active=1 AND lifecycle_status='FINAL' THEN 1 ELSE 0 END) AS final_contract_count,
                SUM(CASE WHEN is_active=1 AND lifecycle_status='LEGACY' THEN 1 ELSE 0 END) AS legacy_active_count,
                SUM(CASE WHEN is_active=1 AND difficulty='EXTREME' THEN 1 ELSE 0 END) AS active_extreme_count,
                SUM(CASE WHEN is_active=1 AND difficulty='EXTREME' AND lifecycle_status='FINAL' THEN 1 ELSE 0 END) AS final_extreme_count,
                SUM(CASE WHEN is_active=1 AND difficulty='EXTREME' AND lifecycle_status='LEGACY' THEN 1 ELSE 0 END) AS legacy_extreme_count,
                SUM(CASE WHEN lifecycle_status='BLOCKED' OR replacement_status LIKE 'BLOCKED%%' THEN 1 ELSE 0 END) AS blocked_question_count
            FROM questions
        """).fetchone()) or {}
    return {key: int(value or 0) for key, value in row.items()}

def get_question_record(question_code: str) -> dict[str, Any] | None:
    with connection() as conn:
        for code in _question_code_candidates(question_code):
            row = _row(_execute(conn, "SELECT * FROM questions WHERE question_code=%s LIMIT 1", (code,)).fetchone())
            if row:
                row["question_code"] = _canonical_question_code(row.get("question_code"))
                return row
    return None


def create_animation_event(record: dict[str, Any]) -> None:
    with connection() as conn:
        _execute(conn, """
            INSERT INTO animation_events (
                animation_run_id, attempt_id, execution_id, animation_case_id,
                question_code, test_id, visible_test_id, scene, payload,
                selected_behavior, status, sent_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'SENT',%s)
        """, (
            record["animation_run_id"], record["attempt_id"], record["execution_id"],
            record["animation_case_id"], _canonical_question_code(record["question_code"]), record["test_id"],
            record.get("visible_test_id") or record["test_id"], record["scene"], record["payload"],
            _json(record.get("selected_behavior", {})), _utcnow(),
        ))


def get_animation_event(animation_run_id: str) -> dict[str, Any] | None:
    mark_animation_timeouts()
    with connection() as conn:
        row = _row(_execute(conn, "SELECT * FROM animation_events WHERE animation_run_id=%s", (animation_run_id,)).fetchone())
    if row:
        row["selected_behavior"] = _decode_json(row.get("selected_behavior"), {})
        row["question_code"] = _canonical_question_code(row.get("question_code"))
    return row


def acknowledge_animation(animation_run_id: str, scene: str | None = None) -> dict[str, Any]:
    now = _utcnow()
    with connection() as conn:
        event = _row(_execute(conn, "SELECT * FROM animation_events WHERE animation_run_id=%s", (animation_run_id,)).fetchone())
        if not event:
            return {"status": "UNKNOWN", "animation_run_id": animation_run_id}
        if scene and event["scene"] != scene:
            return {"status": "SCENE_MISMATCH", "animation_run_id": animation_run_id}
        if event["status"] == "ACKNOWLEDGED":
            return {"status": "DUPLICATE", "animation_run_id": animation_run_id}
        if event["status"] == "TIMEOUT":
            return {"status": "LATE", "animation_run_id": animation_run_id}
        if event["status"] == "CANCELLED":
            return {"status": "CANCELLED_IGNORED", "animation_run_id": animation_run_id}
        if event["status"] == "FAILED":
            return {"status": "FAILED_IGNORED", "animation_run_id": animation_run_id}
        _execute(conn, "UPDATE animation_events SET status='ACKNOWLEDGED', acknowledged_at=%s WHERE animation_run_id=%s AND status='SENT'", (now, animation_run_id))
    return {"status": "ACKNOWLEDGED", "animation_run_id": animation_run_id}


def cancel_animation_event(animation_run_id: str, reason: str = "SCENE_CANCELLED") -> dict[str, Any]:
    with connection() as conn:
        event = _row(_execute(conn, "SELECT * FROM animation_events WHERE animation_run_id=%s", (animation_run_id,)).fetchone())
        if not event:
            return {"status": "UNKNOWN", "animation_run_id": animation_run_id}
        if event["status"] != "SENT":
            return {"status": event["status"], "animation_run_id": animation_run_id}
        _execute(conn, "UPDATE animation_events SET status='CANCELLED',failed_at=%s,failure_reason=%s WHERE animation_run_id=%s AND status='SENT'", (_utcnow(), reason, animation_run_id))
    return {"status": "CANCELLED", "animation_run_id": animation_run_id}

def mark_animation_timeouts() -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=ANIMATION_ACK_TIMEOUT_SECONDS)).replace(tzinfo=None, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    with connection() as conn:
        cursor = _execute(conn, "UPDATE animation_events SET status='TIMEOUT', failed_at=%s, failure_reason='ACK_TIMEOUT' WHERE status='SENT' AND sent_at < %s", (_utcnow(), cutoff))
        return cursor.rowcount


def get_station(station_code: str = STATION_CODE) -> dict[str, Any]:
    with connection() as conn:
        row = _row(_execute(conn, "SELECT * FROM station_state WHERE station_code=%s LIMIT 1", (station_code,)).fetchone())
        if row is None:
            _execute(conn, "INSERT INTO station_state (station_code,status,state_version) VALUES (%s,'IDLE',1)", (station_code,))
            row = {"station_code": station_code, "status": "IDLE", "state_version": 1}
    if row.get("active_question_code"):
        row["active_question_code"] = _canonical_question_code(row["active_question_code"])
    return row


def update_station(station_code: str = STATION_CODE, **fields: Any) -> dict[str, Any]:
    if fields.get("active_question_code"):
        fields["active_question_code"] = _canonical_question_code(fields["active_question_code"])
    allowed = {"active_avatar_uuid","active_avatar_name","active_level","active_question_code","active_scene_code","active_attempt_id","active_animation_run_id","status"}
    invalid = set(fields) - allowed
    if invalid:
        raise ValueError(f"Unsupported station fields: {sorted(invalid)}")
    with connection() as conn:
        existing = _row(_execute(conn, "SELECT station_code FROM station_state WHERE station_code=%s", (station_code,)).fetchone())
        if not existing:
            _execute(conn, "INSERT INTO station_state (station_code,status,state_version) VALUES (%s,'IDLE',0)", (station_code,))
        assignments = [f"{name}=%s" for name in fields] + ["state_version=state_version+1", "updated_at=%s"]
        params = tuple(fields.values()) + (_utcnow(), station_code)
        _execute(conn, f"UPDATE station_state SET {', '.join(assignments)} WHERE station_code=%s", params)
    return get_station(station_code)


def expire_finished_station(
    max_age_seconds: int,
    station_code: str = STATION_CODE,
) -> dict[str, Any]:
    """Atomically return an old FINISHED station to an anonymous IDLE state.

    The conditional UPDATE prevents an old polling request from erasing a new
    player session that started at the same moment the timeout expired.
    """

    timeout = max(1, int(max_age_seconds))
    cutoff = (
        datetime.now(timezone.utc) - timedelta(seconds=timeout)
    ).replace(tzinfo=None, microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    now = _utcnow()

    with connection() as conn:
        _execute(
            conn,
            """
            UPDATE station_state
            SET active_avatar_uuid=NULL,
                active_avatar_name=NULL,
                active_level=NULL,
                active_question_code=NULL,
                active_scene_code=NULL,
                active_attempt_id=NULL,
                active_animation_run_id=NULL,
                status='IDLE',
                state_version=state_version+1,
                updated_at=%s
            WHERE station_code=%s
              AND status='FINISHED'
              AND updated_at <= %s
            """,
            (now, station_code, cutoff),
        )
    return get_station(station_code)


def _json(value: Any) -> str:
    return json.dumps(_json_safe(value), ensure_ascii=False, separators=(",", ":"))


def _json_safe(value: Any, depth: int = 0) -> Any:
    if depth > 16:
        return {"__truncated__": True}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_json_safe(item, depth + 1) for item in list(value)[:2000]]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 2000:
                result["__truncated__"] = True
                break
            safe_key = key if isinstance(key, str) else repr(key)[:200]
            result[safe_key] = _json_safe(item, depth + 1)
        return result
    return {"__python_type__": type(value).__name__, "repr": repr(value)[:1000]}


def _decode_json(value: Any, fallback: Any) -> Any:
    if value in (None, ""):
        return fallback
    if isinstance(value, (dict, list, int, float, bool)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _bool_db(value: Any) -> int:
    return 1 if bool(value) else 0
