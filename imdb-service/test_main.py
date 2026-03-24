"""Tests for IMDB service."""

import sqlite3
import tempfile
from pathlib import Path


def test_create_schema_creates_all_tables():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    try:
        conn = sqlite3.connect(db_path)
        from importer import create_schema

        create_schema(conn)
        conn.commit()
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = {row[0] for row in cursor.fetchall()}
        assert tables == {
            "title_basics",
            "title_ratings",
            "title_akas",
            "title_crew",
            "title_episode",
            "title_principals",
            "name_basics",
            "import_meta",
        }
        conn.close()
    finally:
        db_path.unlink(missing_ok=True)


def test_create_schema_creates_indexes():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    try:
        conn = sqlite3.connect(db_path)
        from importer import create_schema

        create_schema(conn)
        conn.commit()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
        )
        indexes = {row[0] for row in cursor.fetchall()}
        assert "idx_tb_type" in indexes
        assert "idx_aka_tconst" in indexes
        assert "idx_pr_nconst" in indexes
        assert "idx_ep_parent" in indexes
        conn.close()
    finally:
        db_path.unlink(missing_ok=True)
