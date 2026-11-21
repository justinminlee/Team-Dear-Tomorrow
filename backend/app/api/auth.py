"""Authentication against managed Supabase Auth (auth.users).

Never store user passwords in public.fact_user or issue homemade JWTs.
"""
import os
import re
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

from pathlib import Path
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env", override=True)

router = APIRouter(prefix="/auth", tags=["authentication"])
ACCESS_COOKIE = "dt_access"
REFRESH_COOKIE = "dt_refresh"

class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def settings():
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_ANON_KEY", "")
    if not url or not key:
        raise HTTPException(status_code=503, detail="Supabase Auth is not configured")
    return url, key


def headers(key: str):
    return {"apikey": key, "Content-Type": "application/json"}


async def auth_request(method: str, path: str, *, payload: dict | None = None, access_token: str | None = None):
    url, key = settings()
    req_headers = headers(key)
    if access_token:
        req_headers["Authorization"] = f"Bearer {access_token}"
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            result = await client.request(method, f"{url}/auth/v1/{path}", headers=req_headers, json=payload)
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Authentication service unavailable") from None
    try:
        data = result.json()
    except ValueError:
        data = {}
    return result.status_code, data


def problem(data: dict, fallback: str):
    return str(data.get("msg") or data.get("error_description") or data.get("message") or fallback)


def set_auth_cookies(response: Response, data: dict[str, Any]):
    secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    same_site = os.getenv("COOKIE_SAMESITE", "lax").lower()
    if same_site not in ("lax", "strict", "none") or (same_site == "none" and not secure):
        raise HTTPException(503, "Invalid cookie security configuration")
    access = data.get("access_token")
    refresh = data.get("refresh_token")
    if not access or not refresh:
        raise HTTPException(502, "Authentication service returned no session")
    ttl = max(1, int(data.get("expires_in", 3600)))
    response.set_cookie(ACCESS_COOKIE, access, httponly=True, secure=secure, samesite=same_site, max_age=ttl, path="/")
    response.set_cookie(REFRESH_COOKIE, refresh, httponly=True, secure=secure, samesite=same_site, max_age=60 * 60 * 24 * 30, path="/")


def clear_auth_cookies(response: Response):
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")


def public_user(user: dict):
    metadata = user.get("user_metadata") or {}
    return {"id": user["id"], "email": user.get("email"), "username": metadata.get("username") or metadata.get("display_name") or ""}


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, response: Response):
    if not body.username.strip():
        raise HTTPException(422, "Username cannot be blank")
    if not (re.search(r"[A-Z]", body.password) and re.search(r"[0-9]", body.password) and re.search(r"[^A-Za-z0-9]", body.password)):
        raise HTTPException(422, "Password must include uppercase, number and special character")
    status, data = await auth_request("POST", "signup", payload={
        "email": str(body.email).lower(), "password": body.password,
        "data": {"username": body.username.strip(), "display_name": body.username.strip()},
    })
    if status >= 400:
        message = problem(data, "Unable to register")
        raise HTTPException(409 if status == 422 and "already" in message.lower() else status, message)
    # Supabase may intentionally return an obfuscated user for an existing email.
    # Do not infer uniqueness from user payloads when email confirmations are enabled.
    if data.get("access_token") and data.get("refresh_token"):
        set_auth_cookies(response, data)
        return {"message": "Account created", "requires_email_confirmation": False, "user": public_user(data["user"])}
    return {"message": "Please check your email to confirm your account before signing in", "requires_email_confirmation": True}


@router.post("/login")
async def login(body: LoginRequest, response: Response):
    status, data = await auth_request("POST", "token?grant_type=password", payload={"email": str(body.email).lower(), "password": body.password})
    if status >= 400:
        raise HTTPException(401, "Invalid email or password, or email not yet confirmed")
    set_auth_cookies(response, data)
    return {"user": public_user(data["user"])}


async def current_user(request: Request, response: Response) -> dict:
    """FastAPI dependency: the signed-in Supabase user, or 401.

    Verifies the access cookie with Supabase Auth; if it has expired, uses the
    refresh cookie and sets fresh cookies on the response.
    """
    access = request.cookies.get(ACCESS_COOKIE)
    if access:
        status, data = await auth_request("GET", "user", access_token=access)
        if status == 200 and data.get("id"):
            return public_user(data)
    refresh = request.cookies.get(REFRESH_COOKIE)
    if refresh:
        status, data = await auth_request("POST", "token?grant_type=refresh_token", payload={"refresh_token": refresh})
        if status == 200 and data.get("access_token"):
            set_auth_cookies(response, data)
            return public_user(data["user"])
    clear_auth_cookies(response)
    raise HTTPException(401, "Not authenticated")


@router.get("/me")
async def me(user: dict = Depends(current_user)):
    return {"user": user}


@router.post("/logout")
async def logout(request: Request, response: Response):
    # Reject cross-origin cookie-driven POSTs even if CORS is misconfigured.
    origin = request.headers.get("origin")
    allowed = {s.strip() for s in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")}
    if origin and origin not in allowed:
        raise HTTPException(403, "Origin not allowed")
    access = request.cookies.get(ACCESS_COOKIE)
    if access:
        await auth_request("POST", "logout", access_token=access)
    clear_auth_cookies(response)
    return {"message": "Logged out"}
