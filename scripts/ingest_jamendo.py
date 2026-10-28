"""Add the newest English vocal tracks from Jamendo's live API to data/music.db.

The Internet Archive copy of Jamendo (source "jamendo") stops years ago; this
pulls current releases (source "jamendo_api"). Needs a free client ID from
devportal.jamendo.com in .jamendo_client_id or JAMENDO_CLIENT_ID.

Usage: python3 -I scripts/ingest_jamendo.py [--tracks 5000] [--lang en]
"""

import argparse
import html
import json
import os
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from count_ia import DATA  # noqa: E402
from ingest import license_label, parse_year  # noqa: E402
from schema import SCHEMA  # noqa: E402

API = "https://api.jamendo.com/v3.0/tracks/"
PAGE = 200  # API maximum


def client_id():
    key_file = DATA.parent / ".jamendo_client_id"
    cid = os.environ.get("JAMENDO_CLIENT_ID") or (key_file.read_text().strip() if key_file.exists() else "")
    if not cid:
        sys.exit("Set JAMENDO_CLIENT_ID or put the client ID in .jamendo_client_id")
    return cid


def query(cid, lang, offset, tries=6):
    """One page of results. The API intermittently answers with an empty page, so retry those."""
    for attempt in range(tries):
        results = query_once(cid, lang, offset)
        if results:
            return results
        time.sleep(2 * (attempt + 1))
    return []


def query_once(cid, lang, offset):
    url = API + "?" + urllib.parse.urlencode({
        "client_id": cid, "format": "json", "limit": PAGE, "offset": offset,
        "vocalinstrumental": "vocal", "lang": lang, "order": "releasedate_desc",
        "include": "musicinfo", "audioformat": "mp32"})
    with urllib.request.urlopen(url, timeout=120) as r:
        d = json.load(r)
    if d["headers"]["status"] != "success":
        raise RuntimeError(d["headers"]["error_message"])
    return d["results"]


def clean(s):
    """Some titles arrive HTML-escaped, sometimes twice ("Don&amp;#039;t"); decode until stable."""
    while s and (u := html.unescape(s)) != s:
        s = u
    return s


def row_for(t, lang):
    genres = ((t.get("musicinfo") or {}).get("tags") or {}).get("genres") or []
    return {
        "source": "jamendo_api",
        "item_id": f"track/{t['id']}",  # also the jamendo.com/ path
        "file_name": f"{t['id']}.mp3",
        "title": clean(t["name"]),
        "artist": clean(t["artist_name"]),
        "album": clean(t.get("album_name")),
        "year": parse_year(t.get("releasedate")),
        "track_no": t.get("position"),
        "duration": t.get("duration"),
        "size": None,  # not in the API; mp3chunk asks the server
        "language": lang,
        "license_url": t.get("license_ccurl"),
        "license": license_label(t.get("license_ccurl")),
        "genre_tag": ", ".join(genres) or None,
        # Stable form of t["audio"] without its session token; serves CORS and Range.
        "url": f"https://prod-1.storage.jamendo.com/?trackid={t['id']}&format=mp32",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tracks", type=int, default=5000)
    ap.add_argument("--lang", default="en")
    args = ap.parse_args()
    cid = client_id()

    db = sqlite3.connect(DATA / "music.db")
    db.executescript(SCHEMA)
    cols = ["source", "item_id", "file_name", "title", "artist", "album", "year", "track_no",
            "duration", "size", "language", "license_url", "license", "genre_tag", "url"]
    insert = f"INSERT OR IGNORE INTO tracks ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})"

    have = db.execute("SELECT count(*) FROM tracks WHERE source='jamendo_api'").fetchone()[0]
    offset = 0
    while have < args.tracks:
        page = query(cid, args.lang, offset)
        rows = [r for t in page if 30 <= (r := row_for(t, args.lang))["duration"] <= 20 * 60]
        have += db.executemany(insert, [[r[c] for c in cols] for r in rows[:args.tracks - have]]).rowcount
        db.commit()
        print(f"  offset {offset}: {len(page)} results, {have} tracks", file=sys.stderr)
        if len(page) < PAGE:
            break
        offset += PAGE

    db.execute("INSERT INTO tracks_fts(tracks_fts) VALUES ('rebuild')")
    db.commit()
    print(db.execute("SELECT count(*), min(year), max(year) FROM tracks WHERE source='jamendo_api'").fetchone())


if __name__ == "__main__":
    main()
