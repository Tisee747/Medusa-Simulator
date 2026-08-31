"""FastAPI entry point for the Algorithm Simulator backend."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app.config import LOG_LEVEL, PUBLIC_BASE_URL, STATION_CODE, STATION_FINISHED_AUTO_HOME_SECONDS
from app.database import (
    acknowledge_animation,
    cancel_animation_event,
    create_attempt,
    get_attempt,
    get_leaderboard,
    get_question_inventory,
    get_question_metrics,
    get_progress,
    get_station,
    expire_finished_station,
    mark_animation_timeouts,
    ping_database,
    update_station,
)
from app.ids import new_attempt_id
from app.editor_content import get_editor_guide
from app.questions.registry import (
    LEVEL_DESCRIPTIONS,
    LEVEL_ORDER,
    QUESTION_LOAD_ERRORS,
    QUESTIONS,
    get_question,
    questions_for_level,
    registry_status,
)
from app.services.animation import create_animation
from app.services.attempts import check_attempt, evaluate_attempt

logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger("simulator")
APP_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("question_registry active=%s errors=%s", len(QUESTIONS), QUESTION_LOAD_ERRORS)
    yield


app = FastAPI(title="Algorithm Simulator", version="3.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
templates = Jinja2Templates(directory=APP_DIR / "templates")


class RunPayload(BaseModel):
    source_code: str = Field(min_length=1, max_length=50000)
    submission_id: str | None = Field(default=None, min_length=8, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")


class PreviewPayload(BaseModel):
    test_id: str | None = None


class AckPayload(BaseModel):
    message: str


def _new_attempt(question_code: str, avatar_uuid: str, avatar_name: str) -> dict[str, Any]:
    question = get_question(question_code)
    attempt_id = new_attempt_id(question.code)
    record = {
        "attempt_id": attempt_id,
        "question_code": question.code,
        "scene_code": question.scene_code,
        "avatar_uuid": avatar_uuid or "UNKNOWN",
        "avatar_name": avatar_name or "Player",
        "input_data": question.create_attempt_data(),
        "expected_output": "Generated and validated by the question module.",
    }
    create_attempt(record)
    return record


def _page_url(status: str, attempt_id: str | None = None, level: str | None = None) -> str:
    if status == "SELECT_LEVEL":
        return f"{PUBLIC_BASE_URL}/levels"
    if status == "SELECT_QUESTION" and level:
        return f"{PUBLIC_BASE_URL}/questions/{level.lower()}"
    if status == "QUESTION_OVERVIEW" and attempt_id:
        return f"{PUBLIC_BASE_URL}/question/{attempt_id}"
    if status in {"CODING", "WRONG"} and attempt_id:
        return f"{PUBLIC_BASE_URL}/editor/{attempt_id}"
    if status in {"READY_TO_PLAY", "SCORE_READY"} and attempt_id:
        return f"{PUBLIC_BASE_URL}/success/{attempt_id}"
    if status == "FINISHED" and attempt_id:
        return f"{PUBLIC_BASE_URL}/finished/{attempt_id}"
    return f"{PUBLIC_BASE_URL}/monitor-home"


def _station_pipe(state: dict[str, Any]) -> str:
    status = state.get("status") or "IDLE"
    level = state.get("active_level") or ""
    attempt_id = state.get("active_attempt_id") or ""
    return "|".join([
        "STATE", str(state.get("state_version", 0)), status, level,
        state.get("active_question_code") or "", state.get("active_scene_code") or "",
        attempt_id, _page_url(status, attempt_id, level),
    ])


@app.get("/health", response_class=PlainTextResponse)
def health() -> str:
    return "OK|DB_OK" if ping_database() else "ERROR|DB_DOWN"


@app.get("/api/questions/status")
def question_status() -> dict[str, Any]:
    status = registry_status()
    status["database_counts"] = get_question_metrics()
    status["database_inventory"] = get_question_inventory()
    return status


def _student_progress_context(user_id: str | None) -> dict[str, Any]:
    if not user_id or user_id == "UNKNOWN":
        return {
            "progress_by_code": {},
            "attempted_count": 0,
            "total_score": 0.0,
            "question_count": len(QUESTIONS),
        }
    items = get_progress(user_id)
    progress_by_code = {item["question_code"]: item for item in items}
    return {
        "progress_by_code": progress_by_code,
        "attempted_count": sum(1 for item in items if item.get("is_completed")),
        "total_score": round(sum(float(item.get("best_score") or 0.0) for item in items), 1),
        "question_count": len(items),
    }


def _attempt_page_context(attempt: dict[str, Any]) -> dict[str, Any]:
    question = get_question(attempt["question_code"])
    progress = _student_progress_context(attempt.get("avatar_uuid"))
    best = progress["progress_by_code"].get(question.code, {})
    evaluation = attempt.get("evaluation_data") or {}
    return {
        "attempt": attempt,
        "question": question,
        "evaluation": evaluation,
        "score_breakdown": evaluation.get("score_breakdown") or [],
        "best_score": float(best.get("best_score") or attempt.get("score") or 0.0),
        "animation_available": bool(attempt.get("completed_at") and attempt.get("result_status") != "ERROR"),
    }


@app.get("/monitor-home", response_class=HTMLResponse)
def monitor_home(request: Request) -> HTMLResponse:
    # The waiting screen is intentionally anonymous. The next player is not
    # known until START is pressed on the physical control panel.
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={"station_code": STATION_CODE},
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.get("/leaderboard", response_class=HTMLResponse)
def leaderboard_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="leaderboard.html",
        context={"refresh_seconds": 30},
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@app.get("/levels", response_class=HTMLResponse)
def levels(request: Request) -> HTMLResponse:
    state = get_station()
    progress = _student_progress_context(state.get("active_avatar_uuid"))
    level_counts = {level: len(questions_for_level(level)) for level in LEVEL_ORDER}
    return templates.TemplateResponse(
        request=request,
        name="levels.html",
        context={
            "levels": LEVEL_ORDER,
            "descriptions": LEVEL_DESCRIPTIONS,
            "level_counts": level_counts,
            **progress,
        },
    )


@app.post("/select-level")
def select_level(level: str = Form(...)) -> RedirectResponse:
    normalized = level.upper()
    if normalized not in LEVEL_ORDER:
        raise HTTPException(status_code=400, detail="Unknown difficulty.")
    update_station(active_level=normalized, active_question_code=None, active_scene_code=None, active_attempt_id=None, active_animation_run_id=None, status="SELECT_QUESTION")
    return RedirectResponse(url=f"/questions/{normalized.lower()}", status_code=303)


@app.get("/questions/{level}", response_class=HTMLResponse)
def question_list(request: Request, level: str) -> HTMLResponse:
    normalized = level.upper()
    questions = questions_for_level(normalized)
    if not questions:
        raise HTTPException(status_code=404, detail="Difficulty not found.")
    state = get_station()
    progress = _student_progress_context(state.get("active_avatar_uuid"))
    return templates.TemplateResponse(
        request=request,
        name="questions.html",
        context={
            "level": normalized,
            "description": LEVEL_DESCRIPTIONS[normalized],
            "questions": questions,
            **progress,
        },
    )


@app.post("/select-question")
def select_question(question_code: str = Form(...)) -> RedirectResponse:
    state = get_station()
    try:
        question = get_question(question_code)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    record = _new_attempt(question.code, state.get("active_avatar_uuid") or "UNKNOWN", state.get("active_avatar_name") or "Player")
    update_station(active_level=question.level, active_question_code=question.code, active_scene_code=question.scene_code, active_attempt_id=record["attempt_id"], active_animation_run_id=None, status="QUESTION_OVERVIEW")
    return RedirectResponse(url=f"/question/{record['attempt_id']}", status_code=303)


@app.get("/question/{attempt_id}", response_class=HTMLResponse)
def question_overview(request: Request, attempt_id: str) -> HTMLResponse:
    attempt = get_attempt(attempt_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found.")
    question = get_question(attempt["question_code"])
    return templates.TemplateResponse(
        request=request,
        name="question_overview.html",
        context={
            "attempt": attempt,
            "question": question,
            "guide": get_editor_guide(question.code),
            "cases": question.visible_cases(attempt["input_data"]),
        },
    )


@app.post("/start-coding/{attempt_id}")
def start_coding(attempt_id: str) -> RedirectResponse:
    attempt = get_attempt(attempt_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found.")
    state = get_station()
    if _submission_matches_active_station(state, attempt, attempt_id):
        update_station(active_attempt_id=attempt_id, status="CODING")
    return RedirectResponse(url=f"/editor/{attempt_id}", status_code=303)


@app.get("/editor/{attempt_id}", response_class=HTMLResponse)
def editor(request: Request, attempt_id: str) -> HTMLResponse:
    attempt = get_attempt(attempt_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found.")
    question = get_question(attempt["question_code"])
    progress = _student_progress_context(attempt.get("avatar_uuid"))
    current_progress = progress["progress_by_code"].get(question.code, {})
    return templates.TemplateResponse(
        request=request,
        name="editor.html",
        context={
            "attempt": attempt,
            "question": question,
            "guide": get_editor_guide(question.code),
            "source_code": attempt.get("source_code") or question.starter_code,
            "cases": question.visible_cases(attempt["input_data"]),
            "best_score": float(current_progress.get("best_score") or 0.0),
        },
    )


def _submission_matches_active_station(
    state: dict[str, Any],
    stored_attempt: dict[str, Any],
    requested_attempt_id: str,
) -> bool:
    """Keep PLAY attached to the submission from the active avatar/question.

    A browser can still hold an older editor attempt while Firestorm already
    points at a newer draft for the same avatar and canonical question. The
    successful RUN/SUBMIT must promote the persisted attempt to the station so
    PLAY does not remain attached to an unfinished draft.
    """

    if state.get("active_attempt_id") == requested_attempt_id:
        return True
    return bool(
        state.get("active_avatar_uuid")
        and state.get("active_avatar_uuid") == stored_attempt.get("avatar_uuid")
        and state.get("active_question_code") == stored_attempt.get("question_code")
    )


def _evaluation_payload(result: Any, *, attempt_id: str, submission_id: str | None = None, score_awarded: float = 0.0, redirect_url: str = "", submitted: bool = False) -> dict[str, Any]:
    return {
        "attempt_id": attempt_id,
        "submission_id": submission_id,
        "submitted": submitted,
        "status": result.status,
        "score": result.score,
        "functional_score": result.functional_score,
        "score_breakdown": result.score_breakdown,
        "score_awarded": score_awarded,
        "behavior_correct": result.behavior_correct,
        "technique_result": result.technique_result.to_dict(),
        "overall_correct": result.overall_correct,
        "message": result.message,
        "error_message": result.error_message,
        "program_output": result.program_output,
        "visible_results": result.visible_results,
        "hidden_summary": result.hidden_summary,
        "redirect_url": redirect_url,
        "animation_available": result.status != "ERROR",
    }


@app.post("/api/attempt/{attempt_id}/check")
def check_attempt_endpoint(attempt_id: str, payload: RunPayload) -> JSONResponse:
    if not get_attempt(attempt_id):
        raise HTTPException(status_code=404, detail="Attempt not found.")
    try:
        result = check_attempt(attempt_id, payload.source_code)
    except Exception as exc:
        logger.exception("draft check failed attempt_id=%s", attempt_id)
        raise HTTPException(status_code=500, detail="The answer could not be checked. Please try again.") from exc
    return JSONResponse(_evaluation_payload(result, attempt_id=attempt_id, submitted=False))


@app.post("/api/attempt/{attempt_id}/run")
def run_attempt(attempt_id: str, payload: RunPayload) -> JSONResponse:
    if not get_attempt(attempt_id):
        raise HTTPException(status_code=404, detail="Attempt not found.")
    try:
        stored, result = evaluate_attempt(attempt_id, payload.source_code, payload.submission_id)
    except Exception as exc:
        logger.exception("attempt evaluation failed attempt_id=%s", attempt_id)
        raise HTTPException(status_code=500, detail="The answer could not be submitted. Please try again.") from exc

    state = get_station()
    animation_available = result.status != "ERROR"
    station_status = "READY_TO_PLAY" if animation_available else "SCORE_READY"
    if _submission_matches_active_station(state, stored, attempt_id):
        update_station(
            active_attempt_id=stored["attempt_id"],
            active_animation_run_id=None,
            status=station_status,
        )
    redirect_url = f"/success/{stored['attempt_id']}"
    return JSONResponse(_evaluation_payload(
        result,
        attempt_id=stored["attempt_id"],
        submission_id=stored.get("client_submission_id"),
        score_awarded=float(stored.get("score_awarded") or 0),
        redirect_url=redirect_url,
        submitted=True,
    ))


@app.post("/api/attempt/{attempt_id}/preview")
def preview_attempt(attempt_id: str, payload: PreviewPayload) -> dict[str, Any]:
    try:
        event = create_animation(attempt_id, mode="PREVIEW", selected_test_id=payload.test_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Attempt not found.") from exc
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    update_station(active_animation_run_id=event["animation_run_id"], status="ANIMATING")
    return event


@app.post("/api/attempt/{attempt_id}/final-play")
def final_play(attempt_id: str) -> dict[str, Any]:
    try:
        event = create_animation(attempt_id, mode="FINAL")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Attempt not found.") from exc
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    update_station(active_animation_run_id=event["animation_run_id"], status="ANIMATING")
    return event


@app.get("/api/progress/{user_id}")
def progress(user_id: str) -> dict[str, Any]:
    return {"user_id": user_id, "questions": get_progress(user_id)}


@app.get("/api/leaderboard")
def leaderboard() -> JSONResponse:
    metrics = get_question_metrics()
    public_entries = []
    for item in get_leaderboard()[:10]:
        completed = int(item.get("completed_questions") or 0)
        public_entries.append({
            "rank": int(item.get("rank") or 0),
            "avatar_name": item.get("display_name") or "Player",
            "display_name": item.get("display_name") or "Player",
            "total_score": float(item.get("total_score") or 0),
            "completed_question_count": completed,
            "completed_questions": completed,
            "correct_question_count": int(item.get("correct_questions") or completed),
            "last_updated": jsonable_encoder(item.get("last_updated")),
        })
    return JSONResponse(
        {
            "entries": public_entries,
            "active_questions": metrics["active_question_count"],
            **metrics,
        },
        headers={"Cache-Control": "no-store, max-age=0", "Pragma": "no-cache"},
    )


@app.get("/success/{attempt_id}", response_class=HTMLResponse)
def success(request: Request, attempt_id: str) -> HTMLResponse:
    attempt = get_attempt(attempt_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found.")
    return templates.TemplateResponse(request=request, name="success.html", context=_attempt_page_context(attempt))


@app.get("/finished/{attempt_id}", response_class=HTMLResponse)
def finished(request: Request, attempt_id: str) -> HTMLResponse:
    attempt = get_attempt(attempt_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found.")
    return templates.TemplateResponse(request=request, name="finished.html", context=_attempt_page_context(attempt))


@app.get("/api/station/start", response_class=PlainTextResponse)
def station_start(avatar_uuid: str = Query(...), avatar_name: str = Query("Player")) -> str:
    return _station_pipe(update_station(active_avatar_uuid=avatar_uuid, active_avatar_name=avatar_name, active_level=None, active_question_code=None, active_scene_code=None, active_attempt_id=None, active_animation_run_id=None, status="SELECT_LEVEL"))


@app.get("/api/station/state", response_class=PlainTextResponse)
def station_state() -> str:
    mark_animation_timeouts()
    state = expire_finished_station(STATION_FINISHED_AUTO_HOME_SECONDS)
    return _station_pipe(state)


@app.get("/api/station/play", response_class=PlainTextResponse)
def station_play() -> str:
    state = get_station()
    attempt_id = state.get("active_attempt_id")
    if not attempt_id:
        return "ERROR|NO_ATTEMPT"
    try:
        event = create_animation(attempt_id, mode="FINAL")
    except PermissionError:
        return "ERROR|ANSWER_NOT_READY"
    except (KeyError, ValueError) as exc:
        logger.warning("station play failed: %s", exc)
        return "ERROR|ANIMATION_NOT_AVAILABLE"
    update_station(active_animation_run_id=event["animation_run_id"], status="ANIMATING")
    return event["payload"]


@app.api_route("/api/animation/ack", methods=["GET", "POST"])
async def animation_ack(request: Request, message: str | None = Query(None)) -> dict[str, Any]:
    if message is None:
        try:
            body = await request.json()
            message = body.get("message", "")
        except Exception:
            message = (await request.body()).decode("utf-8", errors="replace")
    parts = (message or "").strip().split("|")
    if not parts or parts[0] != "ANIMATION_DONE" or len(parts) not in {2, 3}:
        raise HTTPException(status_code=400, detail="Format ACK tidak valid.")
    if len(parts) == 2:
        scene = None
        animation_run_id = parts[1]
    else:
        scene = parts[1]
        animation_run_id = parts[2]
    if not animation_run_id:
        raise HTTPException(status_code=400, detail="animation_run_id kosong.")
    result = acknowledge_animation(animation_run_id, scene)
    if result["status"] == "ACKNOWLEDGED":
        state = get_station()
        if state.get("active_animation_run_id") == animation_run_id:
            update_station(status="FINISHED")
    if result["status"] == "UNKNOWN":
        logger.warning("unknown animation ack id=%s scene=%s", animation_run_id, scene)
    return result


@app.get("/api/station/reset", response_class=PlainTextResponse)
def station_reset() -> str:
    state = get_station()
    if state.get("active_animation_run_id"):
        cancel_animation_event(state["active_animation_run_id"], "STATION_RESET")
        update_station(active_animation_run_id=None, status="CODING" if state.get("active_attempt_id") else "IDLE")
    return "|".join(["RESET", state.get("active_question_code") or "", state.get("active_scene_code") or "", state.get("active_attempt_id") or ""])


@app.get("/api/station/new-question", response_class=PlainTextResponse)
def station_new_question() -> str:
    state = get_station()
    code = state.get("active_question_code")
    if not code:
        return "ERROR|NO_ACTIVE_QUESTION"
    question = get_question(code)
    if state.get("active_animation_run_id"):
        cancel_animation_event(state["active_animation_run_id"], "NEW_QUESTION")
    record = _new_attempt(code, state.get("active_avatar_uuid") or "UNKNOWN", state.get("active_avatar_name") or "Player")
    updated = update_station(active_attempt_id=record["attempt_id"], active_animation_run_id=None, status="CODING")
    return "|".join(["NEW", question.code, question.scene_code, record["attempt_id"], _page_url("CODING", record["attempt_id"], question.level), str(updated.get("state_version", 0))])


@app.get("/api/station/finish", response_class=PlainTextResponse)
def station_finish(attempt_id: str = Query(...)) -> str:
    state = get_station()
    if state.get("active_attempt_id") != attempt_id:
        return "ERROR|ATTEMPT_MISMATCH"
    return _station_pipe(update_station(status="FINISHED"))


@app.get("/api/station/home", response_class=PlainTextResponse)
def station_home() -> str:
    state = get_station()
    if state.get("active_animation_run_id"):
        cancel_animation_event(state["active_animation_run_id"], "STATION_HOME")
    return _station_pipe(update_station(
        active_avatar_uuid=None,
        active_avatar_name=None,
        active_level=None,
        active_question_code=None,
        active_scene_code=None,
        active_attempt_id=None,
        active_animation_run_id=None,
        status="IDLE",
    ))


# Legacy Traffic endpoint kept for existing object compatibility.
@app.get("/api/traffic-light/start", response_class=PlainTextResponse)
def legacy_traffic_start(avatar_uuid: str = Query(...), avatar_name: str = Query("Player")) -> str:
    question = get_question("E01_TRAFFIC")
    record = _new_attempt(question.code, avatar_uuid, avatar_name)
    update_station(active_avatar_uuid=avatar_uuid, active_avatar_name=avatar_name, active_level=question.level, active_question_code=question.code, active_scene_code=question.scene_code, active_attempt_id=record["attempt_id"], active_animation_run_id=None, status="CODING")
    data = record["input_data"]
    first_case = data.get("cases", [{}])[0]
    color = first_case.get("normalized_input_color") or first_case.get("input_data", {}).get("color", "")
    expected = first_case.get("expected_action") or first_case.get("expected", "")
    return f"{record['attempt_id']}|{color}|{expected}|{PUBLIC_BASE_URL}/editor/{record['attempt_id']}"
