"""Test and diagnose Supabase configuration for PITWALL.

Usage:
  python backend/test_supabase.py
"""
import os
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

print("=" * 65)
print("  PITWALL — Supabase Diagnostic Tool")
print("=" * 65)

if not url or not key:
    print("\n[!] SUPABASE_URL or SUPABASE_KEY is missing from .env.")
    print("    Currently using: Local SQLite database (backend/pitwall.db).")
    print("\nTo enable Supabase:")
    print("  1. Create a Supabase project at https://supabase.com")
    print("  2. Open SQL Editor and run 'supabase_schema.sql'")
    print("  3. Add SUPABASE_URL and SUPABASE_KEY to your .env file:")
    print("       SUPABASE_URL=https://<your-project-ref>.supabase.co")
    print("       SUPABASE_KEY=<your-anon-or-service-role-key>")
    print("=" * 65)
    sys.exit(0)

print(f"\n[1/3] Supabase credentials detected.")
masked_url = url[:32] + "..." if len(url) > 32 else url
masked_key = key[:10] + "..." + key[-6:] if len(key) > 20 else "***"
print(f"      URL: {masked_url}")
print(f"      KEY: {masked_key}")

try:
    from supabase import create_client
    client = create_client(url, key)
    print("\n[2/3] Supabase client initialized successfully.")
except Exception as e:
    print(f"\n[FAIL] Failed to create Supabase client: {e}")
    sys.exit(1)

# Test 'users' table
try:
    res_users = client.table("users").select("id, name, email, role").limit(5).execute()
    count_users = len(res_users.data) if res_users.data is not None else 0
    print(f"\n[3/3] Testing tables in Supabase:")
    print(f"      [OK] 'users' table is accessible (sample count: {count_users})")
except Exception as e:
    print(f"\n[FAIL] Could not query 'users' table:")
    print(f"       {e}")
    print("\n  -> Please run 'supabase_schema.sql' in your Supabase SQL Editor!")
    sys.exit(1)

# Test 'preferences' table
try:
    res_prefs = client.table("preferences").select("user_id").limit(5).execute()
    count_prefs = len(res_prefs.data) if res_prefs.data is not None else 0
    print(f"      [OK] 'preferences' table is accessible (sample count: {count_prefs})")
except Exception as e:
    print(f"\n[FAIL] Could not query 'preferences' table:")
    print(f"       {e}")
    print("\n  -> Please run 'supabase_schema.sql' in your Supabase SQL Editor!")
    sys.exit(1)

print("\n" + "=" * 65)
print("  [SUCCESS] Supabase is fully configured and ready for PITWALL!")
print("=" * 65 + "\n")
