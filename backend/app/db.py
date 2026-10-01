"""Database storage layer for PITWALL: users and their preferences.

Supports:
1. Supabase Cloud Database (PostgreSQL via Supabase Client) when SUPABASE_URL
   and SUPABASE_KEY are provided.
2. Local SQLite fallback (backend/pitwall.db) when Supabase is not configured.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("pitwall.db")

# Load .env if running standalone or environment not yet populated
def _load_env() -> None:
    if os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_KEY"):
        return
    for base in [Path(__file__).resolve().parent.parent.parent, Path(__file__).resolve().parent.parent]:
        env_file = base / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            break

_load_env()

DB_PATH = Path(os.getenv("PITWALL_DB", Path(__file__).resolve().parent.parent / "pitwall.db"))
_local = threading.local()

DEFAULT_PREFS: dict[str, Any] = {
    "fav_drivers": [],        # driverRef strings, e.g. "hamilton"
    "fav_constructors": [],   # constructorRef strings, e.g. "ferrari"
    "followed_sessions": ["race", "qualifying", "sprint"],  # practice | qualifying | sprint | race
    "followed_events": [],    # circuit refs; empty = all Grands Prix
    "onboarded": False,
}

_supabase_client = None
_supabase_tested = False


def get_supabase_client():
    """Returns an authenticated Supabase client if configured, else None."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    url = (os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL") or "").strip()
    key = (os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY") or "").strip()

    if not url or not key:
        return None

    try:
        from supabase import create_client
        _supabase_client = create_client(url, key)
        return _supabase_client
    except Exception as e:
        logger.warning(f"[PITWALL DB] Could not initialize Supabase client: {e}")
        return None


def is_supabase_enabled() -> bool:
    """True if Supabase client is configured and available."""
    return get_supabase_client() is not None


# ------------------------------------------------------------------ SQLite helpers
def conn() -> sqlite3.Connection:
    c = getattr(_local, "conn", None)
    if c is None:
        c = sqlite3.connect(DB_PATH, check_same_thread=False)
        c.row_factory = sqlite3.Row
        _local.conn = c
    return c


def _init_sqlite() -> None:
    c = conn()
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT,
            provider TEXT NOT NULL DEFAULT 'password',
            role TEXT NOT NULL DEFAULT 'user',
            avatar TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS preferences (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            data TEXT NOT NULL
        );
        """
    )
    c.commit()


# ------------------------------------------------------------------ Public API
def init() -> None:
    """Initialize storage tables or verify Supabase connection."""
    client = get_supabase_client()
    if client:
        url = os.getenv("SUPABASE_URL", "")
        masked_url = url[:28] + "..." if len(url) > 28 else url
        print(f"[PITWALL DB] Storage mode: Supabase Cloud Database ({masked_url})")
        try:
            # Probe users table to verify schema existence
            client.table("users").select("id").limit(1).execute()
            print("[PITWALL DB] Supabase 'users' table verified successfully.")
        except Exception as e:
            print("\n" + "=" * 76)
            print("[PITWALL DB] WARNING: Connected to Supabase, but could not query 'users':")
            print(f"  {e}")
            print("\nPlease make sure you have executed the schema script in your Supabase project:")
            print("  File: supabase_schema.sql (or backend/supabase_schema.sql)")
            print("  Dashboard: https://supabase.com/dashboard/project/_/sql")
            print("=" * 76 + "\n")
        return

    # Fallback to SQLite
    print(f"[PITWALL DB] Storage mode: Local SQLite ({DB_PATH.name})")
    print("  [Tip] To store users in Supabase, set SUPABASE_URL and SUPABASE_KEY in .env")
    _init_sqlite()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_uid(uid: int | str) -> int | str:
    s = str(uid).strip()
    return int(s) if s.isdigit() else s


def get_user_by_email(email: str) -> dict | sqlite3.Row | None:
    clean_email = email.strip().lower()
    client = get_supabase_client()
    if client:
        res = client.table("users").select("*").ilike("email", clean_email).limit(1).execute()
        return dict(res.data[0]) if res.data else None

    return conn().execute("SELECT * FROM users WHERE lower(email) = lower(?)", (clean_email,)).fetchone()


def get_user(uid: int | str) -> dict | sqlite3.Row | None:
    clean_id = _clean_uid(uid)
    client = get_supabase_client()
    if client:
        res = client.table("users").select("*").eq("id", clean_id).limit(1).execute()
        return dict(res.data[0]) if res.data else None

    return conn().execute("SELECT * FROM users WHERE id = ?", (clean_id,)).fetchone()


def create_user(name: str, email: str, password_hash: str | None, provider: str = "password",
                role: str = "user", avatar: str | None = None, user_id: int | None = None) -> int:
    clean_email = email.strip().lower()
    clean_name = name.strip()
    client = get_supabase_client()
    if client:
        payload: dict[str, Any] = {
            "name": clean_name,
            "email": clean_email,
            "password_hash": password_hash,
            "provider": provider,
            "role": role,
            "avatar": avatar,
            "created_at": _now(),
        }
        if user_id is not None:
            payload["id"] = int(user_id)
        res = client.table("users").insert(payload).execute()
        if not res.data:
            raise RuntimeError("Failed to insert user into Supabase")
        return int(res.data[0]["id"])

    c = conn()
    if user_id is not None:
        cur = c.execute(
            "INSERT INTO users (id, name, email, password_hash, provider, role, avatar, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (int(user_id), clean_name, clean_email, password_hash, provider, role, avatar, _now()),
        )
    else:
        cur = c.execute(
            "INSERT INTO users (name, email, password_hash, provider, role, avatar, created_at) VALUES (?,?,?,?,?,?,?)",
            (clean_name, clean_email, password_hash, provider, role, avatar, _now()),
        )
    c.commit()
    return cur.lastrowid


def update_user(uid: int | str, **fields: Any) -> None:
    if not fields:
        return
    clean_id = _clean_uid(uid)
    client = get_supabase_client()
    if client:
        client.table("users").update(fields).eq("id", clean_id).execute()
        return

    cols = ", ".join(f"{k} = ?" for k in fields)
    c = conn()
    c.execute(f"UPDATE users SET {cols} WHERE id = ?", (*fields.values(), clean_id))
    c.commit()


def get_prefs(uid: int | str) -> dict:
    clean_id = _clean_uid(uid)
    client = get_supabase_client()
    if client:
        res = client.table("preferences").select("data").eq("user_id", clean_id).limit(1).execute()
        prefs = dict(DEFAULT_PREFS)
        if res.data:
            raw = res.data[0].get("data")
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except Exception:
                    raw = {}
            if isinstance(raw, dict):
                prefs.update(raw)
        return prefs

    row = conn().execute("SELECT data FROM preferences WHERE user_id = ?", (clean_id,)).fetchone()
    prefs = dict(DEFAULT_PREFS)
    if row:
        try:
            prefs.update(json.loads(row["data"]))
        except Exception:
            pass
    return prefs


def save_prefs(uid: int | str, prefs: dict) -> dict:
    clean_id = _clean_uid(uid)
    merged = get_prefs(clean_id)
    merged.update({k: v for k, v in prefs.items() if k in DEFAULT_PREFS})

    client = get_supabase_client()
    if client:
        client.table("preferences").upsert(
            {"user_id": clean_id, "data": merged},
            on_conflict="user_id"
        ).execute()
        return merged

    c = conn()
    c.execute("INSERT INTO preferences (user_id, data) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET data = excluded.data",
              (clean_id, json.dumps(merged)))
    c.commit()
    return merged


def get_all_users() -> list[dict]:
    """Helper to list all users, useful for inspection and migration."""
    client = get_supabase_client()
    if client:
        res = client.table("users").select("*").order("id").execute()
        return [dict(u) for u in (res.data or [])]

    rows = conn().execute("SELECT * FROM users ORDER BY id").fetchall()
    return [dict(r) for r in rows]
