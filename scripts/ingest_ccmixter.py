"""Add recent vocal tracks from ccMixter (CC-licensed, artist-uploaded) to data/music.db.

Queries ccMixter's API for uploads tagged with sung vocals, newest first, and
skips bare a cappella stems (raw vocals meant for remixing, not songs).
ccMixter refuses hotlinked audio, so the app plays these through /api/stream.

Usage: python3 -I scripts/ingest_ccmixter.py [--tracks 5000]
"""

import argparse
import html
import http.client
import json
import re
import sqlite3
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from count_ia import DATA  # noqa: E402
from ingest import license_label, parse_duration  # noqa: E402
from schema import SCHEMA  # noqa: E402

API = "https://ccmixter.org/api/query"
VOCAL_TAGS = ["female_vocals", "male_vocals", "vocals"]
PAGE = 50
# The API echoes a huge header (~5 KB per result) that trips http.client's 64 KB line limit.
http.client._MAXLINE = 8 * 1024 * 1024


def query(tags, offset):
    url = f"{API}?" + urllib.parse.urlencode({
        "f": "json", "tags": f"{tags},-acappella", "sort": "date", "ord": "desc",
        "limit": PAGE, "offset": offset})
    req = urllib.request.Request(url, headers={"User-Agent": "canopy/0.1"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8", "replace"))  # a few uploads carry cp1252 bytes


def clean(s):
    """Some titles arrive HTML-escaped, sometimes twice ("Don&amp;#039;t"); decode until stable."""
    while s and (u := html.unescape(s)) != s:
        s = u
    return s


def row_for(u):
    mp3 = next((f for f in u.get("files", [])
                if f.get("file_format_info", {}).get("mime_type") == "audio/mpeg"
                and not f.get("file_is_remote")), None)
    if not mp3:
        return None
    year = re.search(r", (\d{4}) @", u.get("upload_date_format", ""))
    tags = (u.get("upload_extra") or {}).get("usertags") or ""
    return {
        "source": "ccmixter",
        "item_id": f"{u['user_name']}/{u['upload_id']}",  # also the ccmixter.org/files/ path
        "file_name": mp3["file_name"],
        "title": clean(u["upload_name"]),
        "artist": clean(u.get("user_real_name") or u["user_name"]),
        "album": None,
        "year": int(year.group(1)) if year else None,
        "track_no": None,
        "duration": parse_duration(mp3.get("file_format_info", {}).get("ps")),
        "size": mp3.get("file_rawsize"),
        "language": None,
        "license_url": u.get("license_url"),
        "license": license_label(u.get("license_url")),
        "genre_tag": ", ".join(t.replace("_", " ") for t in tags.split(",")[:6] if t) or None,
        "url": mp3["download_url"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tracks", type=int, default=5000)
    args = ap.parse_args()

    db = sqlite3.connect(DATA / "music.db")
    db.executescript(SCHEMA)
    cols = ["source", "item_id", "file_name", "title", "artist", "album", "year", "track_no",
            "duration", "size", "language", "license_url", "license", "genre_tag", "url"]
    insert = f"INSERT OR IGNORE INTO tracks ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})"

    # Newest uploads across all vocal tags, merged by upload id.
    uploads = {}
    for tag in VOCAL_TAGS:
        offset = 0
        while True:
            page = query(tag, offset)
            for u in page:
                uploads[u["upload_id"]] = u
            print(f"  {tag}: {offset + len(page)} fetched, {len(uploads)} unique", file=sys.stderr)
            if len(page) < PAGE or offset + PAGE >= args.tracks:
                break
            offset += PAGE

    rows = [r for u in sorted(uploads.values(), key=lambda u: -u["upload_id"])
            if (r := row_for(u)) and (not r["duration"] or 30 <= r["duration"] <= 20 * 60)]
    db.executemany(insert, [[r[c] for c in cols] for r in rows[:args.tracks]])
    db.execute("INSERT INTO tracks_fts(tracks_fts) VALUES ('rebuild')")
    db.commit()
    print(db.execute("SELECT count(*), min(year), max(year) FROM tracks WHERE source='ccmixter'").fetchone())


if __name__ == "__main__":
    main()
