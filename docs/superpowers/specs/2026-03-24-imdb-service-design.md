# IMDB Service — Design Spec

**Date:** 2026-03-24
**Branch:** `feat/imdb-service` (to be created)
**Status:** Approved

---

## Overview

A new standalone FastAPI microservice (`imdb-service/`) that downloads and serves the full IMDB public datasets from https://datasets.imdbws.com/. It provides:

- Title and person lookup by IMDB ID
- Pre-computed ranked charts (Top 250 Movies, Top 250 TV, etc.)
- Ad-hoc filtered search mirroring Kometa's `imdb_search` builder parameters

The goal is to replace Kometa's direct IMDB scraping for the builders that can be served from the free public datasets.

---

## What Can (and Cannot) Be Served

### Supported
- `imdb_id` — full title/person lookup
- `imdb_chart` — `top_movies`, `top_shows`, `lowest_rated`, `top_english`, `top_indian`, `top_tamil`, `top_telugu`, `top_malayalam`
- `imdb_search` — type, genre, rating, votes, runtime, year/release, title text, language, country, cast, series, adult, imdb_top/imdb_bottom, sort by rating/votes/year/title

### Not Supported (requires scraping or auth — not in free datasets)
- `imdb_list`, `imdb_watchlist`, `imdb_award`
- `imdb_chart`: `popular_movies`, `popular_shows`, `box_office`, `trending_india`, `trending_tamil`, `trending_telugu`
- `imdb_search` params: `popularity`, `box_office`, `company`, `keyword`, `content_rating`, `interests`, `event`, `topic`, `character`, `list`
- `sort_by`: `popularity.asc/desc`, `box_office.asc/desc`
- Offset/cursor pagination on `/search` (not needed by Kometa builders)

---

## Directory Structure

```
imdb-service/
├── main.py              # FastAPI app, all endpoints
├── importer.py          # Dataset download + SQLite import logic (uses stdlib sqlite3 for bulk speed)
├── charts.py            # Pre-computed chart definitions and in-memory cache
├── Dockerfile
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
└── test_main.py
```

---

## Database Schema

Seven tables, one per IMDB dataset. Built into SQLite at `$DATA_DIR/imdb.db`. During daily refresh, a shadow DB is built at `$TMP_DIR/imdb_shadow.db` then atomically swapped.

`title_akas` has no primary key in the source data; the logical unique key is `(tconst, ordering)`.

```sql
-- title.basics.tsv.gz
CREATE TABLE title_basics (
    tconst TEXT PRIMARY KEY,
    titleType TEXT,
    primaryTitle TEXT,
    originalTitle TEXT,
    isAdult INTEGER,
    startYear INTEGER,
    endYear INTEGER,
    runtimeMinutes INTEGER,
    genres TEXT                 -- comma-separated: "Action,Comedy"
);
CREATE INDEX idx_tb_type ON title_basics(titleType);
CREATE INDEX idx_tb_year ON title_basics(startYear);
CREATE INDEX idx_tb_genres ON title_basics(genres);

-- title.ratings.tsv.gz
CREATE TABLE title_ratings (
    tconst TEXT PRIMARY KEY,
    averageRating REAL,
    numVotes INTEGER
);

-- title.akas.tsv.gz  (logical unique key: tconst + ordering)
CREATE TABLE title_akas (
    tconst TEXT NOT NULL,
    ordering INTEGER,
    title TEXT,
    region TEXT,
    language TEXT,
    types TEXT,
    attributes TEXT,
    isOriginalTitle INTEGER
);
CREATE INDEX idx_aka_tconst ON title_akas(tconst);
CREATE INDEX idx_aka_region ON title_akas(region);
CREATE INDEX idx_aka_language ON title_akas(language);

-- title.crew.tsv.gz
CREATE TABLE title_crew (
    tconst TEXT PRIMARY KEY,
    directors TEXT,             -- comma-separated nm IDs
    writers TEXT
);

-- title.episode.tsv.gz
CREATE TABLE title_episode (
    tconst TEXT PRIMARY KEY,
    parentTconst TEXT,
    seasonNumber INTEGER,
    episodeNumber INTEGER
);
CREATE INDEX idx_ep_parent ON title_episode(parentTconst);

-- title.principals.tsv.gz
CREATE TABLE title_principals (
    tconst TEXT NOT NULL,
    ordering INTEGER,
    nconst TEXT NOT NULL,
    category TEXT,
    job TEXT,
    characters TEXT
);
CREATE INDEX idx_pr_tconst ON title_principals(tconst);
CREATE INDEX idx_pr_nconst ON title_principals(nconst);

-- name.basics.tsv.gz
CREATE TABLE name_basics (
    nconst TEXT PRIMARY KEY,
    primaryName TEXT,
    birthYear INTEGER,
    deathYear INTEGER,
    primaryProfession TEXT,
    knownForTitles TEXT         -- comma-separated tt IDs
);
CREATE INDEX idx_nb_name ON name_basics(primaryName);
```

