"""IMDB Service - FastAPI caching service for IMDB public datasets."""

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import aiosqlite
import charts
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

# --- Config ---
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
DB_PATH = DATA_DIR / "imdb.db"
ROOT_PATH = os.getenv("ROOT_PATH", "")
REFRESH_HOUR = int(os.getenv("REFRESH_HOUR", "3"))
MIN_VOTES_CHART = int(os.getenv("MIN_VOTES_CHART", "25000"))

# --- Global state ---
last_refresh: Optional[str] = None  # ISO 8601 UTC string
refresh_worker_task: Optional[asyncio.Task] = None
current_phase: str = "idle"  # idle | downloading | importing | building_charts
download_progress: Dict[str, str] = {}  # dataset stem → pending|downloading|done
import_progress: Dict[str, Any] = {}  # table → {status, rows}
last_activity: Optional[str] = None  # ISO timestamp of last phase change


def _set_phase(phase: str) -> None:
    """Update current_phase and last_activity timestamp atomically."""
    global current_phase, last_activity
    current_phase = phase
    last_activity = datetime.now(timezone.utc).isoformat()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown: load DB state, rebuild charts, start scheduler."""
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
            await asyncio.to_thread(charts.rebuild_all_charts, DB_PATH, MIN_VOTES_CHART)
        except Exception as e:
            print(f"⚠️  Chart rebuild failed: {e}")

        refresh_worker_task = asyncio.create_task(_refresh_scheduler())
        print("✅ IMDB Service ready")
        yield
    else:
        print("⚠️  No DB found — starting initial import in background")
        refresh_worker_task = asyncio.create_task(_initial_import_then_schedule())
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
    global last_refresh, download_progress, import_progress
    from importer import DATASET_FILES, STEM_TO_TABLE, download_datasets, run_full_import

    print("🔄 Starting daily refresh...")

    # --- Download phase ---
    _set_phase("downloading")
    download_progress = {stem: "pending" for stem in DATASET_FILES}
    import_progress = {}

    def _on_file_start(filename: str) -> None:
        for stem, fname in DATASET_FILES.items():
            if fname == filename:
                download_progress[stem] = "downloading"
                break

    def _on_file_done(filename: str) -> None:
        for stem, fname in DATASET_FILES.items():
            if fname == filename:
                download_progress[stem] = "done"
                break

    gz_paths = await download_datasets(DATA_DIR, _on_file_start, _on_file_done)

    # --- Import phase ---
    _set_phase("importing")
    import_progress = {
        STEM_TO_TABLE[stem]: {"status": "pending", "rows": 0}
        for stem in gz_paths
        if stem in STEM_TO_TABLE
    }

    def _on_table_start(table: str) -> None:
        import_progress[table] = {"status": "importing", "rows": 0}

    def _on_table_done(table: str, count: int) -> None:
        import_progress[table] = {"status": "done", "rows": count}

    await asyncio.to_thread(
        run_full_import, gz_paths, DB_PATH, None, _on_table_start, _on_table_done
    )

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT value FROM import_meta WHERE key = 'last_refresh'")
            row = await cursor.fetchone()
            if row:
                last_refresh = row[0]
    except Exception as e:
        print(f"⚠️  Could not read last_refresh after import: {e}")

    # --- Chart rebuild phase ---
    _set_phase("building_charts")
    await asyncio.to_thread(charts.rebuild_all_charts, DB_PATH, MIN_VOTES_CHART)

    _set_phase("idle")
    print("✅ Refresh complete")


async def _initial_import_then_schedule() -> None:
    """Run initial import immediately, then hand off to scheduler."""
    try:
        await _run_import_pipeline()
    except Exception as e:
        print(f"❌ Initial import failed: {e}")
    await _refresh_scheduler()


async def _refresh_scheduler() -> None:
    """Sleep until REFRESH_HOUR UTC daily, then run the import pipeline."""
    while True:
        now = datetime.now(timezone.utc)
        target = now.replace(hour=REFRESH_HOUR, minute=0, second=0, microsecond=0)
        if target <= now:
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


SORT_COLUMN_MAP: Dict[str, str] = {
    "rating": "tr.averageRating",
    "votes": "tr.numVotes",
    "year": "tb.startYear",
    "title": "tb.primaryTitle",
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
    type: Optional[str] = Query(None, alias="type"),  # noqa: B008
    type_not: Optional[str] = Query(None, alias="type.not"),  # noqa: B008
    genre: Optional[str] = Query(None, alias="genre"),  # noqa: B008
    genre_any: Optional[str] = Query(None, alias="genre.any"),  # noqa: B008
    genre_not: Optional[str] = Query(None, alias="genre.not"),  # noqa: B008
    rating_gte: Optional[float] = Query(None, alias="rating.gte"),  # noqa: B008
    rating_lte: Optional[float] = Query(None, alias="rating.lte"),  # noqa: B008
    votes_gte: Optional[int] = Query(None, alias="votes.gte"),  # noqa: B008
    votes_lte: Optional[int] = Query(None, alias="votes.lte"),  # noqa: B008
    runtime_gte: Optional[int] = Query(None, alias="runtime.gte"),  # noqa: B008
    runtime_lte: Optional[int] = Query(None, alias="runtime.lte"),  # noqa: B008
    release_after: Optional[str] = Query(None, alias="release.after"),  # noqa: B008
    release_before: Optional[str] = Query(None, alias="release.before"),  # noqa: B008
    title: Optional[str] = None,
    adult: bool = False,
    imdb_top: Optional[int] = None,
    imdb_bottom: Optional[int] = None,
    sort_by: str = "rating.desc",
    limit: int = Query(default=100, le=1000),  # noqa: B008
    language: Optional[str] = Query(None, alias="language"),  # noqa: B008
    language_any: Optional[str] = Query(None, alias="language.any"),  # noqa: B008
    language_not: Optional[str] = Query(None, alias="language.not"),  # noqa: B008
    language_primary: Optional[str] = Query(None, alias="language.primary"),  # noqa: B008
    country: Optional[str] = Query(None, alias="country"),  # noqa: B008
    country_any: Optional[str] = Query(None, alias="country.any"),  # noqa: B008
    country_not: Optional[str] = Query(None, alias="country.not"),  # noqa: B008
    country_origin: Optional[str] = Query(None, alias="country.origin"),  # noqa: B008
    cast: Optional[str] = Query(None, alias="cast"),  # noqa: B008
    cast_any: Optional[str] = Query(None, alias="cast.any"),  # noqa: B008
    cast_not: Optional[str] = Query(None, alias="cast.not"),  # noqa: B008
    series: Optional[str] = Query(None, alias="series"),  # noqa: B008
    series_not: Optional[str] = Query(None, alias="series.not"),  # noqa: B008
) -> Dict[str, Any]:
    """Return a filtered list of IMDb IDs matching the given criteria."""
    if imdb_top is not None and imdb_bottom is not None:
        raise HTTPException(
            status_code=400, detail="imdb_top and imdb_bottom are mutually exclusive"
        )

    if not _db_is_ready():
        raise HTTPException(status_code=503, detail="Service initializing")

    try:
        sort_col, sort_dir = _parse_sort(sort_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    conditions: list[str] = []
    params: list = []

    if not adult:
        conditions.append("tb.isAdult = 0")

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

    if genre:
        for g in genre.split(","):
            g = g.strip()
            conditions.append(
                "(tb.genres LIKE ? OR tb.genres LIKE ? OR tb.genres LIKE ? OR tb.genres = ?)"
            )
            params.extend([f"{g},%", f"%,{g},%", f"%,{g}", g])
    if genre_any:
        gs = [g.strip() for g in genre_any.split(",")]
        sub = " OR ".join(
            "(tb.genres LIKE ? OR tb.genres LIKE ? OR tb.genres LIKE ? OR tb.genres = ?)"
            for _ in gs
        )
        conditions.append(f"({sub})")
        for g in gs:
            params.extend([f"{g},%", f"%,{g},%", f"%,{g}", g])
    if genre_not:
        for g in genre_not.split(","):
            g = g.strip()
            conditions.append(
                "(tb.genres NOT LIKE ? AND tb.genres NOT LIKE ? AND tb.genres NOT LIKE ? AND tb.genres != ?)"
            )
            params.extend([f"{g},%", f"%,{g},%", f"%,{g}", g])

    if rating_gte is not None:
        conditions.append("tr.averageRating >= ?")
        params.append(rating_gte)
    if rating_lte is not None:
        conditions.append("tr.averageRating <= ?")
        params.append(rating_lte)
    if votes_gte is not None:
        conditions.append("tr.numVotes >= ?")
        params.append(votes_gte)
    if votes_lte is not None:
        conditions.append("tr.numVotes <= ?")
        params.append(votes_lte)
    if runtime_gte is not None:
        conditions.append("tb.runtimeMinutes >= ?")
        params.append(runtime_gte)
    if runtime_lte is not None:
        conditions.append("tb.runtimeMinutes <= ?")
        params.append(runtime_lte)

    def _year_from(s: str) -> int:
        if s.lower() == "today":
            return date.today().year
        try:
            return int(s[:4])
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid year value: {s!r}")

    if release_after:
        conditions.append("tb.startYear > ?")
        params.append(_year_from(release_after))
    if release_before:
        conditions.append("tb.startYear < ?")
        params.append(_year_from(release_before))

    if title:
        conditions.append("tb.primaryTitle LIKE ?")
        params.append(f"%{title}%")

    if imdb_top is not None:
        top_chart = charts.chart_cache.get("top_movies", [])
        allowed = [item["tconst"] for item in top_chart if item["rank"] <= imdb_top]
        if not allowed:
            return {"results": [], "total": 0}
        placeholders = ",".join("?" * len(allowed))
        conditions.append(f"tb.tconst IN ({placeholders})")  # nosec B608
        params.extend(allowed)
    elif imdb_bottom is not None:
        bottom_chart = charts.chart_cache.get("lowest_rated", [])
        allowed = [item["tconst"] for item in bottom_chart if item["rank"] <= imdb_bottom]
        if not allowed:
            return {"results": [], "total": 0}
        placeholders = ",".join("?" * len(allowed))
        conditions.append(f"tb.tconst IN ({placeholders})")  # nosec B608
        params.extend(allowed)

    _add_join_filters(
        conditions,
        params,
        language,
        language_any,
        language_not,
        language_primary,
        country,
        country_any,
        country_not,
        country_origin,
        cast,
        cast_any,
        cast_not,
        series,
        series_not,
    )

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    sql = (
        f"SELECT DISTINCT tb.tconst "  # nosec B608 — sort_col/sort_dir validated against SORT_COLUMN_MAP
        f"FROM title_basics tb "
        f"LEFT JOIN title_ratings tr ON tb.tconst = tr.tconst "
        f"{where_clause} "
        f"ORDER BY {sort_col} {sort_dir} "
        f"LIMIT ?"
    )

    params.append(limit)

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {e}")

    results = [row[0] for row in rows]

    return {"results": results, "total": len(results)}


def _add_join_filters(
    conditions: list[str],
    params: list[Any],
    language: Optional[str],
    language_any: Optional[str],
    language_not: Optional[str],
    language_primary: Optional[str],
    country: Optional[str],
    country_any: Optional[str],
    country_not: Optional[str],
    country_origin: Optional[str],
    cast: Optional[str],
    cast_any: Optional[str],
    cast_not: Optional[str],
    series: Optional[str],
    series_not: Optional[str],
) -> None:
    """Append WHERE conditions for join-based filters using EXISTS subqueries."""

    def _exists_aka(col: str, negate: bool = False) -> str:
        op = "NOT EXISTS" if negate else "EXISTS"
        return f"{op} (SELECT 1 FROM title_akas ta WHERE ta.tconst = tb.tconst AND ta.{col} = ?)"  # nosec B608

    def _exists_aka_original(col: str) -> str:
        return f"EXISTS (SELECT 1 FROM title_akas ta WHERE ta.tconst = tb.tconst AND ta.{col} = ? AND ta.isOriginalTitle = 1)"  # nosec B608

    if language:
        for lang in language.split(","):
            conditions.append(_exists_aka("language"))
            params.append(lang.strip())
    if language_any:
        langs = [lang.strip() for lang in language_any.split(",")]
        sub = " OR ".join(_exists_aka("language") for _ in langs)
        conditions.append(f"({sub})")
        params.extend(langs)
    if language_not:
        for lang in language_not.split(","):
            conditions.append(_exists_aka("language", negate=True))
            params.append(lang.strip())
    if language_primary:
        for lang in language_primary.split(","):
            conditions.append(_exists_aka_original("language"))
            params.append(lang.strip())

    if country:
        for c in country.split(","):
            conditions.append(_exists_aka("region"))
            params.append(c.strip())
    if country_any:
        cs = [c.strip() for c in country_any.split(",")]
        sub = " OR ".join(_exists_aka("region") for _ in cs)
        conditions.append(f"({sub})")
        params.extend(cs)
    if country_not:
        for c in country_not.split(","):
            conditions.append(_exists_aka("region", negate=True))
            params.append(c.strip())
    if country_origin:
        for c in country_origin.split(","):
            conditions.append(_exists_aka_original("region"))
            params.append(c.strip())

    def _exists_cast(negate: bool = False) -> str:
        op = "NOT EXISTS" if negate else "EXISTS"
        return f"{op} (SELECT 1 FROM title_principals tp WHERE tp.tconst = tb.tconst AND tp.nconst = ?)"  # nosec B608

    if cast:
        for nm in cast.split(","):
            conditions.append(_exists_cast())
            params.append(nm.strip())
    if cast_any:
        nms = [nm.strip() for nm in cast_any.split(",")]
        sub = " OR ".join(_exists_cast() for _ in nms)
        conditions.append(f"({sub})")
        params.extend(nms)
    if cast_not:
        for nm in cast_not.split(","):
            conditions.append(_exists_cast(negate=True))
            params.append(nm.strip())

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


@app.get("/", response_class=HTMLResponse)
async def root(request: Request) -> HTMLResponse:
    """Return HTML landing page with links to available endpoints."""
    base = f"{request.url.scheme}://{request.headers.get('host', request.url.netloc)}"
    if ROOT_PATH:
        base += ROOT_PATH
    return HTMLResponse(
        content=f"""<!DOCTYPE html>
