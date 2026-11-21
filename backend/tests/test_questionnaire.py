import uuid

import pytest
from fastapi.testclient import TestClient

from app.api import questionnaire as qn
from app.api.auth import current_user
from app.database.session import get_db
from app.main import app
from app.models import DimQuestion

USER = {"id": str(uuid.uuid4()), "email": "t@example.com", "username": "Tester"}


def make_question(code, kind, options=None, order=0):
    return DimQuestion(
        question_id=uuid.uuid4(), question_code=code, category="About You",
        question_text=f"{code}?", response_type=kind, options=options, display_order=order,
    )


AGE = make_question("age", "number", None, 1)
SAT = make_question("satisfaction", "scale", {"min": 1, "max": 10}, 2)
VALUES = make_question("values", "single_choice", ["Freedom", "Family"], 3)
TOPICS = make_question("restricted_topics", "multiple_choice", ["Health", "Finances"], 4)
GOAL = make_question("goal", "text", None, 5)
QUESTIONS = [AGE, SAT, VALUES, TOPICS, GOAL]


# ---------- validate_answer ----------

@pytest.mark.parametrize("question, value, expected", [
    (GOAL, "  Run a company ", "Run a company"),
    (AGE, 27, 27),
    (AGE, 27.0, 27),
    (SAT, 7, 7),
    (VALUES, "Family", "Family"),
    (TOPICS, ["Health", "Health"], ["Health"]),
    (TOPICS, [], []),
    (make_question("b", "boolean"), False, False),
])
def test_valid_answers(question, value, expected):
    assert qn.validate_answer(question, value) == expected


@pytest.mark.parametrize("question, value", [
    (GOAL, "   "),
    (GOAL, 5),
    (GOAL, "x" * (qn.MAX_TEXT_LENGTH + 1)),
    (AGE, "27"),
    (AGE, True),
    (AGE, float("nan")),
    (SAT, 11),
    (SAT, 0),
    (SAT, 6.5),
    (VALUES, "Money"),
    (TOPICS, ["Health", "Aliens"]),
    (TOPICS, "Health"),
    (make_question("b", "boolean"), "yes"),
])
def test_invalid_answers(question, value):
    with pytest.raises(ValueError):
        qn.validate_answer(question, value)


def test_scale_defaults_to_one_to_ten():
    q = qn.serialize_question(make_question("s", "scale", {}))
    assert (q["min"], q["max"]) == (1, 10)


def test_serialize_string_options():
    q = qn.serialize_question(VALUES)
    assert q["options"] == [{"value": "Freedom", "label": "Freedom"}, {"value": "Family", "label": "Family"}]
    assert q["id"] == str(VALUES.question_id)


# ---------- endpoints (DB helpers replaced with fakes) ----------

@pytest.fixture
def client(monkeypatch):
    saved: dict = {}
    latest: dict = {}

    def fake_store(db, user, answers):
        saved.update(answers)
        latest.update(answers)

    monkeypatch.setattr(qn, "load_active_questions", lambda db: QUESTIONS)
    monkeypatch.setattr(qn, "load_latest_answers", lambda db, uid: dict(latest))
    monkeypatch.setattr(qn, "store_answers", fake_store)
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[current_user] = lambda: USER
    yield TestClient(app), saved
    app.dependency_overrides.clear()


def test_get_questionnaire(client):
    c, _ = client
    data = c.get("/questionnaire").json()
    assert [q["code"] for q in data["questions"]] == ["age", "satisfaction", "values", "restricted_topics", "goal"]


def test_save_answers(client):
    c, saved = client
    body = {"answers": {str(AGE.question_id): 27, str(TOPICS.question_id): ["Health"]}}
    r = c.post("/questionnaire/answers", json=body)
    assert r.status_code == 200, r.text
    assert r.json() == {"saved": 2, "unchanged": 0}
    assert saved == {AGE.question_id: 27, TOPICS.question_id: ["Health"]}


def test_resubmitting_same_answers_inserts_nothing(client):
    c, _ = client
    body = {"answers": {str(AGE.question_id): 27}}
    c.post("/questionnaire/answers", json=body)
    assert c.post("/questionnaire/answers", json=body).json() == {"saved": 0, "unchanged": 1}
    body = {"answers": {str(AGE.question_id): 28}}
    assert c.post("/questionnaire/answers", json=body).json() == {"saved": 1, "unchanged": 0}


def test_invalid_answer_saves_nothing(client):
    c, saved = client
    body = {"answers": {str(AGE.question_id): 27, str(SAT.question_id): 99}}
    r = c.post("/questionnaire/answers", json=body)
    assert r.status_code == 422
    assert "satisfaction" in r.text
    assert saved == {}


def test_unknown_question_rejected(client):
    c, saved = client
    r = c.post("/questionnaire/answers", json={"answers": {str(uuid.uuid4()): "x"}})
    assert r.status_code == 422
    assert saved == {}


def test_empty_answers_rejected(client):
    c, _ = client
    assert c.post("/questionnaire/answers", json={"answers": {}}).status_code == 422


def test_get_my_answers(client):
    c, _ = client
    c.post("/questionnaire/answers", json={"answers": {str(VALUES.question_id): "Family"}})
    assert c.get("/questionnaire/answers").json() == {"answers": {str(VALUES.question_id): "Family"}}


def test_answers_require_login():
    c = TestClient(app)
    assert c.post("/questionnaire/answers", json={"answers": {str(AGE.question_id): 1}}).status_code == 401
    assert c.get("/questionnaire/answers").status_code == 401
