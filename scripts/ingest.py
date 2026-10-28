"""Build the track index from a sample of Internet Archive items.

Reads the item lists written by count_ia.py, samples items from each source
until a per-source track target is reached, fetches each item's file list and
writes one row per playable track into data/music.db (with an FTS5 index).

Usage: python3 -I scripts/ingest.py [--tracks-per-source 1250] [--workers 8]
"""

import argparse
import json
import random
import re
import sqlite3
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from count_ia import DATA, get_json, lang_bucket, load_items, plausibly_licensed, year_ok  # noqa: E402
from schema import SCHEMA  # noqa: E402

SOURCES = ["jamendo", "fma", "ia_cc_music", "netlabels_cc"]
PLAYABLE = re.compile(r"mp3", re.I)
OTHER_AUDIO = re.compile(r"flac|ogg|vorbis|wave|aiff|m4a|aac|opus", re.I)
# Uploads that look like bulk dumps rather than releases.
JUNK_TITLE = re.compile(r"\b(collection|complete|discography|full album rip|seagate|backup|podcast|episode)\b", re.I)



def first(v):
    return v[0] if isinstance(v, list) else v


def parse_duration(v):
    v = first(v)
    if v is None:
        return None
    try:
        if ":" in str(v):
            secs = 0.0
            for part in str(v).split(":"):
                secs = secs * 60 + float(part)
            return secs
        return float(v)
    except ValueError:
        return None


def parse_int(v):
    m = re.match(r"\s*(\d+)", str(first(v) or ""))
    return int(m.group(1)) if m else None


def parse_year(v):
    y = parse_int(v)
    return y if y and 1000 <= y <= 2100 else None


def license_label(url):
    url = first(url) or ""
    if "publicdomain" in url:
        return "Public domain"
    m = re.search(r"licenses/([a-z-]+)/([\d.]+)", url)
    return f"CC {m.group(1).upper()} {m.group(2)}" if m else ("Unknown" if not url else url)


def clean_title(file_name, artist):
    stem = re.sub(r"\.[^.]+$", "", file_name.rsplit("/", 1)[-1])
    stem = re.sub(r"^\d+[-_. ]+(\d{4,}[-_ ]+)?", "", stem)  # leading track no / jamendo id
    if artist:
        stem = re.sub(r"^" + re.escape(artist) + r"\s*[-_]\s*", "", stem, flags=re.I)
    return stem.replace("_", " ").strip() or file_name


def tracks_for_item(source, item):
    ident = item["identifier"]
    meta = get_json(f"https://archive.org/metadata/{urllib.parse.quote(ident)}")
    md = meta.get("metadata", {})
    files = meta.get("files", [])
    item_artist = first(md.get("creator")) or first(item.get("creator"))
    item_license = first(md.get("licenseurl")) or first(item.get("licenseurl"))
    if not item_license:
        lic = next((f for f in files if f["name"].lower() == "license.txt"), None)
        if lic:  # jamendo/fma mirrors keep the license in a text file
            text = urllib.request.urlopen(
                f"https://archive.org/download/{urllib.parse.quote(ident)}/{urllib.parse.quote(lic['name'])}", timeout=30
            ).read(4000).decode("utf-8", "replace")
            m = re.search(r"https?://creativecommons\.org/[^\s\"'<>]+", text)
            item_license = m.group(0) if m else None

    # One row per track stem; prefer an MP3 (original first) for playback.
    by_stem = {}
    for f in files:
        fmt = f.get("format", "")
        if not (PLAYABLE.search(fmt) or OTHER_AUDIO.search(fmt)):
            continue
        stem = re.sub(r"\.[^.]+$", "", f["name"])
        rank = (0 if PLAYABLE.search(fmt) else 1, 0 if f.get("source") == "original" else 1)
        if stem not in by_stem or rank < by_stem[stem][0]:
            by_stem[stem] = (rank, f)

    rows = []
    for rank, f in by_stem.values():
        if rank[0] != 0:
            continue  # no browser-playable MP3 for this track
        artist = first(f.get("artist")) or first(f.get("creator")) or item_artist
        rows.append({
            "source": source,
            "item_id": ident,
            "file_name": f["name"],
            "title": first(f.get("title")) or clean_title(f["name"], artist),
            "artist": artist,
            "album": first(f.get("album")) or first(md.get("title")) or first(item.get("title")),
            "year": parse_year(md.get("year") or item.get("year") or md.get("date")),
            "track_no": parse_int(f.get("track")),
            "duration": parse_duration(f.get("length")),
            "size": parse_int(f.get("size")),
            "language": lang_bucket(item),
            "license_url": item_license,
            "license": license_label(item_license),
            "genre_tag": first(f.get("genre")),
            "url": f"https://archive.org/download/{urllib.parse.quote(ident)}/{urllib.parse.quote(f['name'])}",
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tracks-per-source", type=int, default=1250)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()
    random.seed(7)

    db = sqlite3.connect(DATA / "music.db")
    db.executescript(SCHEMA)
    cols = ["source", "item_id", "file_name", "title", "artist", "album", "year", "track_no",
            "duration", "size", "language", "license_url", "license", "genre_tag", "url"]
    insert = f"INSERT OR IGNORE INTO tracks ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})"

    for source in SOURCES:
        have = db.execute("SELECT count(*) FROM tracks WHERE source=?", (source,)).fetchone()[0]
        done_items = {r[0] for r in db.execute("SELECT DISTINCT item_id FROM tracks WHERE source=?", (source,))}
        items = [i for i in load_items(source)
                 if year_ok(i) and plausibly_licensed(i) and i["identifier"] not in done_items
                 and lang_bucket(i) != "other_language"
                 and not JUNK_TITLE.search(str(first(i.get("title")) or ""))]
        random.shuffle(items)
        pos = 0
        with ThreadPoolExecutor(args.workers) as pool:
            while have < args.tracks_per_source and pos < len(items):
                batch = items[pos:pos + args.workers * 4]
                pos += len(batch)
                futures = {pool.submit(tracks_for_item, source, it): it for it in batch}
                for fut in as_completed(futures):
                    try:
                        rows = fut.result()
                    except Exception as e:
                        print(f"  skip {futures[fut]['identifier']}: {e}", file=sys.stderr)
                        continue
                    rows = [r for r in rows
                            if (not r["duration"] or 30 <= r["duration"] <= 20 * 60)
                            and (not r["year"] or r["year"] >= 1925)]
                    db.executemany(insert, [[r[c] for c in cols] for r in rows])
                    have += len(rows)
                db.commit()
                print(f"  {source}: {have} tracks from {pos} items", file=sys.stderr)

    db.execute("INSERT INTO tracks_fts(tracks_fts) VALUES ('rebuild')")
    db.commit()
    for row in db.execute("SELECT source, count(*), count(DISTINCT item_id) FROM tracks GROUP BY source"):
        print(row)


if __name__ == "__main__":
    main()
