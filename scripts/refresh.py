"""Weekly refresh: pull new uploads from every live source, then lyrics, analysis and the mood map.

- Jamendo (English and Spanish vocals) and ccMixter: newest first, stopping at
  the first page with nothing new.
- Audius: this week's trending charts across every genre.

New tracks are logged in `refreshes`, which the app reads for its "New this
week" station. Runs from launchd every Sunday (see scripts/canopy.refresh.plist).

Usage: .venv/bin/python -I scripts/refresh.py [--skip-analysis]
"""

import argparse
import json
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_lyrics  # noqa: E402
import ingest_audius  # noqa: E402
import ingest_ccmixter  # noqa: E402
import ingest_jamendo  # noqa: E402
from count_ia import DATA  # noqa: E402
from schema import SCHEMA  # noqa: E402

COLS = ["source", "item_id", "file_name", "title", "artist", "album", "year", "track_no",
        "duration", "size", "language", "license_url", "license", "genre_tag", "url"]
INSERT = f"INSERT OR IGNORE INTO tracks ({','.join(COLS)}) VALUES ({','.join('?' * len(COLS))})"
MAX_PAGES = 40  # a backstop; a normal week is a page or two per source


def log(msg):
    print(f"{time.strftime('%Y-%m-%d %H:%M')}  {msg}", file=sys.stderr, flush=True)


def add(db, rows):
    n = db.executemany(INSERT, [[r[c] for c in COLS] for r in rows]).rowcount
    db.commit()
    return n


def jamendo(db):
    cid, total = ingest_jamendo.client_id(), 0
    for lang in ("en", "es"):
        for page_no in range(MAX_PAGES):
            page = ingest_jamendo.query(cid, lang, page_no * ingest_jamendo.PAGE)
            rows = [r for t in page if 30 <= (r := ingest_jamendo.row_for(t, lang))["duration"] <= 20 * 60]
            new = add(db, rows)
            total += new
            if not new or len(page) < ingest_jamendo.PAGE:
                break
    return total


def ccmixter(db):
    total = 0
    for tag in ingest_ccmixter.VOCAL_TAGS:
        for page_no in range(MAX_PAGES):
            page = ingest_ccmixter.query(tag, page_no * ingest_ccmixter.PAGE)
            rows = [r for u in page if (r := ingest_ccmixter.row_for(u))
                    and (not r["duration"] or 30 <= r["duration"] <= 20 * 60)]
            new = add(db, rows)
            total += new
            if not new or len(page) < ingest_ccmixter.PAGE:
                break
    return total


def audius(db):
    charts = [("/tracks/trending/underground", {})] + [
        ("/tracks/trending", {"genre": g, "time": "week"}) for g in ingest_audius.GENRES]
    total = 0
    for path, params in charts:
        for offset in range(0, ingest_audius.MAX_OFFSET + 1, ingest_audius.PAGE):
            page = ingest_audius.get(path, limit=ingest_audius.PAGE, offset=offset, **params)
            total += add(db, [ingest_audius.row_for(t) for t in page if ingest_audius.acceptable(t)])
            if len(page) < ingest_audius.PAGE:
                break
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-analysis", action="store_true")
    args = ap.parse_args()

    db = sqlite3.connect(DATA / "music.db", timeout=60)
    db.executescript(SCHEMA)
    first_id = db.execute("SELECT coalesce(max(id), 0) + 1 FROM tracks").fetchone()[0]
    by_source = {}
    for name, fn in (("jamendo", jamendo), ("ccmixter", ccmixter), ("audius", audius)):
        try:
            by_source[name] = fn(db)
        except Exception as e:  # one source being down shouldn't sink the others
            log(f"{name} failed: {e}")
            by_source[name] = 0
        log(f"{name}: {by_source[name]} new")
    added = sum(by_source.values())
    db.execute("INSERT INTO tracks_fts(tracks_fts) VALUES ('rebuild')")
    db.execute("INSERT INTO refreshes VALUES (?, ?, ?, ?)", (time.time(), first_id, added, json.dumps(by_source)))
    db.commit()
    log(f"{added} new tracks")

    if added:
        fetch_lyrics.main()
        if not args.skip_analysis:
            root = Path(__file__).resolve().parent.parent
            subprocess.run([str(root / ".venv/bin/python"), "-I", str(root / "scripts/analyze.py")], check=False)
    log("done")


if __name__ == "__main__":
    main()
