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

---

## Directory Structure

```
imdb-service/
├── main.py              # FastAPI app, all endpoints
├── importer.py          # Dataset download + SQLite import logic
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

-- title.akas.tsv.gz
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

### `GET /stats`
Health check. Returns DB record counts per table, last refresh timestamp, chart cache status, and `"status": "online" | "initializing"`.

### `GET /title/{imdb_id}`
Full title record: joins title_basics + title_ratings + title_crew + episode count (if series) + top principals ordered by `ordering`. Returns JSON.

### `GET /person/{imdb_id}`
Full person record from name_basics. Returns JSON.

### `GET /chart/{chart_name}`
Returns a pre-computed list of IMDb IDs with basic metadata. Computed on startup and after each daily refresh. Optional `?limit=N` (max 500).

| chart_name | Logic |
|---|---|
| `top_movies` | Top 250 movies by weighted rating (numVotes ≥ MIN_VOTES_CHART) |
| `top_shows` | Top 250 TV series by weighted rating |
| `lowest_rated` | Bottom 100 movies with ≥ MIN_VOTES_CHART votes |
| `top_english` | Top 250 movies with language=en in title_akas |
| `top_indian` | Top rated movies with region=IN |
| `top_tamil` | Top rated movies with language=ta |
| `top_telugu` | Top rated movies with language=te |
| `top_malayalam` | Top rated movies with language=ml |

### `GET /search`
Ad-hoc filtered query. Returns `{"results": ["tt...", ...], "total": N}` (IMDb IDs only).

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
| `imdb_top` | rank in top_movies chart | integer |
| `imdb_bottom` | rank in lowest_rated chart | integer |
| `sort_by` | rating/votes/year/title + .asc/.desc | default: `rating.desc` |
| `limit` | — | default 100, max 1000 |

---

## Daily Refresh Pipeline

1. **Download** — fetch all 7 `.tsv.gz` files from `https://datasets.imdbws.com/` concurrently with `httpx` streaming. Saved to `$TMP_DIR`.
2. **Import into shadow DB** — parse each file, insert in batches of 10,000 rows. `\N` → `NULL`. Progress logged per-file.
3. **Build indexes** — run all `CREATE INDEX` statements on the shadow DB after bulk insert.
4. **Atomic swap** — `os.replace(shadow_db_path, live_db_path)`. In-flight queries finish against old file handle.
5. **Rebuild chart cache** — recompute all pre-computed charts into the in-memory dict from the new live DB.
6. **Cleanup** — delete downloaded `.tsv.gz` files and temp files.

**Failure handling:** any step failure deletes the shadow DB and leaves the live DB untouched. Service continues serving stale data. Full traceback logged.

**Schedule:** daily at `REFRESH_HOUR` UTC (default: 3), implemented as an `asyncio.sleep` loop matching the anidb-service worker pattern.

**First-run:** if no live DB exists, all data endpoints return `503` with `"status": "initializing"` until the initial import completes. `/stats` always responds.

**Disk:** peak usage is ~2× DB size (live + shadow). Recommend 20 GB volume.

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
    - TMP_DIR=/app/tmp
    - MIN_VOTES_CHART=25000
  volumes:
    - imdb-data:/app/data
    - imdb-tmp:/app/tmp
  deploy:
    resources:
      limits:
        memory: 1G
      reservations:
        memory: 512M

volumes:
  imdb-data:
  imdb-tmp:
```

### Caddyfile
Add a new route block routing `/imdb-service/*` → `reverse_proxy imdb-service:8000`.

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ROOT_PATH` | `""` | Path prefix for reverse proxy |
| `DATA_DIR` | `/app/data` | Directory for live SQLite DB |
| `TMP_DIR` | `/app/tmp` | Directory for shadow DB during refresh |
| `REFRESH_HOUR` | `3` | UTC hour for daily refresh (0–23) |
| `MIN_VOTES_CHART` | `25000` | Min vote threshold for chart ranking |

---

## Out of Scope

- `imdb_list`, `imdb_watchlist`, `imdb_award` (require IMDB scraping)
- Popularity, box office, company, keyword, content rating, interest, award event, topic filters (not in public datasets)
- Full-text search on plot/trivia/quotes (not in datasets)
- Authentication / per-user data
