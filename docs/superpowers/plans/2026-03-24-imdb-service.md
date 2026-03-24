# IMDB Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `imdb-service/` — a FastAPI microservice that downloads the full IMDB public datasets daily and serves title/person lookup, pre-computed ranked charts, and filtered search.

**Architecture:** Three modules: `importer.py` handles dataset download (async httpx) and bulk SQLite import (stdlib sqlite3 in a thread), `charts.py` owns the Bayesian-ranked in-memory chart cache, and `main.py` contains all FastAPI endpoints (reads via aiosqlite). A daily asyncio worker swaps an atomic shadow DB and rebuilds the chart cache.

**Tech Stack:** Python 3.12, FastAPI, aiosqlite, sqlite3 (stdlib), httpx, pytest, pytest-asyncio, pytest-cov

---

## File Map

| File | Responsibility |
|---|---|
| `imdb-service/main.py` | FastAPI app, all endpoints, lifespan, refresh worker |
| `imdb-service/importer.py` | Schema creation, TSV parsing, download, bulk import, atomic swap |
| `imdb-service/charts.py` | Chart configs, Bayesian formula, in-memory cache |
| `imdb-service/Dockerfile` | Container image |
| `imdb-service/requirements.txt` | Runtime dependencies |
| `imdb-service/requirements-dev.txt` | Dev/test dependencies |
| `imdb-service/pytest.ini` | Test config (mirrors anidb-service) |
| `imdb-service/test_main.py` | All tests |
| `docker-compose.yml` | Add imdb-service entry |
| `Caddyfile.example` | Add `/imdb-service/*` route |

---

## Task 1: Project Scaffold

**Files:**
- Create: `imdb-service/requirements.txt`
- Create: `imdb-service/requirements-dev.txt`
- Create: `imdb-service/pytest.ini`
- Create: `imdb-service/Dockerfile`
- Create: `imdb-service/importer.py` (empty stub)
- Create: `imdb-service/charts.py` (empty stub)
- Create: `imdb-service/main.py` (empty stub)
- Create: `imdb-service/test_main.py` (empty stub)

- [ ] **Step 1: Create `imdb-service/requirements.txt`**

```
aiosqlite
fastapi
httpx
uvicorn[standard]
```

- [ ] **Step 2: Create `imdb-service/requirements-dev.txt`**

```
pytest
pytest-asyncio
pytest-cov
httpx
```

- [ ] **Step 3: Create `imdb-service/pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
testpaths = .
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    -v
    --tb=short
    --strict-markers
    --cov=.
    --cov-report=html
    --cov-report=term-missing
    --cov-report=xml
    --cov-fail-under=85
    --cov-branch
markers =
    asyncio: mark test as async

[coverage:run]
omit =
    test_*.py
    __pycache__/*
    .pytest_cache/*
    htmlcov/*
    */__pycache__/*

[coverage:report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    @abstractmethod
    @abc.abstractmethod
```

- [ ] **Step 4: Create `imdb-service/Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py importer.py charts.py ./

RUN mkdir -p /app/data

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 5: Create empty stubs for the three Python modules**

`imdb-service/importer.py`:
```python
"""IMDB dataset download and SQLite import."""
```

`imdb-service/charts.py`:
```python
"""Pre-computed IMDB chart cache."""
```

`imdb-service/main.py`:
```python
"""IMDB Service - FastAPI caching service for IMDB public datasets."""
```

`imdb-service/test_main.py`:
```python
"""Tests for IMDB service."""
```

- [ ] **Step 6: Verify the structure**

Run: `ls imdb-service/`
Expected: `Dockerfile  charts.py  importer.py  main.py  pytest.ini  requirements-dev.txt  requirements.txt  test_main.py`

- [ ] **Step 7: Install dev dependencies**

Run: `cd imdb-service && pip install -r requirements.txt -r requirements-dev.txt`
Expected: All packages installed without errors.

- [ ] **Step 8: Commit scaffold**

```bash
git add imdb-service/
git commit -m "feat(imdb-service): scaffold project structure"
```

---

## Task 2: Database Schema

**Files:**
- Modify: `imdb-service/importer.py`
- Modify: `imdb-service/test_main.py`

- [ ] **Step 1: Write the failing test**

In `test_main.py`:
```python
import os
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
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cursor.fetchall()}
        assert tables == {
            "title_basics", "title_ratings", "title_akas",
            "title_crew", "title_episode", "title_principals", "name_basics"
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
```

- [ ] **Step 2: Run to confirm failure**

Run: `cd imdb-service && pytest test_main.py::test_create_schema_creates_all_tables test_main.py::test_create_schema_creates_indexes -v`
Expected: FAIL with `ImportError` or `cannot import name 'create_schema'`

- [ ] **Step 3: Implement `create_schema` in `importer.py`**

```python
"""IMDB dataset download and SQLite import."""
import sqlite3

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
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `cd imdb-service && pytest test_main.py::test_create_schema_creates_all_tables test_main.py::test_create_schema_creates_indexes -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add imdb-service/importer.py imdb-service/test_main.py
git commit -m "feat(imdb-service): add database schema creation"
```

---

## Task 3: TSV Parsing and Bulk Import

**Files:**
- Modify: `imdb-service/importer.py`
- Modify: `imdb-service/test_main.py`

The IMDB TSV files have a header row, tab-separated columns, and use `\N` for NULL. Each file is gzip-compressed.

- [ ] **Step 1: Write failing tests**

```python
import gzip
import io
import sqlite3
import tempfile
from pathlib import Path


def _make_tsv_gz(header: str, rows: list[str]) -> bytes:
    """Build a gzip-compressed TSV bytes object for testing."""
    content = "\n".join([header] + rows) + "\n"
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as f:
        f.write(content.encode())
    return buf.getvalue()


def test_import_table_inserts_rows():
    data = _make_tsv_gz(
        "tconst\ttitleType\tprimaryTitle\toriginalTitle\tisAdult\tstartYear\tendYear\truntimeMinutes\tgenres",
        [
            "tt0000001\tshort\tCarmencita\tCarmencita\t0\t1894\t\\N\t1\tDocumentary,Short",
            "tt0000002\tshort\tLe clown\tLe clown\t0\t1892\t\\N\t5\tComedyShort",
        ],
    )
    with tempfile.NamedTemporaryFile(suffix=".tsv.gz", delete=False) as f:
        gz_path = Path(f.name)
        f.write(data)

    db_path = Path(tempfile.mktemp(suffix=".db"))
    try:
        conn = sqlite3.connect(db_path)
        from importer import create_schema, import_table
        create_schema(conn)
        conn.commit()
        count = import_table(
            conn,
            gz_path,
            "title_basics",
            ["tconst","titleType","primaryTitle","originalTitle","isAdult","startYear","endYear","runtimeMinutes","genres"],
            min_rows=1,
        )
        assert count == 2
        rows = conn.execute("SELECT tconst, startYear, endYear FROM title_basics ORDER BY tconst").fetchall()
        assert rows[0] == ("tt0000001", 1894, None)   # \N → NULL
        assert rows[1] == ("tt0000002", 1892, None)
        conn.close()
    finally:
        gz_path.unlink(missing_ok=True)
        db_path.unlink(missing_ok=True)


def test_import_table_raises_on_min_rows_not_met():
    data = _make_tsv_gz(
        "tconst\ttitleType\tprimaryTitle\toriginalTitle\tisAdult\tstartYear\tendYear\truntimeMinutes\tgenres",
        ["tt0000001\tshort\tCarmencita\tCarmencita\t0\t1894\t\\N\t1\tDocumentary,Short"],
    )
    with tempfile.NamedTemporaryFile(suffix=".tsv.gz", delete=False) as f:
        gz_path = Path(f.name)
        f.write(data)

    db_path = Path(tempfile.mktemp(suffix=".db"))
    try:
        conn = sqlite3.connect(db_path)
        from importer import create_schema, import_table
        create_schema(conn)
        conn.commit()
        with pytest.raises(ValueError, match="too few rows"):
            import_table(conn, gz_path, "title_basics",
                ["tconst","titleType","primaryTitle","originalTitle","isAdult","startYear","endYear","runtimeMinutes","genres"],
                min_rows=1000)
        conn.close()
    finally:
        gz_path.unlink(missing_ok=True)
        db_path.unlink(missing_ok=True)
```

- [ ] **Step 2: Run to confirm failure**

Run: `cd imdb-service && pytest test_main.py::test_import_table_inserts_rows test_main.py::test_import_table_raises_on_min_rows_not_met -v`
Expected: FAIL — `cannot import name 'import_table'`

- [ ] **Step 3: Implement `import_table` in `importer.py`**

```python
import gzip
import sqlite3
from pathlib import Path
from typing import Optional

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


def import_table(
    conn: sqlite3.Connection,
    gz_path: Path,
    table: str,
    columns: list[str],
    min_rows: int,
) -> int:
    """
    Parse a gzip TSV file and bulk-insert into the given table.

    Runs inside a single transaction; rolls back and raises on any error.
    Validates that at least min_rows were inserted.

    Returns the number of rows inserted.
    """
    placeholders = ",".join("?" * len(columns))
    sql = f"INSERT OR REPLACE INTO {table} VALUES ({placeholders})"  # nosec B608

    # Type coercion per column position based on expected types
    INT_COLS = {"isAdult", "startYear", "endYear", "runtimeMinutes", "numVotes",
                "ordering", "isOriginalTitle", "seasonNumber", "episodeNumber",
                "birthYear", "deathYear"}
    REAL_COLS = {"averageRating"}

    def coerce(col: str, val: str):
        if col in INT_COLS:
            return _int_or_none(val)
        if col in REAL_COLS:
            return _real_or_none(val)
        return _null(val)

    count = 0
    batch = []
    try:
        conn.execute("BEGIN")
        with gzip.open(gz_path, "rt", encoding="utf-8") as f:
            header = f.readline().strip().split("\t")
            # Map file columns to our expected columns (same order assumed)
            for line in f:
                parts = line.rstrip("\n").split("\t")
                row = tuple(coerce(col, val) for col, val in zip(columns, parts))
                batch.append(row)
                if len(batch) >= BATCH_SIZE:
                    conn.executemany(sql, batch)
                    count += len(batch)
                    batch = []
            if batch:
                conn.executemany(sql, batch)
                count += len(batch)

        if count < min_rows:
            conn.execute("ROLLBACK")
            raise ValueError(
                f"import_table({table}): too few rows — got {count}, expected ≥ {min_rows}"
            )

        conn.execute("COMMIT")
        return count
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `cd imdb-service && pytest test_main.py::test_import_table_inserts_rows test_main.py::test_import_table_raises_on_min_rows_not_met -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add imdb-service/importer.py imdb-service/test_main.py
git commit -m "feat(imdb-service): add TSV parsing and bulk import"
```

---

## Task 4: Dataset Download

**Files:**
- Modify: `imdb-service/importer.py`
- Modify: `imdb-service/test_main.py`

- [ ] **Step 1: Write failing tests**

```python
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile
import pytest


@pytest.mark.asyncio
async def test_download_datasets_creates_files():
    """download_datasets saves each dataset file to the target directory."""
    fake_gz_content = b"\x1f\x8b\x08\x00\x00\x00\x00\x00"  # valid gzip magic bytes

    async def fake_stream(*args, **kwargs):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        # aiter_bytes yields chunks
        async def aiter_bytes(chunk_size=None):
            yield fake_gz_content
        mock_response.aiter_bytes = aiter_bytes
        return mock_response

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.stream = MagicMock(return_value=MagicMock(
        __aenter__=AsyncMock(return_value=MagicMock(
            raise_for_status=MagicMock(),
            aiter_bytes=fake_stream.__wrapped__ if hasattr(fake_stream, '__wrapped__') else None
        )),
        __aexit__=AsyncMock(return_value=False)
    ))

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir)
        # Simpler approach: mock at the httpx.AsyncClient level
        with patch("importer.httpx") as mock_httpx:
            # Set up the mock so each stream context yields the fake content
            mock_resp = AsyncMock()
            mock_resp.raise_for_status = MagicMock()

            async def fake_aiter_bytes(chunk_size=65536):
                yield fake_gz_content

            mock_resp.aiter_bytes = fake_aiter_bytes

            mock_stream_ctx = AsyncMock()
            mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

            mock_client_instance = AsyncMock()
            mock_client_instance.stream = MagicMock(return_value=mock_stream_ctx)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=False)

            mock_httpx.AsyncClient = MagicMock(return_value=mock_client_instance)

            from importer import download_datasets
            result = await download_datasets(data_dir)

        assert len(result) == 7
        expected_stems = {
            "title.basics", "title.ratings", "title.akas",
            "title.crew", "title.episode", "title.principals", "name.basics"
        }
        assert set(result.keys()) == expected_stems
        for stem, path in result.items():
            assert path.exists()
            assert path.suffix == ".gz"
