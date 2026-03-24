"""IMDB dataset download and SQLite import."""

import gzip
import sqlite3
from pathlib import Path
from typing import Optional

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS title_basics (
    tconst TEXT PRIMARY KEY,
    titleType TEXT,
    primaryTitle TEXT,
    originalTitle TEXT,
    isAdult INTEGER,
    startYear INTEGER,
    endYear INTEGER,
    runtimeMinutes INTEGER,
    genres TEXT
);
CREATE INDEX IF NOT EXISTS idx_tb_type ON title_basics(titleType);
CREATE INDEX IF NOT EXISTS idx_tb_year ON title_basics(startYear);
CREATE INDEX IF NOT EXISTS idx_tb_genres ON title_basics(genres);

CREATE TABLE IF NOT EXISTS title_ratings (
    tconst TEXT PRIMARY KEY,
    averageRating REAL,
    numVotes INTEGER
);

CREATE TABLE IF NOT EXISTS title_akas (
    tconst TEXT NOT NULL,
    ordering INTEGER,
    title TEXT,
    region TEXT,
    language TEXT,
    types TEXT,
    attributes TEXT,
    isOriginalTitle INTEGER
);
CREATE INDEX IF NOT EXISTS idx_aka_tconst ON title_akas(tconst);
CREATE INDEX IF NOT EXISTS idx_aka_region ON title_akas(region);
CREATE INDEX IF NOT EXISTS idx_aka_language ON title_akas(language);

CREATE TABLE IF NOT EXISTS title_crew (
    tconst TEXT PRIMARY KEY,
    directors TEXT,
    writers TEXT
);

CREATE TABLE IF NOT EXISTS title_episode (
    tconst TEXT PRIMARY KEY,
    parentTconst TEXT,
    seasonNumber INTEGER,
    episodeNumber INTEGER
);
CREATE INDEX IF NOT EXISTS idx_ep_parent ON title_episode(parentTconst);

CREATE TABLE IF NOT EXISTS title_principals (
    tconst TEXT NOT NULL,
    ordering INTEGER,
    nconst TEXT NOT NULL,
    category TEXT,
    job TEXT,
    characters TEXT
);
CREATE INDEX IF NOT EXISTS idx_pr_tconst ON title_principals(tconst);
CREATE INDEX IF NOT EXISTS idx_pr_nconst ON title_principals(nconst);

CREATE TABLE IF NOT EXISTS name_basics (
    nconst TEXT PRIMARY KEY,
    primaryName TEXT,
    birthYear INTEGER,
    deathYear INTEGER,
    primaryProfession TEXT,
    knownForTitles TEXT
);
CREATE INDEX IF NOT EXISTS idx_nb_name ON name_basics(primaryName);

CREATE TABLE IF NOT EXISTS import_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def create_schema(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes in the given connection."""
    conn.executescript(SCHEMA_SQL)


# Minimum row counts per dataset (guards against truncated downloads)
MIN_ROWS: dict[str, int] = {
    "title_basics": 1_000_000,
    "title_ratings": 500_000,
    "title_akas": 1_000_000,
    "title_crew": 1_000_000,
    "title_episode": 100_000,
    "title_principals": 1_000_000,
    "name_basics": 1_000_000,
}

BATCH_SIZE = 10_000


def _null(value: str) -> Optional[str]:
    """Convert IMDB null sentinel to Python None."""
    return None if value == r"\N" else value


def _int_or_none(value: str) -> Optional[int]:
    v = _null(value)
    return int(v) if v is not None else None


def _real_or_none(value: str) -> Optional[float]:
    v = _null(value)
    return float(v) if v is not None else None


INT_COLS = frozenset(
    {
        "isAdult",
        "startYear",
        "endYear",
        "runtimeMinutes",
        "numVotes",
        "ordering",
        "isOriginalTitle",
        "seasonNumber",
        "episodeNumber",
        "birthYear",
        "deathYear",
    }
)
REAL_COLS = frozenset({"averageRating"})


def _coerce(col: str, val: str):
    if col in INT_COLS:
        return _int_or_none(val)
    if col in REAL_COLS:
        return _real_or_none(val)
    return _null(val)


def import_table(
    conn: sqlite3.Connection,
    gz_path: Path,
    table: str,
    columns: list[str],
    min_rows: int,
) -> int:
    """
    Parse a gzip TSV file and bulk-insert into the given table.

    Runs inside a single transaction per file; rolls back on any error.
    Validates that at least min_rows were inserted before committing.

    Returns the number of rows inserted.
    """
    placeholders = ",".join("?" * len(columns))
    sql = f"INSERT OR REPLACE INTO {table} VALUES ({placeholders})"  # nosec B608

    count = 0
    batch: list = []
    try:
        conn.execute("BEGIN")
        with gzip.open(gz_path, "rt", encoding="utf-8") as f:
            f.readline()  # skip header row
            for line in f:
                parts = line.rstrip("\n").split("\t")
                row = tuple(_coerce(col, val) for col, val in zip(columns, parts))
                batch.append(row)
                if len(batch) >= BATCH_SIZE:
                    conn.executemany(sql, batch)
                    count += len(batch)
                    batch = []
            if batch:
                conn.executemany(sql, batch)
                count += len(batch)

        if count < min_rows:
            raise ValueError(
                f"import_table({table}): too few rows — got {count}, expected ≥ {min_rows}"
            )

        conn.execute("COMMIT")
        return count
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:  # nosec B110
            pass
        raise
