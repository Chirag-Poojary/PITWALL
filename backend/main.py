"""FastAPI entrypoint for Vercel deployment.

Imports and exposes the FastAPI `app` from `app.main`.
"""
from app.main import app

__all__ = ["app"]