```

- [ ] **Step 2: Run to confirm failure**

Run: `cd imdb-service && pytest test_main.py::test_download_datasets_creates_files -v`
Expected: FAIL — `cannot import name 'download_datasets'`

- [ ] **Step 3: Implement `download_datasets` in `importer.py`**

```python
import asyncio
import httpx

IMDB_BASE_URL = "https://datasets.imdbws.com"

DATASET_FILES = {
    "title.basics":     "title.basics.tsv.gz",
    "title.ratings":    "title.ratings.tsv.gz",
    "title.akas":       "title.akas.tsv.gz",
    "title.crew":       "title.crew.tsv.gz",
    "title.episode":    "title.episode.tsv.gz",
    "title.principals": "title.principals.tsv.gz",
    "name.basics":      "name.basics.tsv.gz",
}


async def _download_one(client: httpx.AsyncClient, stem: str, filename: str, dest: Path) -> None:
    """Stream a single dataset file to disk."""
    url = f"{IMDB_BASE_URL}/{filename}"
    print(f"⬇️  Downloading {filename}...")
    async with client.stream("GET", url, timeout=600.0) as response:
        response.raise_for_status()
        with dest.open("wb") as f:
            async for chunk in response.aiter_bytes(65536):
                f.write(chunk)
    print(f"✅ Downloaded {filename} ({dest.stat().st_size // 1024 // 1024} MB)")


