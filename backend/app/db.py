"""Supabase Cloud Database storage layer for PITWALL: users, preferences, and F1 data.

100% powered by Supabase PostgreSQL. No local database instances or files.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("pitwall.db")


# ------------------------------------------------------------------ Environment
def _load_env() -> None:
    """Ensure environment variables are loaded from root or backend .env if present."""
    if os.getenv("SUPABASE_URL") and (os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")):
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

DEFAULT_PREFS: dict[str, Any] = {
    "fav_drivers": [],        # driverRef strings, e.g. "hamilton"
    "fav_constructors": [],   # constructorRef strings, e.g. "ferrari"
    "followed_sessions": ["race", "qualifying", "sprint"],  # practice | qualifying | sprint | race
    "followed_events": [],    # circuit refs; empty = all Grands Prix
    "onboarded": False,
}

_thread_local = threading.local()


def get_supabase_client():
    """Returns a thread-local authenticated Supabase client. Raises RuntimeError if not configured."""
    client = getattr(_thread_local, "client", None)
    if client is not None:
        return client

    url = (os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL") or "").strip()
    key = (
        os.getenv("SUPABASE_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_ANON_KEY")
        or ""
    ).strip()

    if not url or not key:
        raise RuntimeError(
            "Supabase Cloud Database credentials not found. "
            "Please configure SUPABASE_URL and SUPABASE_KEY in your environment or .env file."
        )

    try:
        from supabase import create_client
        client = create_client(url, key)
        _thread_local.client = client
        return client
    except Exception as e:
        logger.error(f"[PITWALL DB] Failed to initialize Supabase client: {e}")
        raise RuntimeError(f"Could not connect to Supabase Cloud Database: {e}") from e


def is_supabase_enabled() -> bool:
    """True if Supabase client is configured and available."""
    try:
        return get_supabase_client() is not None
    except Exception:
        return False


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_uid(uid: int | str) -> int | str:
    s = str(uid).strip()
    return int(s) if s.isdigit() else s


# ------------------------------------------------------------------ Lifecycle & Verification
def init() -> None:
    """Verifies connection to Supabase Cloud PostgreSQL and required tables."""
    client = get_supabase_client()
    url = os.getenv("SUPABASE_URL", "")
    masked_url = url[:28] + "..." if len(url) > 28 else url
    print(f"[PITWALL DB] Storage mode: 100% Supabase Cloud Database ({masked_url})")

    # Verify users table
    try:
        client.table("users").select("id").limit(1).execute()
        print("[PITWALL DB] Supabase 'users' table verified successfully.")
    except Exception as e:
        logger.error(f"[PITWALL DB] Failed to query 'users' table: {e}")
        raise RuntimeError(
            f"Failed to access Supabase 'users' table: {e}. "
            "Ensure 'supabase_schema.sql' has been executed in your Supabase SQL editor."
        ) from e

    # Verify F1 tables
    try:
        client.table("circuits").select("circuit_id").limit(1).execute()
        print("[PITWALL DB] Supabase F1 relational tables verified successfully.")
    except Exception as e:
        logger.error(f"[PITWALL DB] Failed to query 'circuits' table: {e}")
        raise RuntimeError(
            f"Failed to access Supabase F1 tables: {e}. "
            "Ensure the database migration script has completed."
        ) from e


# ------------------------------------------------------------------ Users & Auth
def get_user_by_email(email: str) -> dict | None:
    clean_email = email.strip().lower()
    client = get_supabase_client()
    res = client.table("users").select("*").ilike("email", clean_email).limit(1).execute()
    return dict(res.data[0]) if res.data else None


def get_user(uid: int | str) -> dict | None:
    clean_id = _clean_uid(uid)
    client = get_supabase_client()
    res = client.table("users").select("*").eq("id", clean_id).limit(1).execute()
    return dict(res.data[0]) if res.data else None


def create_user(
    name: str,
    email: str,
    password_hash: str | None,
    provider: str = "password",
    role: str = "user",
    avatar: str | None = None,
    user_id: int | None = None,
) -> int:
    clean_email = email.strip().lower()
    clean_name = name.strip()
    client = get_supabase_client()
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
        raise RuntimeError("Failed to insert user into Supabase 'users' table")
    return int(res.data[0]["id"])


def update_user(uid: int | str, **fields: Any) -> None:
    if not fields:
        return
    clean_id = _clean_uid(uid)
    client = get_supabase_client()
    client.table("users").update(fields).eq("id", clean_id).execute()


def get_prefs(uid: int | str) -> dict:
    clean_id = _clean_uid(uid)
    client = get_supabase_client()
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


def save_prefs(uid: int | str, prefs: dict) -> dict:
    clean_id = _clean_uid(uid)
    merged = get_prefs(clean_id)
    merged.update({k: v for k, v in prefs.items() if k in DEFAULT_PREFS})

    client = get_supabase_client()
    client.table("preferences").upsert(
        {"user_id": clean_id, "data": merged},
        on_conflict="user_id",
    ).execute()
    return merged


def get_all_users() -> list[dict]:
    """Lists all users directly from Supabase."""
    client = get_supabase_client()
    res = client.table("users").select("*").order("id").execute()
    return [dict(u) for u in (res.data or [])]


# ------------------------------------------------------------------ High-Performance Supabase F1 Queries
def fetch_all_rows(
    table_name: str,
    select: str = "*",
    gte_filters: dict[str, Any] | None = None,
    eq_filters: dict[str, Any] | None = None,
    batch_size: int = 1000,
) -> list[dict]:
    """Paginates through a Supabase table/view sequentially using .range() chunks."""
    client = get_supabase_client()
    all_data: list[dict] = []
    offset = 0
    while True:
        query = client.table(table_name).select(select).range(offset, offset + batch_size - 1)
        if eq_filters:
            for col, val in eq_filters.items():
                query = query.eq(col, val)
        if gte_filters:
            for col, val in gte_filters.items():
                query = query.gte(col, val)
        res = query.execute()
        if not res.data:
            break
        all_data.extend(res.data)
        if len(res.data) < batch_size:
            break
        offset += batch_size
    return all_data


def fetch_all_rows_parallel(
    table_name: str,
    select: str = "*",
    total_count: int | None = None,
    chunk_size: int = 1000,
    max_workers: int = 12,
) -> list[dict]:
    """Downloads large tables using concurrent range queries across thread-isolated Supabase clients."""
    client = get_supabase_client()
    if total_count is None:
        count_res = client.table(table_name).select(select.split(",")[0], count="exact").limit(1).execute()
        total_count = count_res.count or 0

    if total_count <= 0:
        return []
    if total_count <= chunk_size:
        res = client.table(table_name).select(select).range(0, total_count - 1).execute()
        return res.data or []

    chunks = [(i, min(i + chunk_size - 1, total_count - 1)) for i in range(0, total_count, chunk_size)]

    def _get_chunk(rng: tuple[int, int]) -> list[dict]:
        c = get_supabase_client()
        res = c.table(table_name).select(select).range(rng[0], rng[1]).execute()
        return res.data or []

    workers = min(max_workers, len(chunks))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        chunk_results = list(pool.map(_get_chunk, chunks))

    return [row for chunk in chunk_results for row in chunk]


def fetch_final_standings(final_race_ids: list[int]) -> tuple[list[dict], list[dict]]:
    """Fetches driver and constructor standings concurrently only for the final race of each season."""
    if not final_race_ids:
        return [], []

    def _get_ds() -> list[dict]:
        c = get_supabase_client()
        all_ds: list[dict] = []
        offset = 0
        while True:
            res = (
                c.table("driver_standings")
                .select("*")
                .in_("race_id", final_race_ids)
                .range(offset, offset + 999)
                .execute()
            )
            if not res.data:
                break
            all_ds.extend(res.data)
            if len(res.data) < 1000:
                break
            offset += 1000
        return all_ds

    def _get_cs() -> list[dict]:
        c = get_supabase_client()
        all_cs: list[dict] = []
        offset = 0
        while True:
            res = (
                c.table("constructor_standings")
                .select("*")
                .in_("race_id", final_race_ids)
                .range(offset, offset + 999)
                .execute()
            )
            if not res.data:
                break
            all_cs.extend(res.data)
            if len(res.data) < 1000:
                break
            offset += 1000
        return all_cs

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_ds = pool.submit(_get_ds)
        f_cs = pool.submit(_get_cs)
        return f_ds.result(), f_cs.result()


def fetch_ml_dataset(min_season: int = 2004) -> list[dict]:
    """Fetches ML training features from the dynamic v_f1_ml_dataset SQL view."""
    return fetch_all_rows("v_f1_ml_dataset", gte_filters={"season": min_season})


def fetch_mv_driver_summaries() -> list[dict]:
    """Fetches precomputed all-time driver career statistics from mv_driver_summaries."""
    return fetch_all_rows("mv_driver_summaries")


def fetch_mv_constructor_summaries() -> list[dict]:
    """Fetches precomputed all-time constructor career statistics from mv_constructor_summaries."""
    return fetch_all_rows("mv_constructor_summaries")


def fetch_lap_times_for_race(race_id: int) -> list[dict]:
    """Fetches all lap times for a specific race directly from Supabase using indexed lookup."""
    return fetch_all_rows("lap_times", eq_filters={"race_id": race_id})
