# Progress

**Goal:** a personal, searchable library of music that anyone may legally stream, with playback, audio analysis and a calm place to listen in.

## 2026-10-20 · Census and the first library
- **Census before building:** `scripts/count_ia.py` counted the Internet Archive's openly licensed collections and estimated about 1.29 million tracks from 1925 on (95% range 1.0M–1.57M).
- **The big find:** 41% of the community collection was mislabelled, including one bulk upload of 39,513 commercial jazz 78s marked CC0. `plausibly_licensed()` drops it and the Public Domain Mark items.
- **Reality check:** almost no music people already know is free, so the project became about discovery rather than looking up known songs.
- **Steps 1 and 2:** a 5,000-track sample with full-text search and a waveform player, then analysis (tempo, key, loudness, vocals, genre, mood) exposed as filters.

## 2026-10-20 · The redesign as Canopy
- **Look:** rebuilt with the scroll-craft design skill as a night forest under deep space, drawn entirely in code. The brief is in [docs/design/BRIEF.md](docs/design/BRIEF.md).
- **Signature:** every track played for 20 seconds becomes a star joined to the last.
- **Player:** a closable, translucent overlay.

## Growing the library
- **Scale-up:** 5k → 10k → 20k tracks across four Internet Archive sources, plus a shuffle button.
- **"Everything is super old and/or instrumental":** free recent music is mostly background instrumentals, so Canopy opens on With vocals + Newest. It added ccMixter (5,000 vocal tracks) and every English vocal song from Jamendo's live API.
- **More sources:** about ten were surveyed, and Audius was added (10,000 trending tracks under its Open Music License).
- **Spanish:** all of Jamendo's ~8,300 Spanish vocal songs, and a language filter.
- **Clean-up:** 1,444 HTML-escaped titles, artists and albums fixed in place.
- **Reversed:** a large cursive "Canopy" in the sky was tried in several sizes and positions, then removed.

## Features 1–13
- **1–10:** the real moon, the clock sky, shooting stars, song-coloured stars, named constellations, beat fireflies, more like this, DJ mode, stations with endless play, and the mood map.
- **11–13:** never heard, the weekly refresh with "New this week", and lyrics for about 24,000 songs. The weekly job runs from launchd and needs Full Disk Access for Python.
- **Waiting (14–19):** sleep timer, lock-screen controls, install as an app, faster Audius start, a yearly "year in stars" recap, and artist pages.

## 2026-10-28 · Repo
- **Clean copy:** code, docs and the census results only. The library, its backups, the item lists, logs and the Jamendo Client ID stay out (`.gitignore`).
- **Portable schedule:** `scripts/canopy.refresh.plist` holds `__CANOPY__` and `__HOME__` placeholders that a `sed` line fills in at install.
- **Added:** `requirements.txt` with the pinned versions Canopy runs on, and fresh screenshots of the full 94,589-track library.