IMDB's `\N` null sentinel values are converted to SQL `NULL` during import.

---

## API Endpoints

### `GET /`
HTML landing page listing all endpoints. Consistent with existing services.

### `GET /stats`
Health check. Returns DB record counts per table, `last_refresh` as ISO 8601 UTC string (e.g. `"2026-03-24T03:00:00Z"`), chart cache status, and `"status": "online" | "initializing"`.

### `GET /title/{imdb_id}`
Full title record: joins title_basics + title_ratings + title_crew + episode count (if series) + top principals ordered by `ordering`. Returns JSON.

### `GET /person/{imdb_id}`
Full person record from name_basics. Returns JSON.

### `GET /chart/{chart_name}`
Returns a pre-computed list of IMDb IDs with basic metadata. Computed on startup and after each daily refresh. Optional `?limit=N` (default and max per chart below).

Chart rankings use the Bayesian weighted rating formula: `WR = (v / (v + m)) × R + (m / (v + m)) × C` where `v` = numVotes for the title, `m` = MIN_VOTES_CHART, `R` = title's averageRating, and `C` = mean averageRating across all qualifying titles. This matches IMDB's published methodology.

| chart_name | Logic | Default size | Max via `?limit` |
|---|---|---|---|
| `top_movies` | Top movies by weighted rating (numVotes ≥ MIN_VOTES_CHART) | 250 | 500 |
| `top_shows` | Top TV series by weighted rating (numVotes ≥ MIN_VOTES_CHART) | 250 | 500 |
| `lowest_rated` | Lowest rated movies by weighted rating (numVotes ≥ MIN_VOTES_CHART) | 250 | 500 |
| `top_english` | Top movies with language=en in title_akas, by weighted rating | 250 | 500 |
| `top_indian` | Top movies with region=IN in title_akas, by weighted rating | 250 | 500 |
| `top_tamil` | Top movies with language=ta in title_akas, by weighted rating | 250 | 500 |
| `top_telugu` | Top movies with language=te in title_akas, by weighted rating | 250 | 500 |
| `top_malayalam` | Top movies with language=ml in title_akas, by weighted rating | 250 | 500 |

### `GET /search`
Ad-hoc filtered query. Returns `{"results": ["tt...", ...], "total": N}` (IMDb IDs only). No offset/pagination.

| Query param | Source column | Notes |
|---|---|---|
| `type` / `type.not` | title_basics.titleType | comma-separated |
| `genre` / `genre.any` / `genre.not` | title_basics.genres | LIKE match |
| `rating.gte` / `rating.lte` | title_ratings.averageRating | |
| `votes.gte` / `votes.lte` | title_ratings.numVotes | |
| `runtime.gte` / `runtime.lte` | title_basics.runtimeMinutes | minutes |
| `release.after` / `release.before` | title_basics.startYear | YYYY or `today` |
| `title` | title_basics.primaryTitle | LIKE |
| `language` / `language.any` / `language.not` / `language.primary` | title_akas.language | |
| `country` / `country.any` / `country.not` / `country.origin` | title_akas.region | |
| `cast` / `cast.any` / `cast.not` | title_principals.nconst | nm IDs |
| `series` / `series.not` | title_episode.parentTconst | tt IDs |
| `adult` | title_basics.isAdult | boolean |
| `imdb_top` | rank ≤ N in pre-computed top_movies chart | integer; mutually exclusive with `imdb_bottom` |
| `imdb_bottom` | rank ≤ N in pre-computed lowest_rated chart | integer; mutually exclusive with `imdb_top` |
| `sort_by` | rating/votes/year/title + .asc/.desc | default: `rating.desc` |
| `limit` | — | default 100, max 1000 |

