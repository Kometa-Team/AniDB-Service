"""Tests for IMDB service."""

import gzip
import io
import sqlite3
import tempfile
from pathlib import Path

import pytest


def _make_tsv_gz(header: str, rows: list[str]) -> bytes:
    """Build a gzip-compressed TSV bytes object for testing."""
    content = "\n".join([header] + rows) + "\n"
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as f:
        f.write(content.encode())
    return buf.getvalue()


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


def test_import_table_inserts_rows(tmp_path):
    data = _make_tsv_gz(
        "tconst\ttitleType\tprimaryTitle\toriginalTitle\tisAdult\tstartYear\tendYear\truntimeMinutes\tgenres",
        [
            "tt0000001\tshort\tCarmencita\tCarmencita\t0\t1894\t\\N\t1\tDocumentary,Short",
            "tt0000002\tshort\tLe clown\tLe clown\t0\t1892\t\\N\t5\tComedy",
        ],
    )
    gz_path = tmp_path / "title.basics.tsv.gz"
    gz_path.write_bytes(data)

    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    from importer import create_schema, import_table

    create_schema(conn)
    conn.commit()
    count = import_table(
        conn,
        gz_path,
        "title_basics",
        [
            "tconst",
            "titleType",
            "primaryTitle",
            "originalTitle",
            "isAdult",
            "startYear",
            "endYear",
            "runtimeMinutes",
            "genres",
        ],
        min_rows=1,
    )
    assert count == 2
    rows = conn.execute(
        "SELECT tconst, startYear, endYear FROM title_basics ORDER BY tconst"
    ).fetchall()
    assert rows[0] == ("tt0000001", 1894, None)  # \N → NULL
    assert rows[1] == ("tt0000002", 1892, None)
    conn.close()


def test_import_table_raises_on_min_rows_not_met(tmp_path):
    data = _make_tsv_gz(
        "tconst\ttitleType\tprimaryTitle\toriginalTitle\tisAdult\tstartYear\tendYear\truntimeMinutes\tgenres",
        ["tt0000001\tshort\tCarmencita\tCarmencita\t0\t1894\t\\N\t1\tDocumentary,Short"],
    )
    gz_path = tmp_path / "title.basics.tsv.gz"
    gz_path.write_bytes(data)

    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    from importer import create_schema, import_table

    create_schema(conn)
    conn.commit()
    with pytest.raises(ValueError, match="too few rows"):
        import_table(
            conn,
            gz_path,
            "title_basics",
            [
                "tconst",
                "titleType",
                "primaryTitle",
                "originalTitle",
                "isAdult",
                "startYear",
                "endYear",
                "runtimeMinutes",
                "genres",
            ],
            min_rows=1000,
        )
    conn.close()
