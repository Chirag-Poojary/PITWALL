"""Password hashing, JWT sessions, Google sign-in and role guards."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from . import db

router = APIRouter(prefix="/api/auth", tags=["auth"])

_SECRET_FILE = Path(__file__).resolve().parent.parent / ".jwt_secret"


def _secret() -> str:
    env = os.getenv("JWT_SECRET")
    if env:
        return env
    if not _SECRET_FILE.exists():
        _SECRET_FILE.write_text(secrets.token_urlsafe(48))
    return _SECRET_FILE.read_text().strip()


SECRET = _secret()
TOKEN_DAYS = int(os.getenv("TOKEN_DAYS", "7"))
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ------------------------------------------------------------------ helpers
def hash_password(pw: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 240_000)
    return f"pbkdf2${salt}${dk.hex()}"


def verify_password(pw: str, stored: str | None) -> bool:
    if not stored or not stored.startswith("pbkdf2$"):
        return False
    _, salt, digest = stored.split("$", 2)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 240_000)
    return hmac.compare_digest(dk.hex(), digest)


def make_token(user) -> str:
    payload = {"sub": str(user["id"]), "role": user["role"],
               "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_DAYS)}
    return jwt.encode(payload, SECRET, algorithm="HS256")


def public_user(u) -> dict:
    return {"id": u["id"], "name": u["name"], "email": u["email"], "role": u["role"],
            "provider": u["provider"], "avatar": u["avatar"], "created_at": u["created_at"]}


def session(u) -> dict:
    return {"token": make_token(u), "user": public_user(u)}


def current_user(request: Request):
    h = request.headers.get("Authorization", "")
    if not h.startswith("Bearer "):
        raise HTTPException(401, "Not signed in")
    try:
        payload = jwt.decode(h[7:], SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Session expired, please sign in again")
    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(401, "Invalid token")
    if str(sub).isdigit():
        sub = int(sub)
    u = db.get_user(sub)
    if not u:
        raise HTTPException(401, "Account not found")
    return u


def require_user(u=Depends(current_user)):
    if u["role"] != "user":
        raise HTTPException(403, "This area is for fan accounts. Admins use the analyst dashboard.")
    return u


def require_admin(u=Depends(current_user)):
    if u["role"] != "admin":
        raise HTTPException(403, "Admin access only")
    return u


def seed_admin() -> None:
    email = os.getenv("ADMIN_EMAIL", "admin@pitwall.local")
    pw = os.getenv("ADMIN_PASSWORD", "Admin@123")
    u = db.get_user_by_email(email)
    if not u:
        db.create_user("Analyst Admin", email, hash_password(pw), provider="password", role="admin")
    elif u["role"] != "admin":
        db.update_user(u["id"], role="admin")


# ------------------------------------------------------------------ routes
class RegisterIn(BaseModel):
    name: str
    email: str
    password: str


class LoginIn(BaseModel):
    email: str
    password: str


class GoogleIn(BaseModel):
    credential: str


@router.get("/config")
def config():
    return {"google_client_id": GOOGLE_CLIENT_ID or None}


@router.post("/register")
def register(body: RegisterIn):
    name, email = body.name.strip(), body.email.strip().lower()
    if len(name) < 2:
        raise HTTPException(400, "Please enter your name")
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "Please enter a valid email address")
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    if db.get_user_by_email(email):
        raise HTTPException(409, "An account with this email already exists. Sign in instead.")
    uid = db.create_user(name, email, hash_password(body.password))
    return session(db.get_user(uid))


@router.post("/login")
def login(body: LoginIn):
    u = db.get_user_by_email(body.email.strip())
    if not u or not verify_password(body.password, u["password_hash"]):
        if u and u["provider"] == "google" and not u["password_hash"]:
            raise HTTPException(400, "This account uses Google sign-in. Use 'Continue with Google'.")
        raise HTTPException(401, "Incorrect email or password")
    if u["role"] == "admin":
        raise HTTPException(403, "Admin accounts sign in through the analyst portal (/admin/login)")
    return session(u)


@router.post("/admin/login")
def admin_login(body: LoginIn):
    u = db.get_user_by_email(body.email.strip())
    if not u or not verify_password(body.password, u["password_hash"]) or u["role"] != "admin":
        raise HTTPException(401, "Invalid admin credentials")
    return session(u)


@router.post("/google")
def google_login(body: GoogleIn):
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(400, "Google sign-in is not configured on this server (set GOOGLE_CLIENT_ID)")
    try:
        from google.auth.transport import requests as grequests
        from google.oauth2 import id_token
        info = id_token.verify_oauth2_token(body.credential, grequests.Request(), GOOGLE_CLIENT_ID)
    except Exception:
        raise HTTPException(401, "Google sign-in failed, please try again")
    if not info.get("email_verified", False):
        raise HTTPException(401, "Your Google email is not verified")
    email = info["email"].lower()
    u = db.get_user_by_email(email)
    if u and u["role"] == "admin":
        raise HTTPException(403, "Admin accounts sign in through the analyst portal")
    if not u:
        uid = db.create_user(info.get("name") or email.split("@")[0], email, None, provider="google",
                             avatar=info.get("picture"))
        u = db.get_user(uid)
    elif not u["avatar"] and info.get("picture"):
        db.update_user(u["id"], avatar=info["picture"])
        u = db.get_user(u["id"])
    return session(u)


@router.get("/me")
def me(u=Depends(current_user)):
    return public_user(u)
