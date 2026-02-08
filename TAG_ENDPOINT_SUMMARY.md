# New Tag ID Endpoint - Implementation Summary

## Overview
Added a new endpoint `/tags/{tag_id}` to the AniDB service that retrieves anime by tag ID with a configurable limit.

## Changes Made

### 1. Database Schema Updates
**Files Modified**:
- [anidb-service/main.py](anidb-service/main.py)
- [anidb-service/seed_db.py](anidb-service/seed_db.py)

**Changes**:
- Added `tag_id INTEGER` column to the `tags` table
- Added index `idx_tags_tag_id` on the `tag_id` column for faster queries
- Updated table structure from `(aid, name, weight)` to `(aid, tag_id, name, weight)`

### 2. XML Parsing Updates
**Files Modified**:
- [anidb-service/main.py](anidb-service/main.py#L81-L87)
- [anidb-service/seed_db.py](anidb-service/seed_db.py#L26-L32)

**Changes**:
- Modified tag extraction to parse the `id` attribute from XML `<tag>` elements
- Updated INSERT statements to include tag_id value

### 3. New API Endpoint
**File Modified**: [anidb-service/main.py](anidb-service/main.py#L715-L783)

**Endpoint**: `GET /tags/{tag_id}`

**Parameters**:
- `tag_id` (path, required): The AniDB tag ID (must be positive integer)
- `limit` (query, optional): Maximum number of results (default: 100, max: 1000)
- `mature` (query, optional): Include mature/18+ content (default: false)

**Response**:
```json
{
  "tag_id": 36,
  "tag_name": "military",
  "limit": 10,
  "mature": false,
  "count": 4,
  "results": [
    {"aid": 12757, "weight": 300},
    {"aid": 10430, "weight": 300},
    {"aid": 4233, "weight": 200},
    {"aid": 1808, "weight": 200}
  ]
}
```

**Features**:
- Returns anime sorted by tag weight (descending)
- Optionally filters out mature content (default behavior)
- Returns tag name along with results
- Validates tag_id and limit parameters

### 4. Documentation Updates
**File Modified**: [anidb-service/main.py](anidb-service/main.py#L396-L400)

Added the new endpoint to the HTML documentation on the root page (`/`):
```
GET /tags/{tag_id} - Get anime by tag ID
curl "http://localhost:8000/tags/36?limit=10"
```

### 5. Test Updates
**File Modified**: [anidb-service/test_main.py](anidb-service/test_main.py)

Updated test fixtures to include `tag_id` column (set to NULL for test data):
- `test_search_tags_excludes_mature_content`
- `test_search_tags_mature_keywords`
- Test database setup functions

## Testing
Manually tested the endpoint with the following scenarios:
- ✅ Retrieve anime by valid tag_id (e.g., tag_id=2626 for "future" tag)
- ✅ Limit parameter works correctly
- ✅ Mature content filtering works
- ✅ Invalid tag_id returns 400 error
- ✅ Out-of-range limit returns 400 error
- ✅ Returns tag name along with results

## Example Usage

```bash
# Get top 10 anime with the "military" tag (tag_id=36)
curl "http://localhost:8000/tags/36?limit=10"

# Get top 50 anime with the "future" tag, including mature content
curl "http://localhost:8000/tags/2626?limit=50&mature=true"

# Get all anime with a specific tag (up to 1000)
curl "http://localhost:8000/tags/2846?limit=1000"
```

## Notes
- The database schema change is backward-compatible (uses `CREATE TABLE IF NOT EXISTS`)
- Existing databases will need to be reindexed to populate the `tag_id` column
- Tag IDs come directly from AniDB's XML data
- The endpoint respects the same mature content filtering as other endpoints
