"""Questionnaire: serve questions and save the user's answers.

Questions come from public.dim_question (linked to the active
public.dim_questionnaire). Answers are stored in public.fact_profile_answer as
an append-only history: each save inserts a new row only for answers that
changed, and the latest row per question is the current answer.
"""
import math
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on, insert as pg_insert
from sqlalchemy.orm import Session

from app.api.auth import current_user
from app.database.session import get_db
from app.models import DimQuestion, DimQuestionnaire, DimUserProfile, FactProfileAnswer

router = APIRouter(prefix="/questionnaire", tags=["questionnaire"])

QUESTIONNAIRE_CODE = "future-self"
MAX_TEXT_LENGTH = 2000
DEFAULT_SCALE = (1, 10)


# ---------- Question formatting ----------

def option_list(options: Any) -> list[dict[str, str]] | None:
    """dim_question.options may be ["A", "B"] or [{"value", "label"}]."""
    if not isinstance(options, list):
        return None
    result = []
    for item in options:
        if isinstance(item, str):
            result.append({"value": item, "label": item})
        elif isinstance(item, dict) and item.get("value") is not None:
            value = str(item["value"])
            result.append({"value": value, "label": str(item.get("label") or value)})
    return result


def number_range(question: DimQuestion) -> tuple[float | None, float | None]:
    """min/max from options like {"min": 1, "max": 10}; scales default to 1–10."""
    opts = question.options if isinstance(question.options, dict) else {}
    lo, hi = opts.get("min"), opts.get("max")
    if question.response_type == "scale":
        lo = DEFAULT_SCALE[0] if lo is None else lo
        hi = DEFAULT_SCALE[1] if hi is None else hi
    return lo, hi


def serialize_question(question: DimQuestion) -> dict[str, Any]:
    lo, hi = number_range(question)
    return {
        "id": str(question.question_id),
        "code": question.question_code,
        "category": question.category,
        "text": question.question_text,
        "type": question.response_type,
        "options": option_list(question.options),
        "min": lo,
        "max": hi,
        "order": question.display_order,
    }


# ---------- Answer validation ----------

def validate_answer(question: DimQuestion, value: Any) -> Any:
    """Return the cleaned value to store, or raise ValueError with a reason."""
    kind = question.response_type

    if kind == "text":
        if not isinstance(value, str) or not value.strip():
            raise ValueError("expected non-empty text")
        if len(value) > MAX_TEXT_LENGTH:
            raise ValueError(f"text longer than {MAX_TEXT_LENGTH} characters")
        return value.strip()

    if kind in ("number", "scale"):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError("expected a number")
        if kind == "scale" and value != int(value):
            raise ValueError("expected a whole number")
        lo, hi = number_range(question)
        if (lo is not None and value < lo) or (hi is not None and value > hi):
            raise ValueError(f"expected a value between {lo} and {hi}")
        return int(value) if value == int(value) else value

    if kind == "boolean":
        if not isinstance(value, bool):
            raise ValueError("expected true or false")
        return value

    allowed = {o["value"] for o in option_list(question.options) or []}
    if kind == "single_choice":
        if not isinstance(value, str) or value not in allowed:
            raise ValueError("not one of the options")
        return value

    if kind == "multiple_choice":
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise ValueError("expected a list of options")
        if any(v not in allowed for v in value):
            raise ValueError("contains a value that is not one of the options")
        return list(dict.fromkeys(value))  # drop duplicates, keep order

    raise ValueError(f"unsupported question type '{kind}'")


# ---------- Database access (kept small so tests can replace them) ----------

def load_active_questions(db: Session) -> list[DimQuestion]:
    questionnaire = db.scalars(
        select(DimQuestionnaire)
        .where(DimQuestionnaire.questionnaire_code == QUESTIONNAIRE_CODE, DimQuestionnaire.is_active)
        .order_by(DimQuestionnaire.version.desc())
        .limit(1)
    ).first()
    if questionnaire is None:
        raise HTTPException(404, "No active questionnaire. Run create_tables.py to seed it.")
    return list(db.scalars(
        select(DimQuestion)
        .where(DimQuestion.questionnaire_id == questionnaire.questionnaire_id, DimQuestion.is_active)
        .order_by(DimQuestion.display_order, DimQuestion.question_code)
    ))


def load_latest_answers(db: Session, user_id: uuid.UUID) -> dict[uuid.UUID, Any]:
    rows = db.execute(
        select(FactProfileAnswer.question_id, FactProfileAnswer.answer_value)
        .where(FactProfileAnswer.user_id == user_id)
        .ext(distinct_on(FactProfileAnswer.question_id))
        .order_by(FactProfileAnswer.question_id, FactProfileAnswer.answered_at.desc())
    )
    return {question_id: value for question_id, value in rows}


def store_answers(db: Session, user: dict, answers: dict[uuid.UUID, Any]) -> None:
    user_id = uuid.UUID(user["id"])
    # fact_profile_answer.user_id references dim_user_profile, so the profile
    # row must exist first. No-op if it already does.
    db.execute(
        pg_insert(DimUserProfile)
        .values(user_id=user_id, display_name=user.get("username") or None)
        .on_conflict_do_nothing(index_elements=[DimUserProfile.user_id])
    )
    db.add_all(
        FactProfileAnswer(user_id=user_id, question_id=question_id, answer_value=value)
        for question_id, value in answers.items()
    )
    db.commit()


# ---------- Endpoints ----------

class AnswersRequest(BaseModel):
    # { "<question_id>": <value>, ... }
    answers: dict[uuid.UUID, Any] = Field(min_length=1, max_length=200)


@router.get("")
def get_questionnaire(db: Session = Depends(get_db)):
    return {"questions": [serialize_question(q) for q in load_active_questions(db)]}


@router.get("/answers")
def get_my_answers(user: dict = Depends(current_user), db: Session = Depends(get_db)):
    latest = load_latest_answers(db, uuid.UUID(user["id"]))
    return {"answers": {str(qid): value for qid, value in latest.items()}}


@router.post("/answers")
def save_my_answers(body: AnswersRequest, user: dict = Depends(current_user), db: Session = Depends(get_db)):
    questions = {q.question_id: q for q in load_active_questions(db)}

    cleaned: dict[uuid.UUID, Any] = {}
    errors: list[str] = []
    for question_id, value in body.answers.items():
        question = questions.get(question_id)
        if question is None:
            errors.append(f"{question_id}: unknown or inactive question")
            continue
        try:
            cleaned[question_id] = validate_answer(question, value)
        except ValueError as exc:
            errors.append(f"{question.question_code}: {exc}")
    if errors:
        raise HTTPException(422, {"message": "Some answers are invalid", "errors": errors})

    # Only insert answers that differ from the user's current answer.
    latest = load_latest_answers(db, uuid.UUID(user["id"]))
    changed = {qid: v for qid, v in cleaned.items() if latest.get(qid, object()) != v}
    if changed:
        store_answers(db, user, changed)

    return {"saved": len(changed), "unchanged": len(cleaned) - len(changed)}
