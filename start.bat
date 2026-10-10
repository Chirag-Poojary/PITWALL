@echo off
cd /d %~dp0
if not exist .venv (
  echo Creating virtual environment...
  python -m venv .venv
  call .venv\Scripts\activate
  pip install -r backend\requirements.txt
) else (
  call .venv\Scripts\activate
)
python run.py