async def download_datasets(data_dir: Path) -> dict[str, Path]:
    """
    Download all 7 IMDB dataset files concurrently to data_dir.

    Returns a dict mapping stem → local Path.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {
        stem: data_dir / filename
        for stem, filename in DATASET_FILES.items()
    }

    async with httpx.AsyncClient() as client:
        tasks = [
            _download_one(client, stem, filename, paths[stem])
            for stem, filename in DATASET_FILES.items()
        ]
        await asyncio.gather(*tasks)

    return paths
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `cd imdb-service && pytest test_main.py::test_download_datasets_creates_files -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add imdb-service/importer.py imdb-service/test_main.py
git commit -m "feat(imdb-service): add concurrent dataset download"
```

---

## Task 5: Full Import Pipeline and Atomic Swap

**Files:**
- Modify: `imdb-service/importer.py`
- Modify: `imdb-service/test_main.py`

This task wires together schema creation, per-table import, index building, atomic DB swap, and failure handling.

- [ ] **Step 1: Write failing tests**

```python
def test_run_full_import_produces_populated_db(tmp_path):
    """run_full_import builds a valid SQLite DB and swaps it into place."""
    # Build minimal valid TSV.gz files for each dataset
    basics_data = _make_tsv_gz(
        "tconst\ttitleType\tprimaryTitle\toriginalTitle\tisAdult\tstartYear\tendYear\truntimeMinutes\tgenres",
        [f"tt{i:07d}\tmovie\tTitle {i}\tTitle {i}\t0\t2000\t\\N\t90\tAction" for i in range(1, 6)],
    )
    ratings_data = _make_tsv_gz(
        "tconst\taverageRating\tnumVotes",
        [f"tt{i:07d}\t{7.0 + i * 0.1:.1f}\t{50000 + i * 1000}" for i in range(1, 6)],
    )
    akas_data = _make_tsv_gz(
        "titleId\tordering\ttitle\tregion\tlanguage\ttypes\tattributes\tisOriginalTitle",
        [f"tt{i:07d}\t1\tTitle {i}\tUS\ten\t\\N\t\\N\t1" for i in range(1, 6)],
    )
    empty_crew = _make_tsv_gz("tconst\tdirectors\twriters", [f"tt{i:07d}\tnm000000{i}\t\\N" for i in range(1, 6)])
    empty_episode = _make_tsv_gz("tconst\tparentTconst\tseasonNumber\tepisodeNumber", [])
    empty_principals = _make_tsv_gz("tconst\tordering\tnconst\tcategory\tjob\tcharacters", [f"tt{i:07d}\t1\tnm000000{i}\tactor\t\\N\t\\N" for i in range(1, 6)])
    empty_names = _make_tsv_gz("nconst\tprimaryName\tbirthYear\tdeathYear\tprimaryProfession\tknownForTitles", [f"nm{i:07d}\tPerson {i}\t1970\t\\N\tactor\ttt{i:07d}" for i in range(1, 6)])

    gz_dir = tmp_path / "gz"
    gz_dir.mkdir()
    (gz_dir / "title.basics.tsv.gz").write_bytes(basics_data)
    (gz_dir / "title.ratings.tsv.gz").write_bytes(ratings_data)
    (gz_dir / "title.akas.tsv.gz").write_bytes(akas_data)
    (gz_dir / "title.crew.tsv.gz").write_bytes(empty_crew)
    (gz_dir / "title.episode.tsv.gz").write_bytes(empty_episode)
    (gz_dir / "title.principals.tsv.gz").write_bytes(empty_principals)
    (gz_dir / "name.basics.tsv.gz").write_bytes(empty_names)

    gz_paths = {stem: gz_dir / f"{stem}.tsv.gz" for stem in [
        "title.basics", "title.ratings", "title.akas",
        "title.crew", "title.episode", "title.principals", "name.basics"
    ]}

    live_db = tmp_path / "imdb.db"

    from importer import run_full_import
    # Use min_rows=0 to skip threshold checks for test data
    run_full_import(gz_paths, live_db, min_rows_override=0)

    assert live_db.exists()
    conn = sqlite3.connect(live_db)
    count = conn.execute("SELECT COUNT(*) FROM title_basics").fetchone()[0]
    assert count == 5
    conn.close()


def test_run_full_import_leaves_live_db_on_failure(tmp_path):
    """If import fails, the original live DB is untouched."""
    live_db = tmp_path / "imdb.db"
    # Create a "live" DB with known content
    conn = sqlite3.connect(live_db)
    conn.execute("CREATE TABLE sentinel (val TEXT)")
    conn.execute("INSERT INTO sentinel VALUES ('original')")
    conn.commit()
    conn.close()

    # Provide an invalid (empty) gzip file to trigger failure
    gz_dir = tmp_path / "gz"
    gz_dir.mkdir()
    bad_gz = gz_dir / "title.basics.tsv.gz"
    bad_gz.write_bytes(b"not valid gzip")

    gz_paths = {"title.basics": bad_gz}

    from importer import run_full_import
    with pytest.raises(Exception):
        run_full_import(gz_paths, live_db, min_rows_override=0)

    # Live DB must still be the original
    conn = sqlite3.connect(live_db)
    val = conn.execute("SELECT val FROM sentinel").fetchone()[0]
    assert val == "original"
    conn.close()
```

- [ ] **Step 2: Run to confirm failure**

Run: `cd imdb-service && pytest test_main.py::test_run_full_import_produces_populated_db test_main.py::test_run_full_import_leaves_live_db_on_failure -v`
Expected: FAIL — `cannot import name 'run_full_import'`

- [ ] **Step 3: Implement `run_full_import` in `importer.py`**

```python
import os
import traceback

# Column definitions per table (must match TSV file column order)
TABLE_COLUMNS: dict[str, list[str]] = {
    "title_basics":     ["tconst","titleType","primaryTitle","originalTitle","isAdult","startYear","endYear","runtimeMinutes","genres"],
    "title_ratings":    ["tconst","averageRating","numVotes"],
    "title_akas":       ["tconst","ordering","title","region","language","types","attributes","isOriginalTitle"],
    "title_crew":       ["tconst","directors","writers"],
    "title_episode":    ["tconst","parentTconst","seasonNumber","episodeNumber"],
    "title_principals": ["tconst","ordering","nconst","category","job","characters"],
    "name_basics":      ["nconst","primaryName","birthYear","deathYear","primaryProfession","knownForTitles"],
}

# Maps dataset stem → table name
STEM_TO_TABLE: dict[str, str] = {
    "title.basics":     "title_basics",
    "title.ratings":    "title_ratings",
    "title.akas":       "title_akas",
    "title.crew":       "title_crew",
    "title.episode":    "title_episode",
    "title.principals": "title_principals",
    "name.basics":      "name_basics",
}


def run_full_import(
    gz_paths: dict[str, Path],
    live_db: Path,
    min_rows_override: Optional[int] = None,
) -> None:
    """
    Import all dataset files into a shadow DB, then atomically replace live_db.

    gz_paths: dict mapping dataset stem → local .tsv.gz path
    live_db: path to the live SQLite DB to replace
    min_rows_override: if set, use this as min_rows for all tables (0 = no check; for tests)
    """
    shadow_db = live_db.parent / "imdb_shadow.db"

    # Clean up any previous failed shadow
    if shadow_db.exists():
        shadow_db.unlink()

    conn = None
    try:
        conn = sqlite3.connect(shadow_db)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        create_schema(conn)
        conn.commit()

        for stem, gz_path in gz_paths.items():
            table = STEM_TO_TABLE.get(stem)
            if table is None:
                print(f"⚠️  Unknown stem {stem!r}, skipping")
                continue
            columns = TABLE_COLUMNS[table]
            min_rows = min_rows_override if min_rows_override is not None else MIN_ROWS.get(table, 0)
            print(f"📥 Importing {stem} → {table}...")
            count = import_table(conn, gz_path, table, columns, min_rows)
            print(f"   {count:,} rows")

        # Record import timestamp
        conn.execute(
            "INSERT OR REPLACE INTO import_meta VALUES (?, ?)",
            ("last_refresh", __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()),
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
                    f"Cannot atomically swap {shadow_db} → {live_db}: different filesystems. "
                    "Ensure DATA_DIR and TMP_DIR are on the same volume."
                ) from e
            raise

        print("✅ Import complete, DB swapped")

    except Exception:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        if shadow_db.exists():
            shadow_db.unlink(missing_ok=True)
        traceback.print_exc()
        raise
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `cd imdb-service && pytest test_main.py::test_run_full_import_produces_populated_db test_main.py::test_run_full_import_leaves_live_db_on_failure -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add imdb-service/importer.py imdb-service/test_main.py
git commit -m "feat(imdb-service): add full import pipeline with atomic DB swap"
```

---

## Task 6: Charts Module

**Files:**
- Modify: `imdb-service/charts.py`
- Modify: `imdb-service/test_main.py`

Implement the Bayesian weighted rating formula and all 8 pre-computed charts.

WR formula: `WR = (v / (v + m)) * R + (m / (v + m)) * C`
- `v` = numVotes for the title
- `m` = MIN_VOTES_CHART (minimum votes threshold)
- `R` = averageRating for the title
- `C` = mean averageRating across all qualifying titles for this chart

- [ ] **Step 1: Write failing tests**

```python
def _seed_db_for_charts(db_path: Path):
    """Seed a test DB with minimal data for chart tests."""
    conn = sqlite3.connect(db_path)
    from importer import create_schema
    create_schema(conn)
    # 5 movies with ratings
    movies = [
        ("tt0000001", "movie", "Alpha",   "Alpha",   0, 2000, None, 120, "Action"),
        ("tt0000002", "movie", "Beta",    "Beta",    0, 2001, None, 90,  "Drama"),
        ("tt0000003", "movie", "Gamma",   "Gamma",   0, 2002, None, 100, "Comedy"),
        ("tt0000004", "tvSeries", "Delta","Delta",   0, 2003, 2005, None, "Drama"),
        ("tt0000005", "tvSeries", "Epsilon","Epsilon",0,2004, None, None, "Action"),
    ]
    conn.executemany("INSERT INTO title_basics VALUES (?,?,?,?,?,?,?,?,?)", movies)
    ratings = [
        ("tt0000001", 8.5, 30000),
        ("tt0000002", 7.0, 40000),
        ("tt0000003", 6.5, 35000),
        ("tt0000004", 9.0, 50000),
        ("tt0000005", 8.0, 60000),
    ]
    conn.executemany("INSERT INTO title_ratings VALUES (?,?,?)", ratings)
    # English akas for tt0000001 and tt0000002
    conn.execute("INSERT INTO title_akas VALUES ('tt0000001',1,'Alpha','US','en',NULL,NULL,1)")
    conn.execute("INSERT INTO title_akas VALUES ('tt0000002',1,'Beta','US','en',NULL,NULL,1)")
    conn.commit()
    conn.close()


def test_rebuild_all_charts_populates_cache(tmp_path):
    db_path = tmp_path / "imdb.db"
    _seed_db_for_charts(db_path)

    import charts
    charts.rebuild_all_charts(db_path, min_votes=25000)

    assert "top_movies" in charts.chart_cache
    assert "top_shows" in charts.chart_cache
    assert len(charts.chart_cache["top_movies"]) <= 3   # 3 movies qualify
    assert len(charts.chart_cache["top_shows"]) <= 2    # 2 tvSeries qualify


def test_top_movies_chart_is_sorted_by_weighted_rating(tmp_path):
    db_path = tmp_path / "imdb.db"
    _seed_db_for_charts(db_path)

    import charts
    charts.rebuild_all_charts(db_path, min_votes=25000)

    top = charts.chart_cache["top_movies"]
    # Alpha (8.5) should rank above Beta (7.0) and Gamma (6.5)
    ratings = [item["averageRating"] for item in top]
    assert ratings == sorted(ratings, reverse=True)


def test_lowest_rated_chart_is_ascending(tmp_path):
    db_path = tmp_path / "imdb.db"
    _seed_db_for_charts(db_path)

    import charts
    charts.rebuild_all_charts(db_path, min_votes=25000)

    bottom = charts.chart_cache["lowest_rated"]
    ratings = [item["averageRating"] for item in bottom]
    assert ratings == sorted(ratings)  # ascending


def test_top_english_chart_only_includes_english_titles(tmp_path):
    db_path = tmp_path / "imdb.db"
    _seed_db_for_charts(db_path)

    import charts
    charts.rebuild_all_charts(db_path, min_votes=25000)

    english = charts.chart_cache["top_english"]
    tconsts = {item["tconst"] for item in english}
    assert "tt0000001" in tconsts   # has en aka
    assert "tt0000002" in tconsts   # has en aka
    assert "tt0000003" not in tconsts  # no en aka


def test_chart_items_have_required_fields(tmp_path):
    db_path = tmp_path / "imdb.db"
    _seed_db_for_charts(db_path)

    import charts
    charts.rebuild_all_charts(db_path, min_votes=25000)

    item = charts.chart_cache["top_movies"][0]
    for field in ("tconst", "primaryTitle", "startYear", "averageRating", "numVotes", "rank"):
        assert field in item, f"Missing field: {field}"


def test_chart_cache_is_replaced_atomically(tmp_path):
    db_path = tmp_path / "imdb.db"
    _seed_db_for_charts(db_path)

    import charts
    charts.chart_cache = {"stale_key": [{"tconst": "ttOLD"}]}
    charts.rebuild_all_charts(db_path, min_votes=25000)

    assert "stale_key" not in charts.chart_cache
    assert "top_movies" in charts.chart_cache
```

- [ ] **Step 2: Run to confirm failure**

Run: `cd imdb-service && pytest test_main.py -k "chart" -v`
Expected: FAIL — `cannot import name 'rebuild_all_charts'` or `ModuleNotFoundError: charts`

- [ ] **Step 3: Implement `charts.py`**

```python
"""Pre-computed IMDB chart cache."""
import sqlite3
from pathlib import Path
from typing import Any

# Module-level chart cache. Keys are chart names, values are ordered lists of title dicts.
# Replaced atomically via rebuild_all_charts().
chart_cache: dict[str, list[dict[str, Any]]] = {}

# Chart definitions: name → (titleType filter, aka_filter, ascending)
# aka_filter is a tuple of (column, value) for a title_akas join, or None.
CHART_CONFIGS: dict[str, dict] = {
    "top_movies":    {"title_type": "movie",    "aka_filter": None,              "ascending": False},
    "top_shows":     {"title_type": "tvSeries", "aka_filter": None,              "ascending": False},
    "lowest_rated":  {"title_type": "movie",    "aka_filter": None,              "ascending": True},
    "top_english":   {"title_type": "movie",    "aka_filter": ("language", "en"),"ascending": False},
    "top_indian":    {"title_type": "movie",    "aka_filter": ("region", "IN"),  "ascending": False},
    "top_tamil":     {"title_type": "movie",    "aka_filter": ("language", "ta"),"ascending": False},
    "top_telugu":    {"title_type": "movie",    "aka_filter": ("language", "te"),"ascending": False},
    "top_malayalam": {"title_type": "movie",    "aka_filter": ("language", "ml"),"ascending": False},
}

DEFAULT_CHART_SIZE = 250
MAX_CHART_SIZE = 500


def _compute_chart(
    conn: sqlite3.Connection,
    config: dict,
    min_votes: int,
    limit: int = DEFAULT_CHART_SIZE,
) -> list[dict[str, Any]]:
    """
    Compute a single chart using the Bayesian weighted rating formula.

    WR = (v / (v + m)) * R + (m / (v + m)) * C
      v = numVotes, m = min_votes, R = averageRating, C = mean rating of all qualifying titles
    """
    title_type = config["title_type"]
    aka_filter = config["aka_filter"]
    ascending = config["ascending"]

    # Build the base query for qualifying titles
    if aka_filter:
        aka_col, aka_val = aka_filter
        base_sql = f"""
            SELECT tb.tconst, tb.primaryTitle, tb.startYear, tr.averageRating, tr.numVotes
            FROM title_basics tb
            JOIN title_ratings tr ON tb.tconst = tr.tconst
            WHERE tb.titleType = ?
              AND tr.numVotes >= ?
              AND EXISTS (
                  SELECT 1 FROM title_akas ta
                  WHERE ta.tconst = tb.tconst AND ta.{aka_col} = ?
              )
        """  # nosec B608 - aka_col is from internal CHART_CONFIGS dict, not user input
        params = (title_type, min_votes, aka_val)
    else:
        base_sql = """
            SELECT tb.tconst, tb.primaryTitle, tb.startYear, tr.averageRating, tr.numVotes
            FROM title_basics tb
            JOIN title_ratings tr ON tb.tconst = tr.tconst
            WHERE tb.titleType = ?
              AND tr.numVotes >= ?
        """
        params = (title_type, min_votes)

    rows = conn.execute(base_sql, params).fetchall()
    if not rows:
        return []

    # Compute C: mean averageRating across all qualifying titles
    mean_rating = sum(r[3] for r in rows) / len(rows)
    m = min_votes

    # Compute WR for each title
    def weighted_rating(r, c, v, m):
        return (v / (v + m)) * r + (m / (v + m)) * c

    scored = [
        (row[0], row[1], row[2], row[3], row[4],
         weighted_rating(row[3], mean_rating, row[4], m))
        for row in rows
    ]

    # Sort by WR (ascending=True for lowest_rated, descending for all others)
    scored.sort(key=lambda x: x[5], reverse=not ascending)

    # Build result list with 1-based rank
    return [
        {
            "tconst": item[0],
            "primaryTitle": item[1],
            "startYear": item[2],
            "averageRating": item[3],
            "numVotes": item[4],
            "rank": rank,
        }
        for rank, item in enumerate(scored[:limit], start=1)
    ]


def rebuild_all_charts(db_path: Path, min_votes: int) -> None:
    """
    Recompute all charts from db_path and atomically replace chart_cache.
    """
    global chart_cache

    conn = sqlite3.connect(db_path)
    try:
        new_cache = {}
        for name, config in CHART_CONFIGS.items():
            print(f"📊 Computing chart: {name}...")
            new_cache[name] = _compute_chart(conn, config, min_votes)
            print(f"   {len(new_cache[name])} entries")
        # Atomic replacement
        chart_cache = new_cache
        print("✅ Chart cache rebuilt")
    finally:
        conn.close()
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `cd imdb-service && pytest test_main.py -k "chart" -v`
Expected: All chart tests PASS

- [ ] **Step 5: Commit**

```bash
git add imdb-service/charts.py imdb-service/test_main.py
git commit -m "feat(imdb-service): add Bayesian chart ranking and cache"
```

---

## Task 7: FastAPI App Skeleton, /stats, and /

**Files:**
- Modify: `imdb-service/main.py`
- Modify: `imdb-service/test_main.py`

- [ ] **Step 1: Write failing tests**

```python
import os

# Set env vars before importing main — must be at module level
os.environ["DATA_DIR"] = "/tmp/test_imdb_data"

from fastapi.testclient import TestClient


def test_stats_returns_initializing_when_no_db(tmp_path, monkeypatch):
    import main
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "nonexistent.db")
    monkeypatch.setattr(main, "last_refresh", None)
    client = TestClient(main.app, raise_server_exceptions=False)
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "initializing"


def test_stats_returns_online_with_db(tmp_path, monkeypatch):
    db_path = tmp_path / "imdb.db"
    conn = sqlite3.connect(db_path)
    from importer import create_schema
    create_schema(conn)
    conn.execute("INSERT INTO import_meta VALUES ('last_refresh', '2026-03-24T03:00:00+00:00')")
    conn.commit()
    conn.close()

    import main
    monkeypatch.setattr(main, "DB_PATH", db_path)
    monkeypatch.setattr(main, "last_refresh", "2026-03-24T03:00:00+00:00")
    client = TestClient(main.app)
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "last_refresh" in data
    assert "title_basics" in data["table_counts"]


def test_root_returns_html(tmp_path, monkeypatch):
    import main
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "nonexistent.db")
    client = TestClient(main.app, raise_server_exceptions=False)
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "IMDB" in response.text
```

- [ ] **Step 2: Run to confirm failure**

Run: `cd imdb-service && pytest test_main.py -k "stats or root" -v`
Expected: FAIL — cannot import `main`

- [ ] **Step 3: Implement app skeleton in `main.py`**

```python
"""IMDB Service - FastAPI caching service for IMDB public datasets."""
import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import aiosqlite
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse

# --- Config ---
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
DB_PATH = DATA_DIR / "imdb.db"
ROOT_PATH = os.getenv("ROOT_PATH", "")
REFRESH_HOUR = int(os.getenv("REFRESH_HOUR", "3"))
MIN_VOTES_CHART = int(os.getenv("MIN_VOTES_CHART", "25000"))

# --- Global state ---
last_refresh: Optional[str] = None  # ISO 8601 UTC string
refresh_worker_task: Optional[asyncio.Task] = None

import charts  # noqa: E402 — after config so charts can be imported


@asynccontextmanager
async def lifespan(app: FastAPI):
    global last_refresh, refresh_worker_task

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print("🔧 Initializing IMDB Service...")

    if DB_PATH.exists():
        # Load last refresh time from DB
        try:
            async with aiosqlite.connect(DB_PATH) as db:
                cursor = await db.execute(
                    "SELECT value FROM import_meta WHERE key = 'last_refresh'"
                )
                row = await cursor.fetchone()
                if row:
                    last_refresh = row[0]
        except Exception as e:
            print(f"⚠️  Could not read last_refresh: {e}")

        # Rebuild chart cache from existing DB
        try:
            import asyncio as _asyncio
            await _asyncio.to_thread(charts.rebuild_all_charts, DB_PATH, MIN_VOTES_CHART)
        except Exception as e:
            print(f"⚠️  Chart rebuild failed: {e}")
    else:
        print("⚠️  No DB found — starting initial import in background")
        refresh_worker_task = asyncio.create_task(_initial_import_then_schedule())
        yield
        if refresh_worker_task:
            refresh_worker_task.cancel()
            try:
                await refresh_worker_task
            except asyncio.CancelledError:
                pass
        return

    refresh_worker_task = asyncio.create_task(_refresh_scheduler())
    print("✅ IMDB Service ready")
    yield

    print("🛑 Shutting down...")
    if refresh_worker_task:
        refresh_worker_task.cancel()
        try:
            await refresh_worker_task
        except asyncio.CancelledError:
            pass


async def _run_import_pipeline() -> None:
    """Download datasets and import into shadow DB, then rebuild charts."""
    global last_refresh
    from importer import download_datasets, run_full_import

    print("🔄 Starting daily refresh...")
    gz_paths = await download_datasets(DATA_DIR)
    await asyncio.to_thread(run_full_import, gz_paths, DB_PATH)

    # Read new last_refresh from DB
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT value FROM import_meta WHERE key = 'last_refresh'")
        row = await cursor.fetchone()
        if row:
            last_refresh = row[0]

    await asyncio.to_thread(charts.rebuild_all_charts, DB_PATH, MIN_VOTES_CHART)
    print("✅ Refresh complete")


async def _initial_import_then_schedule() -> None:
    """Run initial import immediately, then hand off to scheduler."""
    try:
        await _run_import_pipeline()
    except Exception as e:
        print(f"❌ Initial import failed: {e}")
    # Proceed to normal schedule regardless
    await _refresh_scheduler()


async def _refresh_scheduler() -> None:
    """Sleep until REFRESH_HOUR UTC daily, then run the import pipeline."""
    while True:
        now = datetime.now(timezone.utc)
        target = now.replace(hour=REFRESH_HOUR, minute=0, second=0, microsecond=0)
        if target <= now:
            from datetime import timedelta
            target = target + timedelta(days=1)
        sleep_secs = (target - now).total_seconds()
        print(f"💤 Next refresh in {sleep_secs / 3600:.1f}h (at {target.isoformat()})")
        await asyncio.sleep(sleep_secs)
        try:
            await _run_import_pipeline()
        except Exception as e:
            print(f"❌ Scheduled refresh failed: {e}")


app = FastAPI(
    title="IMDB Service",
    lifespan=lifespan,
    root_path=ROOT_PATH,
)


def _db_is_ready() -> bool:
    return DB_PATH.exists()


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    base = f"{request.url.scheme}://{request.headers.get('host', request.url.netloc)}"
    if ROOT_PATH:
        base += ROOT_PATH
    return HTMLResponse(content=f"""<!DOCTYPE html>