`imdb_top=250` means "return only titles whose rank in the top_movies chart is ≤ 250" (i.e., they appear in the top 250). `imdb_bottom=100` means the same for the lowest_rated chart. The two params are mutually exclusive; passing both returns a 400 error.

---

## Daily Refresh Pipeline

1. **Download** — fetch all 7 `.tsv.gz` files from `https://datasets.imdbws.com/` concurrently with `httpx` streaming. Saved to `$TMP_DIR`.
2. **Import into shadow DB** — parse each `.tsv.gz` using the stdlib `sqlite3` module (not `aiosqlite`) for bulk-insert performance, in batches of 10,000 rows. Each file is imported inside its own transaction; a corrupt or truncated file raises an exception that aborts that file's transaction and rolls back all rows for that table. `\N` → `NULL`. A minimum row-count threshold per file is validated before committing (e.g. title_basics must have ≥ 1,000,000 rows). Progress logged per-file.
3. **Build indexes** — run all `CREATE INDEX` statements on the shadow DB after all tables are fully populated.
4. **Atomic swap** — `os.replace(shadow_db_path, live_db_path)`. `DATA_DIR` and `TMP_DIR` **must resolve to the same filesystem** (both are subdirectories of the same Docker volume mount by default). If they are on different filesystems, `os.replace()` raises `OSError: [Errno 18] Invalid cross-device link`; the importer catches this, logs a clear error, and leaves the live DB untouched. The docker-compose config avoids this by default: both `imdb-data` and `imdb-tmp` volumes are mounted under `/app/` on the same container filesystem.
5. **Rebuild chart cache** — build all pre-computed charts into a new local dict, then replace the module-level `chart_cache` dict in a single atomic assignment (`chart_cache = new_dict`) to prevent partial reads during rebuild.
6. **Cleanup** — delete downloaded `.tsv.gz` files and temp files.

**Failure handling:** any step failure deletes the shadow DB and leaves the live DB untouched. Service continues serving stale data. Full traceback logged.

**Schedule:** daily at `REFRESH_HOUR` UTC (default: 3), implemented as an `asyncio.sleep` loop matching the anidb-service worker pattern.

**First-run:** if no live DB exists, all data endpoints return `503` with `"status": "initializing"` until the initial import completes. `/stats` always responds.

**Disk:** peak usage is ~2× DB size (live + shadow). Recommend 20 GB volume.

---

## Python Dependencies

**`requirements.txt`** (runtime):
```
fastapi
uvicorn[standard]
httpx
aiosqlite        # used for async read queries in endpoints
```

**`requirements-dev.txt`** (testing):
```
pytest
pytest-asyncio
httpx            # for TestClient
```

`importer.py` uses the stdlib `sqlite3` module (not `aiosqlite`) for bulk import — it runs in a background thread via `asyncio.to_thread()` and stdlib `sqlite3` is significantly faster for batch inserts than the async wrapper.

---

## Docker & Deployment

### Dockerfile
Python 3.12 slim, non-root user, `CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]`.

### docker-compose.yml additions

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

volumes:
  imdb-data:
```

Note: both `DATA_DIR` and `TMP_DIR` must resolve to the same filesystem for `os.replace()` to work atomically. The simplest approach is to use **a single volume** (`imdb-data`) and place the shadow DB inside it as `$DATA_DIR/imdb_shadow.db` (i.e. `TMP_DIR` defaults to `DATA_DIR`). The importer catches `OSError: [Errno 18] Invalid cross-device link` and logs a clear error if misconfigured.

### Caddyfile
Add a new route block routing `/imdb-service/*` → `reverse_proxy imdb-service:8000`.

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ROOT_PATH` | `""` | Path prefix for reverse proxy |
| `DATA_DIR` | `/app/data` | Directory for live SQLite DB |
| `TMP_DIR` | `/app/data` | Directory for shadow DB during refresh (must be same filesystem as DATA_DIR) |
| `REFRESH_HOUR` | `3` | UTC hour for daily refresh (0–23) |
| `MIN_VOTES_CHART` | `25000` | Min vote threshold for chart ranking |

---

## Out of Scope

- `imdb_list`, `imdb_watchlist`, `imdb_award` (require IMDB scraping)
- Popularity, box office, company, keyword, content rating, interest, award event, topic filters (not in public datasets)
- Full-text search on plot/trivia/quotes (not in datasets)
- Authentication / per-user data
- Offset/cursor pagination on `/search`
