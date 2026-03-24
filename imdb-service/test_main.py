"""Tests for IMDB service."""

import gzip
import io
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

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


@pytest.mark.asyncio
async def test_download_datasets_creates_files(tmp_path):
    """download_datasets saves each dataset file to the target directory."""
    fake_gz_content = b"\x1f\x8b\x08\x00\x00\x00\x00\x00"  # gzip magic bytes

    # Build a mock httpx.AsyncClient that streams fake content
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()

    async def fake_aiter_bytes(chunk_size=65536):
        yield fake_gz_content

    mock_resp.aiter_bytes = fake_aiter_bytes

    mock_stream_ctx = AsyncMock()
    mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_client = AsyncMock()
    mock_client.stream = MagicMock(return_value=mock_stream_ctx)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("importer.httpx.AsyncClient", return_value=mock_client):
        from importer import download_datasets

        result = await download_datasets(tmp_path)

    assert len(result) == 7
    expected_stems = {
        "title.basics",
        "title.ratings",
        "title.akas",
        "title.crew",
        "title.episode",
        "title.principals",
        "name.basics",
    }
    assert set(result.keys()) == expected_stems
    for _stem, path in result.items():
        assert path.exists()
        assert path.name.endswith(".tsv.gz")


def _make_all_gz_files(tmp_path):
    """Create minimal valid TSV.gz files for all 7 datasets."""
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
    crew_data = _make_tsv_gz(
        "tconst\tdirectors\twriters",
        [f"tt{i:07d}\tnm{i:07d}\t\\N" for i in range(1, 6)],
    )
    episode_data = _make_tsv_gz(
        "tconst\tparentTconst\tseasonNumber\tepisodeNumber",
        [],
    )
    principals_data = _make_tsv_gz(
        "tconst\tordering\tnconst\tcategory\tjob\tcharacters",
        [f"tt{i:07d}\t1\tnm{i:07d}\tactor\t\\N\t\\N" for i in range(1, 6)],
    )
    names_data = _make_tsv_gz(
        "nconst\tprimaryName\tbirthYear\tdeathYear\tprimaryProfession\tknownForTitles",
        [f"nm{i:07d}\tPerson {i}\t1970\t\\N\tactor\ttt{i:07d}" for i in range(1, 6)],
    )

    gz_dir = tmp_path / "gz"
    gz_dir.mkdir()
    files = {
        "title.basics": basics_data,
        "title.ratings": ratings_data,
        "title.akas": akas_data,
        "title.crew": crew_data,
        "title.episode": episode_data,
        "title.principals": principals_data,
        "name.basics": names_data,
    }
    gz_paths = {}
    for stem, data in files.items():
        path = gz_dir / f"{stem}.tsv.gz"
        path.write_bytes(data)
        gz_paths[stem] = path
    return gz_paths


def test_run_full_import_produces_populated_db(tmp_path):
    gz_paths = _make_all_gz_files(tmp_path)
    live_db = tmp_path / "imdb.db"

    from importer import run_full_import

    run_full_import(gz_paths, live_db, min_rows_override=0)

    assert live_db.exists()
    conn = sqlite3.connect(live_db)
    count = conn.execute("SELECT COUNT(*) FROM title_basics").fetchone()[0]
    assert count == 5
    # Verify import_meta has last_refresh
    row = conn.execute("SELECT value FROM import_meta WHERE key='last_refresh'").fetchone()
    assert row is not None
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

    # Provide an invalid (not-gzip) file to trigger failure
    gz_dir = tmp_path / "gz"
    gz_dir.mkdir()
    bad_gz = gz_dir / "title.basics.tsv.gz"
    bad_gz.write_bytes(b"not valid gzip content")
    gz_paths = {"title.basics": bad_gz}

    from importer import run_full_import

    with pytest.raises(Exception, match="."):  # noqa: B017
        run_full_import(gz_paths, live_db, min_rows_override=0)

    # Live DB must still be the original
    conn = sqlite3.connect(live_db)
    val = conn.execute("SELECT val FROM sentinel").fetchone()[0]
    assert val == "original"
    conn.close()


def _seed_db_for_charts(db_path):
    """Seed a test DB with data for chart tests."""
    conn = sqlite3.connect(db_path)
    from importer import create_schema

    create_schema(conn)
    movies = [
        ("tt0000001", "movie", "Alpha", "Alpha", 0, 2000, None, 120, "Action"),
        ("tt0000002", "movie", "Beta", "Beta", 0, 2001, None, 90, "Drama"),
        ("tt0000003", "movie", "Gamma", "Gamma", 0, 2002, None, 100, "Comedy"),
        ("tt0000004", "tvSeries", "Delta", "Delta", 0, 2003, 2005, None, "Drama"),
        ("tt0000005", "tvSeries", "Epsilon", "Epsilon", 0, 2004, None, None, "Action"),
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
    # English akas for tt0000001 and tt0000002 only
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
    assert len(charts.chart_cache["top_movies"]) <= 3  # 3 movies with votes >= 25000
    assert len(charts.chart_cache["top_shows"]) <= 2  # 2 tvSeries with votes >= 25000


def test_top_movies_chart_sorted_by_weighted_rating(tmp_path):
    db_path = tmp_path / "imdb.db"
    _seed_db_for_charts(db_path)
    import charts

    charts.rebuild_all_charts(db_path, min_votes=25000)
    top = charts.chart_cache["top_movies"]
    ratings = [item["averageRating"] for item in top]
    assert ratings == sorted(ratings, reverse=True)


def test_lowest_rated_chart_is_ascending(tmp_path):
    db_path = tmp_path / "imdb.db"
    _seed_db_for_charts(db_path)
    import charts

    charts.rebuild_all_charts(db_path, min_votes=25000)
    bottom = charts.chart_cache["lowest_rated"]
    ratings = [item["averageRating"] for item in bottom]
    assert ratings == sorted(ratings)


def test_top_english_only_includes_english_titles(tmp_path):
    db_path = tmp_path / "imdb.db"
    _seed_db_for_charts(db_path)
    import charts

    charts.rebuild_all_charts(db_path, min_votes=25000)
    english = charts.chart_cache["top_english"]
    tconsts = {item["tconst"] for item in english}
    assert "tt0000001" in tconsts
    assert "tt0000002" in tconsts
    assert "tt0000003" not in tconsts  # no en aka


def test_chart_items_have_required_fields(tmp_path):
    db_path = tmp_path / "imdb.db"
    _seed_db_for_charts(db_path)
    import charts

    charts.rebuild_all_charts(db_path, min_votes=25000)
    item = charts.chart_cache["top_movies"][0]
    for field in ("tconst", "primaryTitle", "startYear", "averageRating", "numVotes", "rank"):
        assert field in item, f"Missing field: {field}"


def test_chart_cache_replaced_atomically(tmp_path):
    db_path = tmp_path / "imdb.db"
    _seed_db_for_charts(db_path)
    import charts

    charts.chart_cache = {"stale_key": [{"tconst": "ttOLD"}]}
    charts.rebuild_all_charts(db_path, min_votes=25000)
    assert "stale_key" not in charts.chart_cache
    assert "top_movies" in charts.chart_cache