<html>
<head>
    <title>IMDB Service</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
            line-height: 1.6;
            color: #333;
        }}
        h1 {{ color: #2c3e50; }}
        code {{
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }}
        .endpoint {{
            background: #f8f9fa;
            padding: 15px;
            margin: 10px 0;
            border-left: 4px solid #007bff;
            border-radius: 4px;
        }}
        a {{ color: #007bff; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <h1>🎬 IMDB Service</h1>
    <p>A caching service for IMDB public dataset metadata with daily updates and pre-computed charts.</p>

    <h2>API Endpoints</h2>

    <div class="endpoint">
        <strong>GET /stats</strong> - Service status and table row counts<br>
        <code>curl {base}/stats</code>
    </div>

    <div class="endpoint">
        <strong>GET /title/{{imdb_id}}</strong> - Full title record by IMDb ID<br>
        <code>curl {base}/title/tt0111161</code>
    </div>

    <div class="endpoint">
        <strong>GET /person/{{imdb_id}}</strong> - Person record by IMDb person ID<br>
        <code>curl {base}/person/nm0000199</code>
    </div>

    <div class="endpoint">
        <strong>GET /chart/{{chart_name}}</strong> - Pre-computed ranked chart<br>
        <code>curl "{base}/chart/top_movies?limit=10"</code><br>
        Available charts: top_movies, top_shows, lowest_rated, top_english, top_indian, top_tamil, top_telugu, top_malayalam
    </div>

    <div class="endpoint">
        <strong>GET /search</strong> - Filtered title search returning IMDb IDs<br>
        <code>curl "{base}/search?type=movie&amp;rating.gte=8&amp;limit=10"</code>
    </div>

    <h2>API Documentation</h2>

    <div class="endpoint">
        <strong><a href="{base}/docs">Swagger UI</a></strong> - Interactive API documentation<br>
        Try out endpoints directly from your browser
    </div>

    <div class="endpoint">
        <strong><a href="{base}/redoc">ReDoc</a></strong> - Alternative API documentation<br>
        Clean, readable documentation format
    </div>

    <div class="endpoint">
        <strong><a href="{base}/openapi.json">OpenAPI Schema</a></strong> - Machine-readable API specification<br>
        JSON schema for automated tools and clients
    </div>
</body>
</html>
"""
    )


@app.get("/stats")
async def get_stats() -> Dict[str, Any]:
    """Return service health: status, phase, progress indicators, and per-table row counts."""
    if not _db_is_ready():
        return {
            "status": "initializing",
            "phase": current_phase,
            "download_progress": download_progress,
            "import_progress": import_progress,
            "last_activity": last_activity,
        }

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            counts: Dict[str, int] = {}
            for table in (
                "title_basics",
                "title_ratings",
                "title_akas",
                "title_crew",
                "title_episode",
                "title_principals",
                "name_basics",
            ):
                cursor = await db.execute(f"SELECT COUNT(*) FROM {table}")  # nosec B608
                row = await cursor.fetchone()
                counts[table] = row[0] if row else 0

        return {
            "status": "online",
            "phase": current_phase,
            "last_refresh": last_refresh,
            "last_activity": last_activity,
            "table_counts": counts,
            "charts_cached": list(charts.chart_cache.keys()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/title/{imdb_id}")
async def get_title(imdb_id: str) -> Dict[str, Any]:
    """Return full title record by IMDb ID (e.g. tt0111161)."""
    if not _db_is_ready():
        raise HTTPException(status_code=503, detail="Service initializing")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

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

        cursor = await db.execute(
            "SELECT directors, writers FROM title_crew WHERE tconst = ?", (imdb_id,)
        )
        crew = await cursor.fetchone()
        result["directors"] = crew["directors"] if crew else None
        result["writers"] = crew["writers"] if crew else None

        cursor = await db.execute(
            """
            SELECT nconst, ordering, category, job, characters
            FROM title_principals WHERE tconst = ? ORDER BY ordering
            """,
            (imdb_id,),
        )
        principals = await cursor.fetchall()
        result["principals"] = [dict(p) for p in principals]

        if result.get("titleType") in ("tvSeries", "tvMiniSeries"):
            cursor = await db.execute(
                "SELECT COUNT(*) FROM title_episode WHERE parentTconst = ?", (imdb_id,)
            )
            ep_row = await cursor.fetchone()
            result["episode_count"] = ep_row[0] if ep_row else 0

    return result


@app.get("/chart/{chart_name}")
async def get_chart(chart_name: str, limit: Optional[int] = None) -> Dict[str, Any]:
    """Return a pre-computed ranked chart of IMDb titles."""
    if chart_name not in charts.CHART_CONFIGS:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown chart: {chart_name!r}. Valid: {list(charts.CHART_CONFIGS.keys())}",
        )

    if not _db_is_ready() and not charts.chart_cache:
        raise HTTPException(status_code=503, detail="Service initializing")

    if limit is not None and (limit < 1 or limit > charts.MAX_CHART_SIZE):
        raise HTTPException(status_code=400, detail=f"limit must be ≤ {charts.MAX_CHART_SIZE}")

    results = charts.chart_cache.get(chart_name, [])
    if limit is not None:
        results = results[:limit]
    else:
        results = results[: charts.DEFAULT_CHART_SIZE]

    return {"chart": chart_name, "total": len(results), "results": results}


@app.get("/person/{imdb_id}")
async def get_person(imdb_id: str) -> Dict[str, Any]:
    """Return person record by IMDb person ID (e.g. nm0000093)."""
    if not _db_is_ready():
        raise HTTPException(status_code=503, detail="Service initializing")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM name_basics WHERE nconst = ?", (imdb_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Person {imdb_id!r} not found")
        return dict(row)
