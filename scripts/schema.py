"""Shared SQLite schema for data/music.db."""

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    item_id TEXT NOT NULL,
    file_name TEXT NOT NULL,
    title TEXT, artist TEXT, album TEXT,
    year INTEGER, track_no INTEGER, duration REAL, size INTEGER,
    language TEXT, license_url TEXT, license TEXT, genre_tag TEXT,
    url TEXT NOT NULL,
    UNIQUE (item_id, file_name)
);
CREATE VIRTUAL TABLE IF NOT EXISTS tracks_fts USING fts5(
    title, artist, album, content='tracks', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);
CREATE TABLE IF NOT EXISTS analysis (
    track_id INTEGER PRIMARY KEY REFERENCES tracks(id),
    bpm REAL, musical_key TEXT, key_confidence REAL, loudness_db REAL,
    vocal_prob REAL, speech_prob REAL, genre TEXT, mood TEXT,
    tags TEXT, error TEXT, analyzed_at REAL
);
-- Where each analyzed track sits on the mood map: x calm -> energetic, y sad -> happy, both 0..1.
CREATE TABLE IF NOT EXISTS mood_map (
    track_id INTEGER PRIMARY KEY REFERENCES tracks(id),
    x REAL NOT NULL, y REAL NOT NULL
);
-- Lyrics where the source has them; '' means checked and none found.
CREATE TABLE IF NOT EXISTS lyrics (
    track_id INTEGER PRIMARY KEY REFERENCES tracks(id),
    text TEXT NOT NULL
);
-- Tracks the listener has heard for at least 20 s, mirrored from the browser for the "never heard" filter.
CREATE TABLE IF NOT EXISTS heard (
    track_id INTEGER PRIMARY KEY, at REAL
);
-- One row per weekly refresh: tracks with id >= first_id arrived in it.
CREATE TABLE IF NOT EXISTS refreshes (
    ran_at REAL NOT NULL, first_id INTEGER NOT NULL, added INTEGER NOT NULL, by_source TEXT
);
"""
