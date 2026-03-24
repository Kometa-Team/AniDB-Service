"""IMDB Service - FastAPI caching service for IMDB public datasets."""

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import aiosqlite
import charts
from fastapi import FastAPI, HTTPException, Request
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
    global last_refresh
    from importer import download_datasets, run_full_import

    print("🔄 Starting daily refresh...")
    gz_paths = await download_datasets(DATA_DIR)
    await asyncio.to_thread(run_full_import, gz_paths, DB_PATH)

    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT value FROM import_meta WHERE key = 'last_refresh'")
            row = await cursor.fetchone()
            if row:
                last_refresh = row[0]
    except Exception as e:
        print(f"⚠️  Could not read last_refresh after import: {e}")

    await asyncio.to_thread(charts.rebuild_all_charts, DB_PATH, MIN_VOTES_CHART)
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


@app.get("/", response_class=HTMLResponse)
async def root(request: Request) -> HTMLResponse:
    """Return HTML landing page with links to available endpoints."""
    base = f"{request.url.scheme}://{request.headers.get('host', request.url.netloc)}"
    if ROOT_PATH:
        base += ROOT_PATH
    return HTMLResponse(
        content=f"""<!DOCTYPE html>
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
"""
    )


@app.get("/stats")
async def get_stats() -> Dict[str, Any]:
    """Return service health: status, last refresh time, and per-table row counts."""
    if not _db_is_ready():
        return {"status": "initializing"}

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
            "last_refresh": last_refresh,
            "table_counts": counts,
            "charts_cached": list(charts.chart_cache.keys()),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
