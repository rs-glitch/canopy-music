"""Add trending tracks from Audius to data/music.db.

Audius tracks are streamed under the Audius Open Music License, which grants
music-player apps the right to stream them (the uploader warrants they own the
rights). Most are "all rights reserved" otherwise, so they are for listening in
this app only. Audio is never stored; the app streams from Audius on demand.

The trending chart pages only ~300 deep, so this walks every music genre over
three time windows (week, month, all time) plus the underground chart.

To keep clear of uploads that are unlikely to be the uploader's to license,
it skips: covers, DJ mixes, bootlegs/mashups/leaks, gated or unlisted tracks,
and non-music genres (podcasts, audiobooks, spoken word, comedy).

Usage: python3 -I scripts/ingest_audius.py [--tracks 10000]
"""

import argparse
import json
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from count_ia import DATA  # noqa: E402
from ingest import parse_year  # noqa: E402
from schema import SCHEMA  # noqa: E402

API = "https://api.audius.co/v1"
APP = "canopy-learning"  # Audius asks apps to identify themselves
OML = "https://audius.org/open-music-license.pdf"
PAGE, MAX_OFFSET = 100, 200  # the trending endpoint rejects offsets past 200
WINDOWS = ["week", "month", "allTime"]
GENRES = [
    "Electronic", "Rock", "Metal", "Alternative", "Hip-Hop/Rap", "Experimental", "Punk", "Folk", "Pop",
    "Ambient", "Soundtrack", "World", "Jazz", "Acoustic", "Funk", "R&B/Soul", "Devotional", "Classical",
    "Reggae", "Country", "Blues", "Latin", "Lo-Fi", "Hyperpop", "Dancehall", "Techno", "Trap", "House",
    "Tech House", "Deep House", "Disco", "Electro", "Jungle", "Progressive House", "Hardstyle",
    "Glitch Hop", "Trance", "Future Bass", "Future House", "Tropical House", "Downtempo", "Drum & Bass",
    "Dubstep", "Jersey Club", "Vaporwave", "Moombahton",
]
SKIP_GENRES = {"Podcasts", "Audiobooks", "Spoken Word", "Comedy", "DJ Mixes", "Kids"}
RISKY_TITLE = re.compile(r"\b(bootleg|mashup|mash-up|leak(ed)?|unreleased|snippet|dj mix|full mix|"
                         r"live set|cover)\b", re.I)


def get(path, **params):
    url = f"{API}{path}?" + urllib.parse.urlencode({"app_name": APP, **params})
    for attempt in range(5):
        try:
            # Cloudflare in front of the API refuses Python's default User-Agent.
            req = urllib.request.Request(url, headers={"User-Agent": "canopy/0.1 (personal learning project)"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r).get("data") or []
        except urllib.error.HTTPError as e:
            if e.code == 400:
                return []  # past the end of a chart
            time.sleep(2 * (attempt + 1))
        except OSError:
            time.sleep(2 * (attempt + 1))
    return []


def acceptable(t):
    return (t.get("is_streamable") and not t.get("is_stream_gated") and not t.get("stream_conditions")
            and not t.get("is_delete") and not t.get("is_unlisted") and t.get("is_available", True)
            and t.get("genre") not in SKIP_GENRES and not t.get("cover_original_artist")
            and not RISKY_TITLE.search(t.get("title") or "")
            and 30 <= (t.get("duration") or 0) <= 20 * 60)


def row_for(t):
    album = t.get("album_backlink")
    lic = t.get("license") or ""
    cc = re.search(r"CC (BY[\w-]*)", lic)
    return {
        "source": "audius",
        "item_id": (t.get("permalink") or "").lstrip("/"),  # also the audius.co/ path
        "file_name": str(t["id"]),
        "title": t["title"],
        "artist": (t.get("user") or {}).get("name"),
        "album": album.get("playlist_name") if isinstance(album, dict) else None,
        "year": parse_year(t.get("release_date") or t.get("created_at")),
        "track_no": None,
        "duration": t.get("duration"),
        "size": None,  # mp3chunk asks the server
        "language": None,
        "license_url": f"https://creativecommons.org/licenses/{cc.group(1).lower()}/4.0/" if cc else OML,
        "license": lic if cc else "Audius Open Music License (stream only)",
        "genre_tag": ", ".join(x for x in (t.get("genre"), t.get("mood")) if x) or None,
        "url": f"{API}/tracks/{t['id']}/stream?app_name={APP}",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tracks", type=int, default=10000)
    args = ap.parse_args()

    db = sqlite3.connect(DATA / "music.db")
    db.executescript(SCHEMA)
    cols = ["source", "item_id", "file_name", "title", "artist", "album", "year", "track_no",
            "duration", "size", "language", "license_url", "license", "genre_tag", "url"]
    insert = f"INSERT OR IGNORE INTO tracks ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})"

    charts = [("/tracks/trending/underground", {})] + [
        ("/tracks/trending", {"genre": g, "time": w}) for w in WINDOWS for g in GENRES]
    seen, skipped = {}, 0
    for path, params in charts:
        for offset in range(0, MAX_OFFSET + 1, PAGE):
            page = get(path, limit=PAGE, offset=offset, **params)
            for t in page:
                if t["id"] in seen:
                    continue
                if acceptable(t):
                    seen[t["id"]] = row_for(t)
                else:
                    skipped += 1
            if len(page) < PAGE:
                break
        print(f"  {params.get('genre', 'underground')} {params.get('time', '')}: "
              f"{len(seen)} tracks, {skipped} skipped", file=sys.stderr)
        if len(seen) >= args.tracks:
            break

    rows = list(seen.values())[:args.tracks]
    db.executemany(insert, [[r[c] for c in cols] for r in rows])
    db.execute("INSERT INTO tracks_fts(tracks_fts) VALUES ('rebuild')")
    db.commit()
    print(db.execute("SELECT count(*), min(year), max(year) FROM tracks WHERE source='audius'").fetchone())


if __name__ == "__main__":
    main()
