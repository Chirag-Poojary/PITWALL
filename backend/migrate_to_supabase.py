"""Migrate existing users and preferences from SQLite (pitwall.db) to Supabase.

Usage:
  python backend/migrate_to_supabase.py
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
env_file = ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

url = (os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL") or "").strip()
key = (os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY") or "").strip()

if not url or not key:
    print("[ERROR] SUPABASE_URL and SUPABASE_KEY must be set in your .env file before running migration.")
    print("Example in .env:")
    print("  SUPABASE_URL=https://your-project.supabase.co")
    print("  SUPABASE_KEY=eyJhbGciOi...")
    sys.exit(1)

db_path = ROOT / "backend" / "pitwall.db"
if not db_path.exists():
    print(f"[INFO] No SQLite database found at {db_path}. Nothing to migrate.")
    sys.exit(0)

try:
    from supabase import create_client
    client = create_client(url, key)
except Exception as e:
    print(f"[ERROR] Failed to connect to Supabase: {e}")
    sys.exit(1)

# Check if Supabase tables exist
try:
    client.table("users").select("id").limit(1).execute()
except Exception as e:
    print(f"[ERROR] Could not query 'users' table in Supabase. Have you executed supabase_schema.sql?")
    print(f"Details: {e}")
    sys.exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

users = conn.execute("SELECT * FROM users").fetchall()
print(f"\n[INFO] Found {len(users)} user(s) in SQLite ({db_path.name}). Starting migration to Supabase...")

migrated_users = 0
migrated_prefs = 0

for u in users:
    email = u["email"].strip().lower()
    res = client.table("users").select("id").ilike("email", email).execute()
    user_id = u["id"]

    if res.data:
        user_id = res.data[0]["id"]
        print(f"  - User '{email}' already exists in Supabase (id={user_id}). Updating...")
        client.table("users").update({
            "name": u["name"],
            "password_hash": u["password_hash"],
            "provider": u["provider"],
            "role": u["role"],
            "avatar": u["avatar"],
        }).eq("id", user_id).execute()
    else:
        print(f"  - Inserting user '{email}' (id={user_id})...")
        client.table("users").insert({
            "id": user_id,
            "name": u["name"],
            "email": email,
            "password_hash": u["password_hash"],
            "provider": u["provider"],
            "role": u["role"],
            "avatar": u["avatar"],
            "created_at": u["created_at"],
        }).execute()
        migrated_users += 1

    # Migrate preferences
    pref_row = conn.execute("SELECT data FROM preferences WHERE user_id = ?", (u["id"],)).fetchone()
    if pref_row:
        try:
            data = json.loads(pref_row["data"])
        except Exception:
            data = {}
        client.table("preferences").upsert({
            "user_id": user_id,
            "data": data,
        }, on_conflict="user_id").execute()
        migrated_prefs += 1

print("\n" + "=" * 60)
print(f"[SUCCESS] Migration completed successfully!")
print(f"  Users migrated / updated: {len(users)}")
print(f"  Preferences migrated:     {migrated_prefs}")
print("=" * 60 + "\n")
