# AniDB Mirror Service

FastAPI-based caching service for AniDB anime metadata with rate limiting and background updates.

## Setup

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

2. Configure your environment variables in `.env`

3. Deploy with Docker Compose (from root directory):
   ```bash
   docker compose up -d anidb-mirror
   ```

## Access

- Service URL: `https://yourdomain.com/anidb-service`
- API Documentation: `https://yourdomain.com/anidb-service/docs`

## Development

Install dependencies:
```bash
pip install -r requirements.txt
```

Run tests:
```bash
pytest
```

Run locally:
```bash
uvicorn main:app --reload
```

## Features

- Caches AniDB anime metadata locally
- Rate limiting to respect AniDB API limits
- Background worker for async updates
- Tag-based search with mature content filtering
- Per-request mature content filtering

## API Endpoints

### GET /anime/{aid}
Fetch anime metadata by AniDB ID.

**Parameters:**
- `aid` (required): AniDB anime ID
- `mature` (optional, default: `false`): Include mature/18+ content

**Examples:**
```bash
# Get anime with adult content filtered out (default)
curl "http://localhost/anime/123"

# Get anime with adult content included
curl "http://localhost/anime/123?mature=true"
```

**Response Headers:**
- `X-Cache`: `HIT`, `STALE`, or not present (queued)
- `X-Mature-Filter`: `enabled` or `disabled`
- `X-Age-Days`: Cache age in days

### GET /search/tags
Search for anime by tags.

**Parameters:**
- `tags` (required): Comma-separated list of tags
- `min_weight` (optional, default: 200): Minimum tag weight
- `mature` (optional, default: `false`): Include mature/18+ anime in results

**Examples:**
```bash
# Search excluding adult anime (default)
curl "http://localhost/search/tags?tags=action,comedy"

# Search including adult anime in results
curl "http://localhost/search/tags?tags=action,comedy&mature=true"

# With minimum weight filter
curl "http://localhost/search/tags?tags=action&min_weight=300&mature=false"
```

**Response:**
```json
{
  "query": ["action", "comedy"],
  "min_weight": 200,
  "mature": false,
  "results": [
    {"aid": 123, "tag_matches": 2},
    {"aid": 456, "tag_matches": 2}
  ]
}
```

**Mature Filtering:**
When `mature=false`, anime with the following tags are excluded:
- "18 restricted"
- "hentai"
- "pornography"
- "adult"

### GET /stats
Get service statistics.

**Response:**
```json
{
  "status": "online",
  "cached_anime": 1500,
  "api_calls_last_24h": 45,
  "queue_size": 2,
  "daily_limit": 200
}
```

### GET /tags
List all known tags with usage statistics (HTML page).

## Mature Content Filtering

The service supports two levels of mature content control:

1. **API Access** (via AniDB credentials):
   - Set `ANIDB_USERNAME` and `ANIDB_PASSWORD` in `.env`
   - Required to fetch mature anime from AniDB
   - Without credentials, adult anime cannot be retrieved

2. **Client-Side Filtering** (per-request, opt-in):
   - `/anime/{aid}?mature=true` - Include adult content (filtered by default)
   - `/search/tags?mature=true` - Include adult anime (excluded by default)
   - Default behavior is family-friendly; users must explicitly request mature content
