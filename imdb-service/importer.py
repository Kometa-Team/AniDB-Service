"""IMDB dataset download and SQLite import."""

import asyncio
import gzip
import json
import os
import sqlite3
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

import httpx

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
CREATE INDEX IF NOT EXISTS idx_aka_lang_tconst ON title_akas(language, tconst);
CREATE INDEX IF NOT EXISTS idx_aka_region_tconst ON title_akas(region, tconst);

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
    on_progress: Optional[Callable[[int], None]] = None,
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
                    if on_progress:
                        on_progress(count)
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


IMDB_BASE_URL = "https://datasets.imdbws.com"

DATASET_FILES: dict[str, str] = {
    "title.basics": "title.basics.tsv.gz",
    "title.ratings": "title.ratings.tsv.gz",
    "title.akas": "title.akas.tsv.gz",
    "title.crew": "title.crew.tsv.gz",
    "title.episode": "title.episode.tsv.gz",
    "title.principals": "title.principals.tsv.gz",
    "name.basics": "name.basics.tsv.gz",
}


def _gzip_is_complete(path: Path) -> bool:
    """Return True if the gzip file exists and its stream ends cleanly."""
    if not path.exists():
        return False
    try:
        with gzip.open(path, "rb") as f:
            while f.read(65536):
                pass
        return True
    except Exception:
        return False


async def _download_one(
    client: httpx.AsyncClient,
    filename: str,
    dest: Path,
    on_start: Optional[Callable[[str], None]] = None,
    on_done: Optional[Callable[[str], None]] = None,
) -> None:
    """Stream a single dataset file to disk, skipping if already complete."""
    if await asyncio.to_thread(_gzip_is_complete, dest):
        print(f"⏭️  Skipping {filename} (already complete)")
        if on_start:
            on_start(filename)
        if on_done:
            on_done(filename)
        return
    url = f"{IMDB_BASE_URL}/{filename}"
    if on_start:
        on_start(filename)
    print(f"⬇️  Downloading {filename}...")
    async with client.stream("GET", url, timeout=600.0) as response:
        response.raise_for_status()
        with dest.open("wb") as f:
            async for chunk in response.aiter_bytes(65536):
                f.write(chunk)
    print(f"✅ Downloaded {filename}")
    if on_done:
        on_done(filename)


async def download_datasets(
    data_dir: Path,
    on_file_start: Optional[Callable[[str], None]] = None,
    on_file_done: Optional[Callable[[str], None]] = None,
) -> dict[str, Path]:
    """
    Download all 7 IMDB dataset files concurrently to data_dir.

    Returns a dict mapping stem → local Path.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {stem: data_dir / filename for stem, filename in DATASET_FILES.items()}

    async with httpx.AsyncClient(timeout=600.0) as client:
        tasks = [
            _download_one(client, filename, paths[stem], on_file_start, on_file_done)
            for stem, filename in DATASET_FILES.items()
        ]
        await asyncio.gather(*tasks)

    return paths


# Maps dataset stem → table name
STEM_TO_TABLE: dict[str, str] = {
    "title.basics": "title_basics",
    "title.ratings": "title_ratings",
    "title.akas": "title_akas",
    "title.crew": "title_crew",
    "title.episode": "title_episode",
    "title.principals": "title_principals",
    "name.basics": "name_basics",
}

# Column definitions per table (must match TSV file column order)
TABLE_COLUMNS: dict[str, list[str]] = {
    "title_basics": [
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
    "title_ratings": ["tconst", "averageRating", "numVotes"],
    "title_akas": [
        "tconst",
        "ordering",
        "title",
        "region",
        "language",
        "types",
        "attributes",
        "isOriginalTitle",
    ],
    "title_crew": ["tconst", "directors", "writers"],
    "title_episode": ["tconst", "parentTconst", "seasonNumber", "episodeNumber"],
    "title_principals": ["tconst", "ordering", "nconst", "category", "job", "characters"],
    "name_basics": [
        "nconst",
        "primaryName",
        "birthYear",
        "deathYear",
        "primaryProfession",
        "knownForTitles",
    ],
}


def run_full_import(
    gz_paths: dict[str, Path],
    live_db: Path,
    min_rows_override: Optional[int] = None,
    on_table_start: Optional[Callable[[str], None]] = None,
    on_table_done: Optional[Callable[[str, int], None]] = None,
    on_table_progress: Optional[Callable[[str, int], None]] = None,
) -> None:
    """
    Import all dataset files into a shadow DB, then atomically replace live_db.

    gz_paths: dict mapping dataset stem → local .tsv.gz path
    live_db: path to the live SQLite DB to replace
    min_rows_override: if set, use this as min_rows for all tables (0 = no check; for tests)
    """
    shadow_db = live_db.parent / "imdb_shadow.db"

    # Clean up any leftover shadow from a previous failed run
    if shadow_db.exists():
        shadow_db.unlink()

    conn = None
    try:
        conn = sqlite3.connect(shadow_db)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        create_schema(conn)
        conn.commit()

        row_counts: dict[str, int] = {}
        for stem, gz_path in gz_paths.items():
            table = STEM_TO_TABLE.get(stem)
            if table is None:
                print(f"Unknown stem {stem!r}, skipping")
                continue
            columns = TABLE_COLUMNS[table]
            min_rows = (
                min_rows_override if min_rows_override is not None else MIN_ROWS.get(table, 0)
            )
            print(f"Importing {stem} -> {table}...")
            if on_table_start:
                on_table_start(table)
            _t, _cb = table, on_table_progress
            _progress_cb = (lambda t, cb: lambda n: cb(t, n))(_t, _cb) if _cb else None
            count = import_table(conn, gz_path, table, columns, min_rows, _progress_cb)
            row_counts[table] = count
            if on_table_done:
                on_table_done(table, count)
            print(f"   {count:,} rows")

        # Record import timestamp and row counts
        conn.execute(
            "INSERT OR REPLACE INTO import_meta VALUES (?, ?)",
            ("last_refresh", datetime.now(timezone.utc).isoformat()),
        )
        conn.execute(
            "INSERT OR REPLACE INTO import_meta VALUES (?, ?)",
            ("row_counts", json.dumps(row_counts)),
        )
        conn.commit()
        conn.close()
        conn = None

        # Atomic swap — requires live_db and shadow_db on the same filesystem
        try:
            os.replace(shadow_db, live_db)
        except OSError as e:
            if e.errno == 18:  # EXDEV: cross-device link
                raise RuntimeError(
                    f"Cannot atomically swap {shadow_db} -> {live_db}: different filesystems. "
                    "Ensure DATA_DIR and TMP_DIR are on the same volume."
                ) from e
            raise

        print("Import complete, DB swapped")

    except Exception:
        if conn:
            try:
                conn.close()
            except Exception:  # nosec B110
                pass
        if shadow_db.exists():
            shadow_db.unlink(missing_ok=True)
        traceback.print_exc()
        raise
