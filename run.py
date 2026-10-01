"""Start PITWALL:  python run.py   ->  http://localhost:8000

Reads optional settings from a .env file next to this script
(GOOGLE_CLIENT_ID, ADMIN_EMAIL, ADMIN_PASSWORD, JWT_SECRET, PORT).
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
env = ROOT / ".env"
if env.exists():
    for line in env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

sys.path.insert(0, str(ROOT / "backend"))

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    print(f"\n  PITWALL running at  http://localhost:{port}\n  Analyst portal:     http://localhost:{port}/admin/login\n")
    uvicorn.run("app.main:app", host=os.getenv("HOST", "127.0.0.1"), port=port,
                reload="--reload" in sys.argv, app_dir=str(ROOT / "backend"))
