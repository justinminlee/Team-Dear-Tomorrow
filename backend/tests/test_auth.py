from fastapi.testclient import TestClient
from app.main import app
from app.api import auth

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_me_unauthenticated():
    assert client.get("/auth/me").status_code == 401


def test_register_rejects_weak_password():
    response = client.post("/auth/register", json={"username": "Test", "email": "test@example.com", "password": "abcdefgh"})
    assert response.status_code == 422


def test_login_sets_cookies(monkeypatch):
    async def fake(method, path, **kwargs):
        return 200, {"access_token": "access", "refresh_token": "refresh", "expires_in": 3600,
                     "user": {"id": "uuid", "email": "t@example.com", "user_metadata": {"username": "Test"}}}
    monkeypatch.setattr(auth, "auth_request", fake)
    response = client.post("/auth/login", json={"email": "t@example.com", "password": "something"})
    assert response.status_code == 200
    assert response.json()["user"]["username"] == "Test"
    assert "httponly" in response.headers["set-cookie"].lower()
