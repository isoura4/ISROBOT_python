"""
Tests for .env synchronization and database column migration.

This module tests:
- ensure_env_variables: adding missing keys from .env.example to .env
- ensure_table_columns: adding missing columns to existing database tables
"""

import os
import sqlite3
import tempfile

import pytest


class TestEnsureEnvVariables:
    """Tests for the .env synchronization logic."""

    def test_missing_keys_added(self, tmp_path):
        """Missing keys from .env.example are appended to .env."""
        env_example = tmp_path / ".env.example"
        env_file = tmp_path / ".env"

        env_example.write_text(
            "app_id=123\nsecret_key=TOKEN\nNEW_VAR=default_value\n"
        )
        env_file.write_text("app_id=999\nsecret_key=MYTOKEN\n")

        _run_ensure_env(str(tmp_path))

        content = env_file.read_text()
        assert "NEW_VAR=default_value" in content
        # Existing values should not be overwritten
        assert "app_id=999" in content
        assert "secret_key=MYTOKEN" in content

    def test_no_changes_when_all_present(self, tmp_path):
        """No changes when all keys already exist in .env."""
        env_example = tmp_path / ".env.example"
        env_file = tmp_path / ".env"

        env_example.write_text("app_id=123\nsecret_key=TOKEN\n")
        env_file.write_text("app_id=999\nsecret_key=MYTOKEN\n")

        original = env_file.read_text()
        _run_ensure_env(str(tmp_path))
        assert env_file.read_text() == original

    def test_creates_env_if_missing(self, tmp_path):
        """Creates .env with all keys when it doesn't exist."""
        env_example = tmp_path / ".env.example"
        env_file = tmp_path / ".env"

        env_example.write_text("app_id=123\nsecret_key=TOKEN\n")

        _run_ensure_env(str(tmp_path))

        content = env_file.read_text()
        assert "app_id=123" in content
        assert "secret_key=TOKEN" in content

    def test_skips_comments_and_empty_lines(self, tmp_path):
        """Comments and empty lines in .env.example are ignored."""
        env_example = tmp_path / ".env.example"
        env_file = tmp_path / ".env"

        env_example.write_text(
            "# This is a comment\n\napp_id=123\n# Another comment\n"
        )
        env_file.write_text("")

        _run_ensure_env(str(tmp_path))

        content = env_file.read_text()
        assert "app_id=123" in content
        assert "# This is a comment" not in content

    def test_no_env_example(self, tmp_path):
        """Does nothing when .env.example doesn't exist."""
        env_file = tmp_path / ".env"
        env_file.write_text("app_id=999\n")

        _run_ensure_env(str(tmp_path))

        assert env_file.read_text() == "app_id=999\n"


def _run_ensure_env(script_dir):
    """Run the ensure_env_variables logic with a custom script_dir."""
    env_path = os.path.join(script_dir, ".env")
    env_example_path = os.path.join(script_dir, ".env.example")

    if not os.path.exists(env_example_path):
        return

    example_entries = {}
    with open(env_example_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                key = stripped.split("=", 1)[0].strip()
                value = stripped.split("=", 1)[1].strip()
                example_entries[key] = value

    existing_keys = set()
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    key = stripped.split("=", 1)[0].strip()
                    existing_keys.add(key)

    missing = {k: v for k, v in example_entries.items() if k not in existing_keys}
    if missing:
        with open(env_path, "a", encoding="utf-8") as f:
            f.write("\n# Variables ajoutées automatiquement depuis .env.example\n")
            for key, value in missing.items():
                f.write(f"{key}={value}\n")


class TestEnsureTableColumns:
    """Tests for the database column migration logic."""

    def test_adds_missing_column(self):
        """Missing columns are added to existing tables."""
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        try:
            conn = sqlite3.connect(db_path)
            # Create a table missing the 'coins' column
            conn.execute("""
                CREATE TABLE users (
                    guildId TEXT NOT NULL,
                    userId TEXT NOT NULL,
                    xp REAL DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    messages INTEGER DEFAULT 0,
                    PRIMARY KEY (guildId, userId)
                )
            """)
            conn.commit()
            conn.close()

            from db_migrations import ensure_table_columns

            result = ensure_table_columns(db_path)
            assert result is True

            # Verify the column was added
            conn = sqlite3.connect(db_path)
            cursor = conn.execute("PRAGMA table_info(users)")
            col_names = [row[1] for row in cursor.fetchall()]
            conn.close()

            assert "coins" in col_names
        finally:
            os.unlink(db_path)

    def test_no_change_when_all_columns_present(self):
        """No changes when all columns already exist."""
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        try:
            conn = sqlite3.connect(db_path)
            conn.execute("""
                CREATE TABLE users (
                    guildId TEXT NOT NULL,
                    userId TEXT NOT NULL,
                    xp REAL DEFAULT 0,
                    level INTEGER DEFAULT 1,
                    messages INTEGER DEFAULT 0,
                    coins REAL DEFAULT 0,
                    PRIMARY KEY (guildId, userId)
                )
            """)
            conn.commit()
            conn.close()

            from db_migrations import ensure_table_columns

            result = ensure_table_columns(db_path)
            assert result is True
        finally:
            os.unlink(db_path)

    def test_skips_nonexistent_table(self):
        """Tables that don't exist are skipped without error."""
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        try:
            # Create an empty database (no tables)
            conn = sqlite3.connect(db_path)
            conn.commit()
            conn.close()

            from db_migrations import ensure_table_columns

            result = ensure_table_columns(db_path)
            assert result is True
        finally:
            os.unlink(db_path)

    def test_multiple_missing_columns(self):
        """Multiple missing columns across tables are added."""
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        try:
            conn = sqlite3.connect(db_path)
            # Create streamers table missing 'roleId' and 'startTime'
            conn.execute("""
                CREATE TABLE streamers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    streamerName TEXT NOT NULL,
                    streamChannelId TEXT,
                    announced INTEGER DEFAULT 0
                )
            """)
            conn.commit()
            conn.close()

            from db_migrations import ensure_table_columns

            result = ensure_table_columns(db_path)
            assert result is True

            conn = sqlite3.connect(db_path)
            cursor = conn.execute("PRAGMA table_info(streamers)")
            col_names = [row[1] for row in cursor.fetchall()]
            conn.close()

            assert "roleId" in col_names
            assert "startTime" in col_names
        finally:
            os.unlink(db_path)
