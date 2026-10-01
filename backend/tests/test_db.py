"""Unit tests for app.db (SQLite mode and Supabase mode)."""
import os
import sqlite3
import tempfile
from pathlib import Path
from unittest import TestCase, mock

# Ensure backend is on sys.path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db


class TestDbSQLite(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_db_path = Path(self.temp_dir.name) / "test_pitwall.db"
        
        # Override DB_PATH and clear thread-local connection
        self.orig_db_path = db.DB_PATH
        db.DB_PATH = self.test_db_path
        if hasattr(db._local, "conn"):
            try:
                db._local.conn.close()
            except Exception:
                pass
            db._local.conn = None
        
        # Ensure Supabase client is None during SQLite tests
        self.orig_sb = db._supabase_client
        db._supabase_client = None
        db.init()

    def tearDown(self):
        if hasattr(db._local, "conn") and db._local.conn:
            try:
                db._local.conn.close()
            except Exception:
                pass
            db._local.conn = None
        db.DB_PATH = self.orig_db_path
        db._supabase_client = self.orig_sb
        self.temp_dir.cleanup()

    def test_create_and_get_user(self):
        uid = db.create_user("Test Fan", "fan@example.com", "hash123", provider="password", role="user")
        assert uid > 0

        user = db.get_user(uid)
        assert user is not None
        assert user["name"] == "Test Fan"
        assert user["email"] == "fan@example.com"
        assert user["role"] == "user"

        by_email = db.get_user_by_email("FAN@EXAMPLE.COM")
        assert by_email is not None
        assert by_email["id"] == uid

    def test_update_user(self):
        uid = db.create_user("Old Name", "update@example.com", None)
        db.update_user(uid, name="New Name", avatar="https://example.com/avatar.jpg")
        u = db.get_user(uid)
        assert u["name"] == "New Name"
        assert u["avatar"] == "https://example.com/avatar.jpg"

    def test_preferences_lifecycle(self):
        uid = db.create_user("Pref Fan", "prefs@example.com", None)
        prefs = db.get_prefs(uid)
        assert prefs["onboarded"] is False
        assert prefs["fav_drivers"] == []

        saved = db.save_prefs(uid, {"fav_drivers": ["verstappen", "hamilton"], "onboarded": True})
        assert saved["onboarded"] is True
        assert saved["fav_drivers"] == ["verstappen", "hamilton"]

        refetched = db.get_prefs(uid)
        assert refetched["onboarded"] is True
        assert refetched["fav_drivers"] == ["verstappen", "hamilton"]


class TestDbSupabase(TestCase):
    def setUp(self):
        self.mock_client = mock.MagicMock()
        self.orig_sb = db._supabase_client
        db._supabase_client = self.mock_client

    def tearDown(self):
        db._supabase_client = self.orig_sb

    def test_supabase_get_user_by_email(self):
        mock_table = mock.MagicMock()
        self.mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.ilike.return_value = mock_table
        mock_table.limit.return_value = mock_table
        
        # Mock returned record
        mock_table.execute.return_value = mock.MagicMock(
            data=[{"id": 42, "name": "Supa Fan", "email": "supa@example.com", "role": "user"}]
        )

        user = db.get_user_by_email("supa@example.com")
        assert user is not None
        assert user["id"] == 42
        assert user["name"] == "Supa Fan"
        self.mock_client.table.assert_called_with("users")

    def test_supabase_create_user(self):
        mock_table = mock.MagicMock()
        self.mock_client.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.execute.return_value = mock.MagicMock(
            data=[{"id": 99, "name": "Created User", "email": "created@example.com"}]
        )

        uid = db.create_user("Created User", "created@example.com", "pw_hash")
        assert uid == 99
        self.mock_client.table.assert_called_with("users")
        mock_table.insert.assert_called_once()
        inserted_payload = mock_table.insert.call_args[0][0]
        assert inserted_payload["email"] == "created@example.com"
        assert inserted_payload["name"] == "Created User"

    def test_supabase_preferences(self):
        mock_table = mock.MagicMock()
        self.mock_client.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.limit.return_value = mock_table
        
        # Test get_prefs
        mock_table.execute.return_value = mock.MagicMock(
            data=[{"user_id": 99, "data": {"fav_drivers": ["norris"], "onboarded": True}}]
        )
        prefs = db.get_prefs(99)
        assert prefs["fav_drivers"] == ["norris"]
        assert prefs["onboarded"] is True

        # Test save_prefs
        mock_table.upsert.return_value = mock_table
        saved = db.save_prefs(99, {"fav_constructors": ["mclaren"]})
        assert "mclaren" in saved["fav_constructors"]
        mock_table.upsert.assert_called_once()
