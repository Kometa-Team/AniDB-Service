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
