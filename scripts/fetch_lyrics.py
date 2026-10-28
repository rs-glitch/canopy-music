"""Fetch lyrics for tracks that don't have a row in `lyrics` yet.

Jamendo (live API and the Internet Archive copy) has a lyrics field that
artists fill in. ccMixter has none, but some artists paste lyrics into the
upload description under a "Lyrics" heading; those are picked out here.
Other sources have no lyrics. A track checked with nothing found gets an
empty row so it isn't asked about again.

Usage: python3 -I scripts/fetch_lyrics.py
"""

import http.client
import json
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from count_ia import DATA  # noqa: E402
from ingest_jamendo import client_id  # noqa: E402
from schema import SCHEMA  # noqa: E402

JAMENDO = "https://api.jamendo.com/v3.0/tracks/"
CCMIXTER = "https://ccmixter.org/api/query"
http.client._MAXLINE = 8 * 1024 * 1024  # ccMixter echoes huge headers
# A line that announces lyrics: "Lyrics", "LYRICS:", "Rêves et Perspectives Lyrics", "Lyrics by Snowflake".
HEADING = re.compile(r"^[^\S\n]*(?:[\w'’ .-]{0,60}[^\S\n])?lyrics?\b[^\n,.!?]{0,40}:?[^\S\n]*$", re.I | re.M)


def get(url, tries=4):
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "canopy/0.1 (personal learning project)"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except (OSError, ValueError):
            time.sleep(3 * (attempt + 1))
    return None


def tidy(text):
    text = re.sub(r"\r\n?|\u2028", "\n", text or "").strip()
    text = re.sub(r"\n[^\S\n]+\n", "\n\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Some artists leave a blank line after every line; single-space those, keeping a gap before [Verse] labels.
    if text.count("\n\n") > 2 * len(re.findall(r"[^\n]\n[^\n]", text)):
        text = re.sub(r"\n(?=\[)", "\n\n", text.replace("\n\n", "\n"))
    return text[:12000]


def from_description(desc):
    """Lyrics pasted under a heading in a ccMixter description, or ''."""
    desc = tidy(desc)
    m = HEADING.search(desc)
    if not m:
        return ""
    body = desc[m.end():].strip()
    lines = [ln for ln in body.split("\n") if ln.strip()]
    if len(lines) < 4 or sum(map(len, lines)) / len(lines) > 80:
        return ""  # prose that mentions lyrics, not lyrics
    return body


def jamendo_id(source, item_id, file_name):
    if source == "jamendo_api":
        return item_id.split("/", 1)[1]
    m = re.match(r"\d+-(\d+)-", file_name)  # Internet Archive copy: "01-1899563-Album-Title.mp3"
    return m.group(1) if m else None


def main():
    db = sqlite3.connect(DATA / "music.db")
    db.executescript(SCHEMA)
    todo = db.execute("""SELECT id, source, item_id, file_name FROM tracks
                         WHERE source IN ('jamendo_api', 'jamendo', 'ccmixter')
                           AND id NOT IN (SELECT track_id FROM lyrics)""").fetchall()
    print(f"{len(todo)} tracks to check", file=sys.stderr)
    save = "INSERT OR REPLACE INTO lyrics (track_id, text) VALUES (?, ?)"

    jam = {}
    for tid, source, item_id, file_name in todo:
        if source == "ccmixter":
            continue
        jid = jamendo_id(source, item_id, file_name)
        if jid:
            jam.setdefault(jid, []).append(tid)
        else:
            db.execute(save, (tid, ""))
    ids, cid, found = list(jam), client_id(), 0
    chunks = [ids[i:i + 50] for i in range(0, len(ids), 50)]  # the API takes at most 50 ids per parameter
    urls = [JAMENDO + "?" + urllib.parse.urlencode({
        "client_id": cid, "format": "json", "limit": 50, "id": " ".join(c), "include": "lyrics"}) for c in chunks]
    pool = ThreadPoolExecutor(4)
    for n, (chunk, d) in enumerate(zip(chunks, pool.map(get, urls))):
        if not d or d["headers"]["status"] != "success":
            print(f"  jamendo error: {d and d['headers']['error_message']}", file=sys.stderr)
            continue  # try again next run
        got = {str(t["id"]): tidy(t.get("lyrics")) for t in d.get("results", [])}
        rows = [(tid, got.get(jid, "")) for jid in chunk for tid in jam[jid]]
        found += sum(1 for _, text in rows if text)
        db.executemany(save, rows)
        db.commit()
        if n % 100 == 0 or n == len(chunks) - 1:
            print(f"  jamendo {n * 50 + len(chunk)}/{len(ids)}: {found} with lyrics", file=sys.stderr)

    cc = {item_id.rsplit("/", 1)[1]: tid for tid, source, item_id, _ in todo if source == "ccmixter"}
    ids, found_cc = list(cc), 0
    chunks = [ids[i:i + 50] for i in range(0, len(ids), 50)]
    urls = [CCMIXTER + "?" + urllib.parse.urlencode({"f": "json", "ids": ",".join(c), "limit": 50}) for c in chunks]
    for chunk, d in zip(chunks, pool.map(get, urls)):
        if not isinstance(d, list):
            continue  # try again next run
        got = {str(u["upload_id"]): from_description(u.get("upload_description_plain")) for u in d}
        rows = [(cc[uid], got.get(uid, "")) for uid in chunk]
        found_cc += sum(1 for _, text in rows if text)
        db.executemany(save, rows)
        db.commit()
    print(f"lyrics: {found} Jamendo, {found_cc} ccMixter", file=sys.stderr)


if __name__ == "__main__":
    main()