<html><head><title>IMDB Service</title></head>
<body>
<h1>IMDB Service</h1>
<p>Cached IMDB public dataset service for Kometa.</p>
<ul>
  <li><a href="{base}/stats">GET /stats</a> — service health</li>
  <li><a href="{base}/title/tt0111161">GET /title/{{imdb_id}}</a> — title lookup</li>
  <li><a href="{base}/person/nm0000093">GET /person/{{imdb_id}}</a> — person lookup</li>
  <li><a href="{base}/chart/top_movies">GET /chart/{{chart_name}}</a> — pre-computed charts</li>
  <li><a href="{base}/search?type=movie&rating.gte=8&limit=10">GET /search</a> — filtered search</li>
</ul>
<p>Available charts: top_movies, top_shows, lowest_rated, top_english, top_indian, top_tamil, top_telugu, top_malayalam</p>
</body></html>
""")


@app.get("/stats")
async def get_stats() -> Dict[str, Any]:
    if not _db_is_ready():
        return {"status": "initializing", "last_refresh": None, "table_counts": {}}

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            counts = {}
            for table in ("title_basics", "title_ratings", "title_akas",
                          "title_crew", "title_episode", "title_principals", "name_basics"):
                cursor = await db.execute(f"SELECT COUNT(*) FROM {table}")  # nosec B608
                row = await cursor.fetchone()
                counts[table] = row[0] if row else 0

        return {
            "status": "online",
            "last_refresh": last_refresh,
            "table_counts": counts,
            "charts_cached": list(charts.chart_cache.keys()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `cd imdb-service && pytest test_main.py -k "stats or root" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add imdb-service/main.py imdb-service/test_main.py
git commit -m "feat(imdb-service): add app skeleton, /stats, and / endpoints"
```

---

## Task 8: GET /title/{imdb_id}

**Files:**
- Modify: `imdb-service/main.py`
- Modify: `imdb-service/test_main.py`

- [ ] **Step 1: Write failing tests**

```python
def _seed_full_test_db(db_path: Path):
    """Seed a test DB with a complete set of test data for endpoint tests."""
    conn = sqlite3.connect(db_path)
    from importer import create_schema
    create_schema(conn)

    conn.execute("INSERT INTO title_basics VALUES ('tt0111161','movie','The Shawshank Redemption','The Shawshank Redemption',0,1994,NULL,142,'Drama')")
    conn.execute("INSERT INTO title_basics VALUES ('tt0096697','tvSeries','The Simpsons','The Simpsons',0,1989,NULL,22,'Animation,Comedy')")
    conn.execute("INSERT INTO title_ratings VALUES ('tt0111161', 9.3, 2800000)")
    conn.execute("INSERT INTO title_ratings VALUES ('tt0096697', 8.0, 500000)")
    conn.execute("INSERT INTO title_crew VALUES ('tt0111161','nm0001104',NULL)")
    conn.execute("INSERT INTO title_principals VALUES ('tt0111161',1,'nm0000209','actor',NULL,'[\"Andy Dufresne\"]')")
    conn.execute("INSERT INTO title_principals VALUES ('tt0111161',2,'nm0000151','actor',NULL,'[\"Ellis Boyd Redding\"]')")
    conn.execute("INSERT INTO title_episode VALUES ('tt0502973','tt0096697',1,1)")
    conn.execute("INSERT INTO name_basics VALUES ('nm0001104','Frank Darabont',1959,NULL,'director,writer,producer','tt0111161')")
    conn.commit()
    conn.close()


def test_get_title_returns_full_record(tmp_path, monkeypatch):
    db_path = tmp_path / "imdb.db"
    _seed_full_test_db(db_path)
    import main
    monkeypatch.setattr(main, "DB_PATH", db_path)
    client = TestClient(main.app)

    response = client.get("/title/tt0111161")
    assert response.status_code == 200
    data = response.json()
    assert data["tconst"] == "tt0111161"
    assert data["primaryTitle"] == "The Shawshank Redemption"
    assert data["averageRating"] == 9.3
    assert data["numVotes"] == 2800000
    assert data["directors"] == "nm0001104"
    assert len(data["principals"]) == 2


def test_get_title_includes_episode_count_for_series(tmp_path, monkeypatch):
    db_path = tmp_path / "imdb.db"
    _seed_full_test_db(db_path)
    import main
    monkeypatch.setattr(main, "DB_PATH", db_path)
    client = TestClient(main.app)

    response = client.get("/title/tt0096697")
    assert response.status_code == 200
    data = response.json()
    assert data["episode_count"] == 1


def test_get_title_returns_404_for_unknown(tmp_path, monkeypatch):
    db_path = tmp_path / "imdb.db"
    _seed_full_test_db(db_path)
    import main
    monkeypatch.setattr(main, "DB_PATH", db_path)
    client = TestClient(main.app)

    response = client.get("/title/tt9999999")
    assert response.status_code == 404


def test_get_title_returns_503_when_no_db(tmp_path, monkeypatch):
    import main
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "nonexistent.db")
    client = TestClient(main.app, raise_server_exceptions=False)
    response = client.get("/title/tt0111161")
    assert response.status_code == 503
```

- [ ] **Step 2: Run to confirm failure**

Run: `cd imdb-service && pytest test_main.py -k "get_title" -v`
Expected: FAIL — 404/422 for all since endpoint doesn't exist yet

- [ ] **Step 3: Implement `GET /title/{imdb_id}` in `main.py`**

```python
@app.get("/title/{imdb_id}")
async def get_title(imdb_id: str) -> Dict[str, Any]:
    """Return full title record by IMDb ID (e.g. tt0111161)."""
    if not _db_is_ready():
        raise HTTPException(status_code=503, detail="Service initializing")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Basic info + rating
        cursor = await db.execute(
            """
            SELECT tb.*, tr.averageRating, tr.numVotes
            FROM title_basics tb
            LEFT JOIN title_ratings tr ON tb.tconst = tr.tconst
            WHERE tb.tconst = ?
            """,
            (imdb_id,),
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Title {imdb_id!r} not found")

        result = dict(row)

        # Crew
        cursor = await db.execute(
            "SELECT directors, writers FROM title_crew WHERE tconst = ?", (imdb_id,)
        )
        crew = await cursor.fetchone()
        result["directors"] = crew["directors"] if crew else None
        result["writers"] = crew["writers"] if crew else None

        # Principals (ordered)
        cursor = await db.execute(
            """
            SELECT nconst, ordering, category, job, characters
            FROM title_principals WHERE tconst = ? ORDER BY ordering
            """,
            (imdb_id,),
        )
        principals = await cursor.fetchall()
        result["principals"] = [dict(p) for p in principals]

        # Episode count for series
        if result.get("titleType") in ("tvSeries", "tvMiniSeries"):
            cursor = await db.execute(
                "SELECT COUNT(*) FROM title_episode WHERE parentTconst = ?", (imdb_id,)
            )
            ep_row = await cursor.fetchone()
            result["episode_count"] = ep_row[0] if ep_row else 0

    return result
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `cd imdb-service && pytest test_main.py -k "get_title" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add imdb-service/main.py imdb-service/test_main.py
git commit -m "feat(imdb-service): add GET /title/{imdb_id} endpoint"
```

---

## Task 9: GET /person/{imdb_id}

**Files:**
- Modify: `imdb-service/main.py`
- Modify: `imdb-service/test_main.py`

- [ ] **Step 1: Write failing tests**

```python
def test_get_person_returns_record(tmp_path, monkeypatch):
    db_path = tmp_path / "imdb.db"
    _seed_full_test_db(db_path)
    import main
    monkeypatch.setattr(main, "DB_PATH", db_path)
    client = TestClient(main.app)

    response = client.get("/person/nm0001104")
    assert response.status_code == 200
    data = response.json()
    assert data["nconst"] == "nm0001104"
    assert data["primaryName"] == "Frank Darabont"
    assert data["birthYear"] == 1959


def test_get_person_returns_404_for_unknown(tmp_path, monkeypatch):
    db_path = tmp_path / "imdb.db"
    _seed_full_test_db(db_path)
    import main
    monkeypatch.setattr(main, "DB_PATH", db_path)
    client = TestClient(main.app)

    response = client.get("/person/nm9999999")
    assert response.status_code == 404


def test_get_person_returns_503_when_no_db(tmp_path, monkeypatch):
    import main
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "nonexistent.db")
    client = TestClient(main.app, raise_server_exceptions=False)
    response = client.get("/person/nm0001104")
    assert response.status_code == 503
```

- [ ] **Step 2: Run to confirm failure**

Run: `cd imdb-service && pytest test_main.py -k "get_person" -v`
Expected: FAIL

- [ ] **Step 3: Implement `GET /person/{imdb_id}` in `main.py`**

```python
@app.get("/person/{imdb_id}")
async def get_person(imdb_id: str) -> Dict[str, Any]:
    """Return person record by IMDb person ID (e.g. nm0000093)."""
    if not _db_is_ready():
        raise HTTPException(status_code=503, detail="Service initializing")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM name_basics WHERE nconst = ?", (imdb_id,)
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Person {imdb_id!r} not found")
        return dict(row)
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `cd imdb-service && pytest test_main.py -k "get_person" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add imdb-service/main.py imdb-service/test_main.py
git commit -m "feat(imdb-service): add GET /person/{imdb_id} endpoint"
```

---

## Task 10: GET /chart/{chart_name}

**Files:**
- Modify: `imdb-service/main.py`
- Modify: `imdb-service/test_main.py`

- [ ] **Step 1: Write failing tests**

```python
def test_get_chart_top_movies_returns_list(tmp_path, monkeypatch):
    import main, charts
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "imdb.db")
    # Pre-populate chart cache
    charts.chart_cache = {
        "top_movies": [
            {"tconst": "tt0111161", "primaryTitle": "Shawshank", "startYear": 1994,
             "averageRating": 9.3, "numVotes": 2800000, "rank": 1},
        ]
    }
    client = TestClient(main.app)
    response = client.get("/chart/top_movies")
    assert response.status_code == 200
    data = response.json()
    assert data["chart"] == "top_movies"
    assert len(data["results"]) == 1
    assert data["results"][0]["tconst"] == "tt0111161"


def test_get_chart_respects_limit(tmp_path, monkeypatch):
    import main, charts
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "imdb.db")
    charts.chart_cache = {
        "top_movies": [
            {"tconst": f"tt{i:07d}", "primaryTitle": f"Movie {i}", "startYear": 2000,
             "averageRating": 8.0, "numVotes": 50000, "rank": i}
            for i in range(1, 11)
        ]
    }
    client = TestClient(main.app)
    response = client.get("/chart/top_movies?limit=3")
    assert response.status_code == 200
    assert len(response.json()["results"]) == 3


def test_get_chart_rejects_limit_above_max(tmp_path, monkeypatch):
    import main, charts
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "imdb.db")
    charts.chart_cache = {"top_movies": []}
    client = TestClient(main.app)
    response = client.get("/chart/top_movies?limit=999")
    assert response.status_code == 400


def test_get_chart_returns_404_for_unknown_chart(tmp_path, monkeypatch):
    import main, charts
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "imdb.db")
    charts.chart_cache = {}
    client = TestClient(main.app)
    response = client.get("/chart/nonexistent_chart")
    assert response.status_code == 404


def test_get_chart_returns_503_when_initializing(tmp_path, monkeypatch):
    import main, charts
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "nonexistent.db")
    charts.chart_cache = {}
    client = TestClient(main.app, raise_server_exceptions=False)
    response = client.get("/chart/top_movies")
    assert response.status_code == 503
```

- [ ] **Step 2: Run to confirm failure**

Run: `cd imdb-service && pytest test_main.py -k "get_chart" -v`
Expected: FAIL

- [ ] **Step 3: Implement `GET /chart/{chart_name}` in `main.py`**

```python
from charts import chart_cache, CHART_CONFIGS, DEFAULT_CHART_SIZE, MAX_CHART_SIZE


@app.get("/chart/{chart_name}")
async def get_chart(chart_name: str, limit: Optional[int] = None) -> Dict[str, Any]:
    """Return a pre-computed ranked chart of IMDb titles."""
    if not _db_is_ready() and not chart_cache:
        raise HTTPException(status_code=503, detail="Service initializing")

    if chart_name not in CHART_CONFIGS:
        raise HTTPException(status_code=404, detail=f"Unknown chart: {chart_name!r}. "
                            f"Valid charts: {list(CHART_CONFIGS.keys())}")

    if limit is not None and limit > MAX_CHART_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"limit must be ≤ {MAX_CHART_SIZE}"
        )

    results = chart_cache.get(chart_name, [])
    if limit is not None:
        results = results[:limit]
    else:
        results = results[:DEFAULT_CHART_SIZE]

    return {"chart": chart_name, "total": len(results), "results": results}
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `cd imdb-service && pytest test_main.py -k "get_chart" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add imdb-service/main.py imdb-service/test_main.py
git commit -m "feat(imdb-service): add GET /chart/{chart_name} endpoint"
```

---

## Task 11: GET /search — Basic Filters

**Files:**
- Modify: `imdb-service/main.py`
- Modify: `imdb-service/test_main.py`

Implements: `type`, `type.not`, `genre`, `genre.any`, `genre.not`, `rating.gte`, `rating.lte`, `votes.gte`, `votes.lte`, `runtime.gte`, `runtime.lte`, `release.after`, `release.before`, `title`, `adult`, `sort_by`, `limit`.

Note: FastAPI does not accept dots in query parameter names natively. Use `Query` aliases. Parameters with dots in their names must be declared with `alias="param.name"`.

- [ ] **Step 1: Write failing tests**

```python
def _seed_search_db(db_path: Path):
    """Seed DB with varied data for search tests."""
    conn = sqlite3.connect(db_path)
    from importer import create_schema
    create_schema(conn)
    titles = [
        ("tt0000001", "movie",    "Action Film",   "Action Film",   0, 2000, None, 120, "Action,Thriller"),
        ("tt0000002", "movie",    "Comedy Film",   "Comedy Film",   0, 2005, None, 90,  "Comedy"),
        ("tt0000003", "tvSeries", "Drama Series",  "Drama Series",  0, 2010, None, 45,  "Drama"),
        ("tt0000004", "movie",    "Short Film",    "Short Film",    0, 2015, None, 10,  "Short"),
        ("tt0000005", "movie",    "Adult Film",    "Adult Film",    1, 2018, None, 80,  "Drama"),
    ]
    conn.executemany("INSERT INTO title_basics VALUES (?,?,?,?,?,?,?,?,?)", titles)
    ratings = [
        ("tt0000001", 8.5, 100000),
        ("tt0000002", 7.0, 50000),
        ("tt0000003", 9.0, 200000),
        ("tt0000004", 6.0, 5000),
        ("tt0000005", 5.0, 2000),
    ]
    conn.executemany("INSERT INTO title_ratings VALUES (?,?,?)", ratings)
    conn.commit()
    conn.close()


def test_search_filter_by_type(tmp_path, monkeypatch):
    db_path = tmp_path / "imdb.db"
    _seed_search_db(db_path)
    import main
    monkeypatch.setattr(main, "DB_PATH", db_path)
    client = TestClient(main.app)

    response = client.get("/search?type=movie")
    assert response.status_code == 200
    data = response.json()
    tconsts = {r for r in data["results"]}
    assert "tt0000001" in tconsts
    assert "tt0000003" not in tconsts  # tvSeries


def test_search_filter_by_genre_any(tmp_path, monkeypatch):
    db_path = tmp_path / "imdb.db"
    _seed_search_db(db_path)
    import main
    monkeypatch.setattr(main, "DB_PATH", db_path)
    client = TestClient(main.app)

    response = client.get("/search?genre.any=Action,Comedy")
    assert response.status_code == 200
    data = response.json()
    assert "tt0000001" in data["results"]
    assert "tt0000002" in data["results"]
    assert "tt0000003" not in data["results"]  # Drama only


def test_search_filter_by_rating_gte(tmp_path, monkeypatch):
    db_path = tmp_path / "imdb.db"
    _seed_search_db(db_path)
    import main
    monkeypatch.setattr(main, "DB_PATH", db_path)
    client = TestClient(main.app)

    response = client.get("/search?rating.gte=8")
    assert response.status_code == 200
    data = response.json()
    assert "tt0000001" in data["results"]   # 8.5
    assert "tt0000003" in data["results"]   # 9.0
    assert "tt0000002" not in data["results"]  # 7.0


def test_search_excludes_adult_by_default(tmp_path, monkeypatch):
    db_path = tmp_path / "imdb.db"
    _seed_search_db(db_path)
    import main
    monkeypatch.setattr(main, "DB_PATH", db_path)
    client = TestClient(main.app)

    response = client.get("/search")
    assert response.status_code == 200
    data = response.json()
    assert "tt0000005" not in data["results"]


def test_search_includes_adult_when_requested(tmp_path, monkeypatch):
    db_path = tmp_path / "imdb.db"
    _seed_search_db(db_path)
    import main
    monkeypatch.setattr(main, "DB_PATH", db_path)
    client = TestClient(main.app)

    response = client.get("/search?adult=true")
    assert response.status_code == 200
    data = response.json()
    assert "tt0000005" in data["results"]


def test_search_sort_by_year_asc(tmp_path, monkeypatch):
    db_path = tmp_path / "imdb.db"
    _seed_search_db(db_path)
    import main
    monkeypatch.setattr(main, "DB_PATH", db_path)
    client = TestClient(main.app)

    response = client.get("/search?sort_by=year.asc&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["results"][0] == "tt0000001"  # 2000 is first


def test_search_limit(tmp_path, monkeypatch):
    db_path = tmp_path / "imdb.db"
    _seed_search_db(db_path)
    import main
    monkeypatch.setattr(main, "DB_PATH", db_path)
    client = TestClient(main.app)

    response = client.get("/search?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) <= 2


def test_search_rejects_imdb_top_and_bottom_together(tmp_path, monkeypatch):
    import main, charts
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "imdb.db")
    charts.chart_cache = {"top_movies": [], "lowest_rated": []}
    client = TestClient(main.app)
    response = client.get("/search?imdb_top=100&imdb_bottom=50")
    assert response.status_code == 400
```

- [ ] **Step 2: Run to confirm failure**

Run: `cd imdb-service && pytest test_main.py -k "test_search" -v`
Expected: FAIL — `/search` endpoint doesn't exist

- [ ] **Step 3: Implement `GET /search` with basic filters in `main.py`**

```python
from datetime import date
from typing import List, Optional
from fastapi import Query

SORT_COLUMN_MAP = {
    "rating":  "tr.averageRating",
    "votes":   "tr.numVotes",
    "year":    "tb.startYear",
    "title":   "tb.primaryTitle",
}


def _parse_sort(sort_by: str) -> tuple[str, str]:
    """Parse 'rating.desc' → ('tr.averageRating', 'DESC'). Raises ValueError on invalid input."""
    parts = sort_by.rsplit(".", 1)
    col_key = parts[0]
    direction = parts[1].upper() if len(parts) == 2 else "DESC"
    if col_key not in SORT_COLUMN_MAP:
        raise ValueError(f"Invalid sort column: {col_key!r}")
    if direction not in ("ASC", "DESC"):
        raise ValueError(f"Invalid sort direction: {direction!r}")
    return SORT_COLUMN_MAP[col_key], direction


@app.get("/search")
async def search(
    # Type filters
    type: Optional[str] = Query(None, alias="type"),
    type_not: Optional[str] = Query(None, alias="type.not"),
    # Genre filters
    genre: Optional[str] = Query(None, alias="genre"),
    genre_any: Optional[str] = Query(None, alias="genre.any"),
    genre_not: Optional[str] = Query(None, alias="genre.not"),
    # Rating/votes filters
    rating_gte: Optional[float] = Query(None, alias="rating.gte"),
    rating_lte: Optional[float] = Query(None, alias="rating.lte"),
    votes_gte: Optional[int] = Query(None, alias="votes.gte"),
    votes_lte: Optional[int] = Query(None, alias="votes.lte"),
    # Runtime filters
    runtime_gte: Optional[int] = Query(None, alias="runtime.gte"),
    runtime_lte: Optional[int] = Query(None, alias="runtime.lte"),
    # Release year filters
    release_after: Optional[str] = Query(None, alias="release.after"),
    release_before: Optional[str] = Query(None, alias="release.before"),
    # Title search
    title: Optional[str] = None,
    # Content
    adult: bool = False,
    # Chart rank filters
    imdb_top: Optional[int] = None,
    imdb_bottom: Optional[int] = None,
    # Sorting and pagination
    sort_by: str = "rating.desc",
    limit: int = Query(default=100, le=1000),
    # Join filters (handled in Task 12)
    language: Optional[str] = Query(None, alias="language"),
    language_any: Optional[str] = Query(None, alias="language.any"),
    language_not: Optional[str] = Query(None, alias="language.not"),
    language_primary: Optional[str] = Query(None, alias="language.primary"),
    country: Optional[str] = Query(None, alias="country"),
    country_any: Optional[str] = Query(None, alias="country.any"),
    country_not: Optional[str] = Query(None, alias="country.not"),
    country_origin: Optional[str] = Query(None, alias="country.origin"),
    cast: Optional[str] = Query(None, alias="cast"),
    cast_any: Optional[str] = Query(None, alias="cast.any"),
    cast_not: Optional[str] = Query(None, alias="cast.not"),
    series: Optional[str] = Query(None, alias="series"),
    series_not: Optional[str] = Query(None, alias="series.not"),
) -> Dict[str, Any]:
    """Filtered title search returning IMDb IDs."""
    if not _db_is_ready():
        raise HTTPException(status_code=503, detail="Service initializing")

    if imdb_top is not None and imdb_bottom is not None:
        raise HTTPException(status_code=400, detail="imdb_top and imdb_bottom are mutually exclusive")

    try:
        sort_col, sort_dir = _parse_sort(sort_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Resolve imdb_top/imdb_bottom to a set of tconsts from chart cache
    allowed_tconsts: Optional[set] = None
    if imdb_top is not None:
        top_chart = chart_cache.get("top_movies", [])
        allowed_tconsts = {item["tconst"] for item in top_chart if item["rank"] <= imdb_top}
    elif imdb_bottom is not None:
        bottom_chart = chart_cache.get("lowest_rated", [])
        allowed_tconsts = {item["tconst"] for item in bottom_chart if item["rank"] <= imdb_bottom}

    # Build SQL
    conditions: list[str] = []
    params: list = []

    # Adult filter — exclude adult content unless explicitly requested
    if not adult:
        conditions.append("tb.isAdult = 0")

    # Type
    if type:
        types = [t.strip() for t in type.split(",")]
        placeholders = ",".join("?" * len(types))
        conditions.append(f"tb.titleType IN ({placeholders})")  # nosec B608
        params.extend(types)
    if type_not:
        types = [t.strip() for t in type_not.split(",")]
        placeholders = ",".join("?" * len(types))
        conditions.append(f"tb.titleType NOT IN ({placeholders})")  # nosec B608
        params.extend(types)

    # Genre — all must match (comma-sep = AND of LIKEs)
    if genre:
        for g in genre.split(","):
            conditions.append("(tb.genres LIKE ? OR tb.genres LIKE ? OR tb.genres LIKE ? OR tb.genres = ?)")
            g = g.strip()
            params.extend([f"{g},%", f"%,{g},%", f"%,{g}", g])

    # Genre.any — at least one must match
    if genre_any:
        gs = [g.strip() for g in genre_any.split(",")]
        sub = " OR ".join(
            "(tb.genres LIKE ? OR tb.genres LIKE ? OR tb.genres LIKE ? OR tb.genres = ?)"
            for _ in gs
        )
        conditions.append(f"({sub})")
        for g in gs:
            params.extend([f"{g},%", f"%,{g},%", f"%,{g}", g])

    # Genre.not
    if genre_not:
        for g in genre_not.split(","):
            g = g.strip()
            conditions.append("(tb.genres NOT LIKE ? AND tb.genres NOT LIKE ? AND tb.genres NOT LIKE ? AND tb.genres != ?)")
            params.extend([f"{g},%", f"%,{g},%", f"%,{g}", g])

    # Rating
    if rating_gte is not None:
        conditions.append("tr.averageRating >= ?")
        params.append(rating_gte)
    if rating_lte is not None:
        conditions.append("tr.averageRating <= ?")
        params.append(rating_lte)

    # Votes
    if votes_gte is not None:
        conditions.append("tr.numVotes >= ?")
        params.append(votes_gte)
    if votes_lte is not None:
        conditions.append("tr.numVotes <= ?")
        params.append(votes_lte)

    # Runtime
    if runtime_gte is not None:
        conditions.append("tb.runtimeMinutes >= ?")
        params.append(runtime_gte)
    if runtime_lte is not None:
        conditions.append("tb.runtimeMinutes <= ?")
        params.append(runtime_lte)

    # Release year
    def _year_from(s: str) -> int:
        if s.lower() == "today":
            return date.today().year
        return int(s[:4])

    if release_after:
        conditions.append("tb.startYear > ?")
        params.append(_year_from(release_after))
    if release_before:
        conditions.append("tb.startYear < ?")
        params.append(_year_from(release_before))

    # Title text search
    if title:
        conditions.append("tb.primaryTitle LIKE ?")
        params.append(f"%{title}%")

    # Join filters (language, country, cast, series)
    joins: list[str] = []
    _add_join_filters(
        joins, conditions, params,
        language, language_any, language_not, language_primary,
        country, country_any, country_not, country_origin,
        cast, cast_any, cast_not,
        series, series_not,
    )

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    join_clause = " ".join(joins)

    sql = f"""
        SELECT DISTINCT tb.tconst
        FROM title_basics tb
        LEFT JOIN title_ratings tr ON tb.tconst = tr.tconst
        {join_clause}
        {where_clause}
        ORDER BY {sort_col} {sort_dir}
        LIMIT ?
    """  # nosec B608 — sort_col/sort_dir are validated against SORT_COLUMN_MAP

    params.append(limit)

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {e}")

    results = [row[0] for row in rows]

    # Apply imdb_top/imdb_bottom filter (post-query, from chart cache)
    if allowed_tconsts is not None:
        results = [t for t in results if t in allowed_tconsts]

    return {"results": results, "total": len(results)}


def _add_join_filters(
    joins, conditions, params,
    language, language_any, language_not, language_primary,
    country, country_any, country_not, country_origin,
    cast, cast_any, cast_not,
    series, series_not,
):
    """Append JOIN clauses and WHERE conditions for join-based filters. Implemented in Task 12."""
    pass  # placeholder — filled in Task 12
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `cd imdb-service && pytest test_main.py -k "test_search" -v`
Expected: All search tests in this task PASS

- [ ] **Step 5: Commit**

```bash
git add imdb-service/main.py imdb-service/test_main.py
git commit -m "feat(imdb-service): add GET /search with basic filters"
```

---

## Task 12: GET /search — Join Filters

**Files:**
- Modify: `imdb-service/main.py`
- Modify: `imdb-service/test_main.py`

Implements: `language`, `language.any`, `language.not`, `language.primary`, `country`, `country.any`, `country.not`, `country.origin`, `cast`, `cast.any`, `cast.not`, `series`, `series.not`.

- [ ] **Step 1: Write failing tests**

```python
def _seed_join_search_db(db_path: Path):
    """Seed DB with data for join-filter search tests."""
    conn = sqlite3.connect(db_path)
    from importer import create_schema
    create_schema(conn)
    titles = [
        ("tt0000001", "movie", "English Film",  "English Film",  0, 2000, None, 120, "Drama"),
        ("tt0000002", "movie", "French Film",   "French Film",   0, 2001, None, 100, "Drama"),
        ("tt0000003", "movie", "Hindi Film",    "Hindi Film",    0, 2002, None, 90,  "Drama"),
        ("tt0000004", "tvEpisode", "Episode 1", "Episode 1",     0, 2010, None, 45,  "Drama"),
    ]
    conn.executemany("INSERT INTO title_basics VALUES (?,?,?,?,?,?,?,?,?)", titles)
    conn.executemany("INSERT INTO title_ratings VALUES (?,?,?)", [
        ("tt0000001", 8.0, 50000), ("tt0000002", 7.5, 40000),
        ("tt0000003", 7.0, 30000), ("tt0000004", 8.5, 10000),
    ])
    # AKAs: language
    conn.execute("INSERT INTO title_akas VALUES ('tt0000001',1,'English Film','US','en',NULL,NULL,1)")
    conn.execute("INSERT INTO title_akas VALUES ('tt0000002',1,'French Film','FR','fr',NULL,NULL,1)")
    conn.execute("INSERT INTO title_akas VALUES ('tt0000003',1,'Hindi Film','IN','hi',NULL,NULL,1)")
    # Principals: cast
    conn.execute("INSERT INTO title_principals VALUES ('tt0000001',1,'nm0000001','actor',NULL,'[\"Hero\"]')")
    conn.execute("INSERT INTO title_principals VALUES ('tt0000002',1,'nm0000002','actor',NULL,'[\"Villain\"]')")
    # Episode: series
    conn.execute("INSERT INTO title_episode VALUES ('tt0000004','tt0000099',1,1)")
    conn.commit()
    conn.close()


def test_search_filter_by_language(tmp_path, monkeypatch):
    db_path = tmp_path / "imdb.db"
    _seed_join_search_db(db_path)
    import main
    monkeypatch.setattr(main, "DB_PATH", db_path)
    client = TestClient(main.app)

    response = client.get("/search?language=en")
    assert response.status_code == 200
    data = response.json()
    assert "tt0000001" in data["results"]
    assert "tt0000002" not in data["results"]


def test_search_filter_language_not(tmp_path, monkeypatch):
    db_path = tmp_path / "imdb.db"
    _seed_join_search_db(db_path)
    import main
    monkeypatch.setattr(main, "DB_PATH", db_path)
    client = TestClient(main.app)

    response = client.get("/search?language.not=fr&type=movie")
    assert response.status_code == 200
    data = response.json()
    assert "tt0000002" not in data["results"]   # fr excluded
    assert "tt0000001" in data["results"]


def test_search_filter_by_cast(tmp_path, monkeypatch):
    db_path = tmp_path / "imdb.db"
    _seed_join_search_db(db_path)
    import main
    monkeypatch.setattr(main, "DB_PATH", db_path)
    client = TestClient(main.app)

    response = client.get("/search?cast=nm0000001")
    assert response.status_code == 200
    data = response.json()
    assert "tt0000001" in data["results"]
    assert "tt0000002" not in data["results"]


def test_search_filter_by_series(tmp_path, monkeypatch):
    db_path = tmp_path / "imdb.db"
    _seed_join_search_db(db_path)
    import main
    monkeypatch.setattr(main, "DB_PATH", db_path)
    client = TestClient(main.app)

    response = client.get("/search?series=tt0000099")
    assert response.status_code == 200
    data = response.json()
    assert "tt0000004" in data["results"]
    assert "tt0000001" not in data["results"]
```

- [ ] **Step 2: Run to confirm failure**

Run: `cd imdb-service && pytest test_main.py -k "language or cast or series" -v`
Expected: FAIL — filters return all results since `_add_join_filters` is a no-op

- [ ] **Step 3: Implement `_add_join_filters` in `main.py`**

Replace the `pass` placeholder in `_add_join_filters`:

```python
def _add_join_filters(
    joins, conditions, params,
    language, language_any, language_not, language_primary,
    country, country_any, country_not, country_origin,
    cast, cast_any, cast_not,
    series, series_not,
):
    """Append JOIN clauses and WHERE conditions for join-based filters."""

    def _exists_aka(col: str, val: str, negate: bool = False) -> str:
        op = "NOT EXISTS" if negate else "EXISTS"
        return f"{op} (SELECT 1 FROM title_akas ta WHERE ta.tconst = tb.tconst AND ta.{col} = ?)"  # nosec B608

    def _exists_aka_original(col: str, val: str) -> str:
        return f"EXISTS (SELECT 1 FROM title_akas ta WHERE ta.tconst = tb.tconst AND ta.{col} = ? AND ta.isOriginalTitle = 1)"  # nosec B608

    # Language filters (each value must have an aka row with that language)
    if language:
        for lang in language.split(","):
            conditions.append(_exists_aka("language", lang.strip()))
            params.append(lang.strip())
    if language_any:
        langs = [l.strip() for l in language_any.split(",")]
        sub = " OR ".join(_exists_aka("language", l) for l in langs)
        conditions.append(f"({sub})")
        params.extend(langs)
    if language_not:
        for lang in language_not.split(","):
            conditions.append(_exists_aka("language", lang.strip(), negate=True))
            params.append(lang.strip())
    if language_primary:
        for lang in language_primary.split(","):
            conditions.append(_exists_aka_original("language", lang.strip()))
            params.append(lang.strip())

    # Country filters
    if country:
        for c in country.split(","):
            conditions.append(_exists_aka("region", c.strip()))
            params.append(c.strip())
    if country_any:
        cs = [c.strip() for c in country_any.split(",")]
        sub = " OR ".join(_exists_aka("region", c) for c in cs)
        conditions.append(f"({sub})")
        params.extend(cs)
    if country_not:
        for c in country_not.split(","):
            conditions.append(_exists_aka("region", c.strip(), negate=True))
            params.append(c.strip())
    if country_origin:
        for c in country_origin.split(","):
            conditions.append(_exists_aka_original("region", c.strip()))
            params.append(c.strip())

    # Cast filters
    def _exists_cast(val: str, negate: bool = False) -> str:
        op = "NOT EXISTS" if negate else "EXISTS"
        return f"{op} (SELECT 1 FROM title_principals tp WHERE tp.tconst = tb.tconst AND tp.nconst = ?)"

    if cast:
        for nm in cast.split(","):
            conditions.append(_exists_cast(nm.strip()))
            params.append(nm.strip())
    if cast_any:
        nms = [nm.strip() for nm in cast_any.split(",")]
        sub = " OR ".join(_exists_cast(nm) for nm in nms)
        conditions.append(f"({sub})")
        params.extend(nms)
    if cast_not:
        for nm in cast_not.split(","):
            conditions.append(_exists_cast(nm.strip(), negate=True))
            params.append(nm.strip())

    # Series filter
    if series:
        for s in series.split(","):
            conditions.append(
                "EXISTS (SELECT 1 FROM title_episode te WHERE te.tconst = tb.tconst AND te.parentTconst = ?)"
            )
            params.append(s.strip())
    if series_not:
        for s in series_not.split(","):
            conditions.append(
                "NOT EXISTS (SELECT 1 FROM title_episode te WHERE te.tconst = tb.tconst AND te.parentTconst = ?)"
            )
            params.append(s.strip())
```

- [ ] **Step 4: Run all search tests to confirm pass**

Run: `cd imdb-service && pytest test_main.py -k "search" -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add imdb-service/main.py imdb-service/test_main.py
git commit -m "feat(imdb-service): add join-based search filters (language, country, cast, series)"
```

---

## Task 13: Daily Refresh Worker

**Files:**
- Modify: `imdb-service/test_main.py`

The refresh worker implementation already exists in `main.py` from Task 7. This task adds tests for the scheduler logic.

- [ ] **Step 1: Write failing tests**

```python
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_refresh_scheduler_calls_pipeline_at_correct_time():
    """Scheduler sleeps until REFRESH_HOUR, then calls _run_import_pipeline."""
    call_count = 0

    async def fake_pipeline():
        nonlocal call_count
        call_count += 1

    async def fake_sleep(secs):
        pass  # Don't actually sleep in tests

    import main
    with patch.object(main, "_run_import_pipeline", fake_pipeline):
        with patch("asyncio.sleep", fake_sleep):
            # Cancel after one iteration
            task = asyncio.create_task(main._refresh_scheduler())
            await asyncio.sleep(0)  # yield to let one loop run
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    assert call_count >= 1


@pytest.mark.asyncio
async def test_refresh_scheduler_continues_after_pipeline_failure():
    """Scheduler logs the error and continues to next day rather than crashing."""
    call_count = 0

    async def failing_pipeline():
        nonlocal call_count
        call_count += 1
        raise RuntimeError("Download failed")

    async def fake_sleep(secs):
        if call_count >= 2:
            raise asyncio.CancelledError  # Stop after 2 iterations

    import main
    with patch.object(main, "_run_import_pipeline", failing_pipeline):
        with patch("asyncio.sleep", fake_sleep):
            task = asyncio.create_task(main._refresh_scheduler())
            try:
                await task
            except asyncio.CancelledError:
                pass

    assert call_count >= 1  # Called at least once despite failures
```

- [ ] **Step 2: Run to confirm failure**

Run: `cd imdb-service && pytest test_main.py -k "scheduler" -v`
Expected: FAIL

- [ ] **Step 3: Verify existing `_refresh_scheduler` handles the test cases**

Review `main.py::_refresh_scheduler`. The `try/except` around `_run_import_pipeline` already handles failures. If the tests fail for a different reason, adjust the scheduler to:

```python
async def _refresh_scheduler() -> None:
    while True:
        now = datetime.now(timezone.utc)
        target = now.replace(hour=REFRESH_HOUR, minute=0, second=0, microsecond=0)
        if target <= now:
            from datetime import timedelta
            target = target + timedelta(days=1)
        sleep_secs = (target - now).total_seconds()
        await asyncio.sleep(sleep_secs)
        try:
            await _run_import_pipeline()
        except Exception as e:
            print(f"❌ Scheduled refresh failed: {e}")
```

- [ ] **Step 4: Run tests to confirm pass**

Run: `cd imdb-service && pytest test_main.py -k "scheduler" -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite and verify ≥85% coverage**

Run: `cd imdb-service && pytest --cov=. --cov-report=term-missing`
Expected: All tests PASS, coverage ≥ 85%

If coverage is below 85%, identify uncovered branches and add targeted tests for error paths (e.g., DB connection failure in `/stats`, malformed imdb_id in `/title`).

- [ ] **Step 6: Commit**

```bash
git add imdb-service/test_main.py
git commit -m "test(imdb-service): add refresh scheduler tests and full coverage pass"
```

---

## Task 14: Docker and Deployment Configuration

**Files:**
- Modify: `docker-compose.yml`
- Modify: `Caddyfile.example`

- [ ] **Step 1: Add `imdb-service` to `docker-compose.yml`**

Open `docker-compose.yml` and add the following service before the `caddy:` block, and add `imdb-data:` to the `volumes:` section:

```yaml
  imdb-service:
    image: ghcr.io/kometa-team/imdb-service:latest
    container_name: imdb-service
    restart: unless-stopped
    environment:
      - ROOT_PATH=/imdb-service
      - REFRESH_HOUR=3
      - DATA_DIR=/app/data
      - TMP_DIR=/app/data
      - MIN_VOTES_CHART=25000
    volumes:
      - imdb-data:/app/data
    deploy:
      resources:
        limits:
          memory: 1G
        reservations:
          memory: 512M
```

And add to `volumes:`:
```yaml
  imdb-data:
```

- [ ] **Step 2: Verify docker-compose syntax**

Run: `docker compose config --quiet`
Expected: No errors

- [ ] **Step 3: Add `/imdb-service/*` route to `Caddyfile.example`**

After the `simkl-service` block (or the last service block before the `handle /` block), add:

```
    # Handle /imdb-service path
    # FastAPI service serving IMDB dataset API
    handle /imdb-service* {
        uri strip_prefix /imdb-service
        reverse_proxy imdb-service:8000 {
            header_up X-Script-Name /imdb-service
        }
    }
```

- [ ] **Step 4: Commit deployment config**

```bash
git add docker-compose.yml Caddyfile.example
git commit -m "feat(imdb-service): add docker-compose and Caddy routing config"
```

---

## Done

All tasks complete. The `imdb-service/` is fully implemented with:
- Dataset download, bulk import, and daily atomic refresh
- Pre-computed Bayesian-ranked charts for 8 chart types
- `GET /title/{id}`, `GET /person/{id}`, `GET /chart/{name}`, `GET /search` endpoints
- All `imdb_search` filters serveable from public IMDB datasets
- ≥85% test coverage
- Docker and Caddy deployment config

**Not in scope** (requires IMDB scraping): `imdb_list`, `imdb_watchlist`, `imdb_award`, popularity/box-office/company/keyword/content-rating/interests/event/topic filters.
