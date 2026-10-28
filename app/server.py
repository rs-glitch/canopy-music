"""Local music browser: search API over data/music.db plus the static UI.

Run: .venv/bin/uvicorn app.server:app --port 8765
"""

import json
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, StreamingResponse

ROOT = Path(__file__).resolve().parent
DB = ROOT.parent / "data" / "music.db"
# PANNs under-scores sung vocals in full mixes and often hears dense rock/rap
# vocals as "Speech"; thresholds calibrated by inspecting the score distribution.
VOCAL_SQL = "(a.vocal_prob >= 0.10 OR a.speech_prob >= 0.15)"

sys.path.insert(0, str(ROOT.parent / "scripts"))
from mp3chunk import REFERERS, request_headers  # noqa: E402
from schema import SCHEMA  # noqa: E402

app = FastAPI(title="Canopy")
app.add_middleware(GZipMiddleware, minimum_size=2000)
with sqlite3.connect(DB) as _conn:  # create tables the pipeline hasn't reached yet
    _conn.executescript(SCHEMA)


def db():
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def fts_query(q):
    """Turn free text into a prefix-matching FTS5 query: 'blue sk' -> "blue"* "sk"*."""
    words = re.findall(r"\w+", q, flags=re.UNICODE)
    return " ".join(f'"{w}"*' for w in words)


# Language codes as the ingest scripts stored them: Internet Archive sources say
# "english"/"untagged", the Jamendo API ones use ISO codes.
LANG_SQL = "CASE t.language WHEN 'english' THEN 'en' WHEN 'untagged' THEN NULL ELSE t.language END"


SELECT = f"""
SELECT t.id, t.title, t.artist, t.album, t.year, t.duration, t.license, t.license_url,
       t.source, t.item_id, t.url, t.genre_tag, {LANG_SQL} AS lang,
       a.bpm, a.musical_key, a.vocal_prob, a.speech_prob, a.genre, a.mood, a.loudness_db,
       EXISTS (SELECT 1 FROM lyrics l WHERE l.track_id = t.id AND l.text != '') AS has_lyrics
FROM tracks t LEFT JOIN analysis a ON a.track_id = t.id
"""


def row_out(r):
    d = dict(r)
    vp, sp = d.get("vocal_prob"), d.get("speech_prob")
    d["vocals"] = None if vp is None else (vp >= 0.10 or (sp or 0) >= 0.15)
    d["has_lyrics"] = bool(d.get("has_lyrics"))
    if d["source"] == "ccmixter":
        d["source_page"] = f"https://ccmixter.org/files/{d['item_id']}"
    elif d["source"] == "jamendo_api":
        d["source_page"] = f"https://www.jamendo.com/{d['item_id']}"
    elif d["source"] == "audius":
        d["source_page"] = f"https://audius.co/{d['item_id']}"
    else:
        d["source_page"] = f"https://archive.org/details/{d['item_id']}"
    if any(host in d["url"] for host in REFERERS):  # host refuses hotlinks; play via /api/stream
        d["url"] = f"/api/stream/{d['id']}"
    # Only Creative Commons licenses without NC; Audius's stream-only license never counts.
    d["commercial_ok"] = bool(d["license_url"]) and "creativecommons.org" in d["license_url"] and "-nc" not in d["license_url"]
    return d


# Harmonic mixing: a key blends with itself, its neighbours on the circle of fifths, and its relative major/minor.
PITCH = {"C": 0, "C#": 1, "D": 2, "Eb": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "Ab": 8, "A": 9, "Bb": 10, "B": 11}
NOTE = {v: k for k, v in PITCH.items()}


def compatible_keys(key):
    try:
        note, mode = key.split()
        pc = PITCH[note]
    except (AttributeError, ValueError, KeyError):
        return []
    other = "minor" if mode == "major" else "major"
    rel = (pc + 9) % 12 if mode == "major" else (pc + 3) % 12
    return [key, f"{NOTE[(pc + 7) % 12]} {mode}", f"{NOTE[(pc + 5) % 12]} {mode}", f"{NOTE[rel]} {other}"]


def filters(
    q: str = "",
    genre: list[str] = Query(default=[]),
    mood: list[str] = Query(default=[]),
    vocals: str | None = None,  # "vocal" | "instrumental"
    bpm_min: float | None = None,
    bpm_max: float | None = None,
    key: str | None = None,
    year_min: int | None = None,
    year_max: int | None = None,
    source: list[str] = Query(default=[]),
    language: list[str] = Query(default=[]),
    commercial: bool = False,
    unheard: bool = False,  # leave out everything in `heard`
    lyrics: bool = False,  # only tracks with lyrics
    since_id: int | None = None,  # only tracks added from this id on (a weekly refresh's first_id)
    like: int | None = None,  # "more like this": same vocals, close tempo, same mood or genre, best blends first
    map_x: float | None = None,  # an area on the mood map: centre and radii, in 0..1 map units
    map_y: float | None = None,
    map_r: float | None = None,
    map_ry: float | None = None,  # the map is wider than tall, so a round circle on screen has a taller y radius
):
    return {k: v for k, v in locals().items()}


def where_for(conn, f):
    """Joins, WHERE clauses and params for a set of filters, plus the "more like this" ordering if asked."""
    (q, genre, mood, vocals, bpm_min, bpm_max, key, year_min, year_max, source, language, commercial,
     unheard, lyrics, since_id, like, map_x, map_y, map_r, map_ry) = (f[k] for k in (
        "q", "genre", "mood", "vocals", "bpm_min", "bpm_max", "key", "year_min", "year_max", "source", "language",
        "commercial", "unheard", "lyrics", "since_id", "like", "map_x", "map_y", "map_r", "map_ry"))
    joins, where, params = "", [], []
    if q.strip():
        joins += " JOIN tracks_fts f ON f.rowid = t.id"
        where.append("tracks_fts MATCH ?")
        params.append(fts_query(q))
    if genre:
        where.append(f"a.genre IN ({','.join('?' * len(genre))})")
        params += genre
    if mood:
        where.append(f"a.mood IN ({','.join('?' * len(mood))})")
        params += mood
    if vocals == "vocal":
        where.append(VOCAL_SQL)
    elif vocals == "instrumental":
        where.append(f"a.vocal_prob IS NOT NULL AND NOT {VOCAL_SQL}")
    for col, op, val in (("a.bpm", ">=", bpm_min), ("a.bpm", "<=", bpm_max),
                         ("t.year", ">=", year_min), ("t.year", "<=", year_max)):
        if val is not None:
            where.append(f"{col} {op} ?")
            params.append(val)
    if key:
        where.append("a.musical_key = ?")
        params.append(key)
    if source:
        where.append(f"t.source IN ({','.join('?' * len(source))})")
        params += source
    if language:
        where.append(f"{LANG_SQL} IN ({','.join('?' * len(language))})")
        params += language
    if commercial:
        where.append("t.license_url LIKE '%creativecommons.org%' AND t.license_url NOT LIKE '%-nc%'")
    if unheard:
        where.append("t.id NOT IN (SELECT track_id FROM heard)")
    if lyrics:
        where.append("t.id IN (SELECT track_id FROM lyrics WHERE text != '')")
    if since_id is not None:
        where.append("t.id >= ?")
        params.append(since_id)
    if None not in (map_x, map_y, map_r):
        joins += " JOIN mood_map m ON m.track_id = t.id"
        ry = map_ry or map_r
        where.append("(m.x - ?) * (m.x - ?) / (? * ?) + (m.y - ?) * (m.y - ?) / (? * ?) <= 1")
        params += [map_x, map_x, map_r, map_r, map_y, map_y, ry, ry]
    like_order, order_params = None, []
    if like is not None:
        base = conn.execute(SELECT + " WHERE t.id = ?", (like,)).fetchone()
        if not base or base["bpm"] is None:
            where.append("0")
            return joins, where, params, None, []
        b = row_out(base)
        where.append("t.id != ? AND a.bpm BETWEEN ? AND ? AND (a.mood = ? OR a.genre = ?)")
        params += [like, b["bpm"] * 0.92, b["bpm"] * 1.08, b["mood"], b["genre"]]
        if b["vocals"] is not None:
            where.append(VOCAL_SQL if b["vocals"] else f"NOT {VOCAL_SQL}")
        keys = compatible_keys(b["musical_key"])
        like_order = (f"(a.mood IS ?) + (a.genre IS ?) + (a.musical_key IN ({','.join('?' * len(keys))}) ) * 0.8"
                      f" - abs(a.bpm - ?) / ? DESC, random()") if keys else "(a.mood IS ?) + (a.genre IS ?) - abs(a.bpm - ?) / ? DESC"
        order_params = [b["mood"], b["genre"], *keys, b["bpm"], b["bpm"] * 0.08]
    return joins, where, params, like_order, order_params


@app.get("/api/search")
def search(f: dict = Depends(filters), sort: str = "relevance",
           limit: int = Query(default=50, le=200), offset: int = 0):
    conn = db()
    joins, where, params, like_order, order_params = where_for(conn, f)
    sql = SELECT + joins
    if where:
        sql += " WHERE " + " AND ".join(where)
    q = f["q"]
    order = {
        "relevance": "f.rank" if q.strip() else "t.id",
        "newest": "t.year DESC NULLS LAST, t.id DESC",  # later-added sources (Jamendo, ccMixter) first within a year
        "oldest": "t.year ASC NULLS LAST",
        "bpm": "a.bpm ASC NULLS LAST",
        "title": "t.title COLLATE NOCASE",
        "random": "random()",
    }.get(sort, "t.id")
    total = conn.execute(f"SELECT count(*) FROM ({sql})", params).fetchone()[0]
    if like_order:
        order, params = like_order, params + order_params
    rows = conn.execute(f"{sql} ORDER BY {order} LIMIT ? OFFSET ?", params + [limit, offset]).fetchall()
    return {"total": total, "results": [row_out(r) for r in rows]}


MOODS = ["Tender", "Sad", "Happy", "Exciting", "Funny", "Scary", "Angry"]


@app.get("/api/map")
def mood_map(f: dict = Depends(filters)):
    """Every track matching the filters as a point: x and y in thousandths, plus its mood's index in MOODS."""
    conn = db()
    f = {**f, "map_x": None, "map_y": None, "map_r": None, "map_ry": None}
    joins, where, params, _, _ = where_for(conn, f)
    sql = ("SELECT m.x, m.y, a.mood FROM tracks t LEFT JOIN analysis a ON a.track_id = t.id"
           " JOIN mood_map m ON m.track_id = t.id" + joins)
    if where:
        sql += " WHERE " + " AND ".join(where)
    xs, ys, ms = [], [], []
    for x, y, mood in conn.execute(sql, params):
        xs.append(round(x * 1000)); ys.append(round(y * 1000)); ms.append(MOODS.index(mood) if mood in MOODS else -1)
    return {"moods": MOODS, "x": xs, "y": ys, "m": ms}


@app.get("/api/facets")
def facets():
    conn = db()
    out = {
        "sources": dict(conn.execute("SELECT source, count(*) FROM tracks GROUP BY source").fetchall()),
        "languages": dict(conn.execute(
            f"SELECT {LANG_SQL} l, count(*) c FROM tracks t WHERE l IS NOT NULL GROUP BY l ORDER BY c DESC").fetchall()),
        "years": dict(zip(("min", "max"), conn.execute(
            "SELECT min(year), max(year) FROM tracks WHERE year >= 1925").fetchone())),
        "total": conn.execute("SELECT count(*) FROM tracks").fetchone()[0],
    }
    out["lyrics"] = conn.execute("SELECT count(*) FROM lyrics WHERE text != ''").fetchone()[0]
    out["heard"] = conn.execute("SELECT count(*) FROM heard").fetchone()[0]
    # The latest weekly refresh that brought anything, if it was in the last eight days.
    fresh = conn.execute("SELECT ran_at, first_id, added FROM refreshes WHERE added > 0 AND ran_at > ?"
                         " ORDER BY ran_at DESC LIMIT 1", (time.time() - 8 * 86400,)).fetchone()
    out["fresh"] = dict(fresh) if fresh else None
    out["analyzed"] = conn.execute("SELECT count(*) FROM analysis WHERE error IS NULL").fetchone()[0]
    out["genres"] = dict(conn.execute(
        "SELECT genre, count(*) c FROM analysis WHERE genre IS NOT NULL GROUP BY genre ORDER BY c DESC").fetchall())
    out["moods"] = dict(conn.execute(
        "SELECT mood, count(*) c FROM analysis WHERE mood IS NOT NULL GROUP BY mood ORDER BY c DESC").fetchall())
    out["keys"] = [r[0] for r in conn.execute(
        "SELECT DISTINCT musical_key FROM analysis WHERE musical_key IS NOT NULL ORDER BY musical_key")]
    out["vocal"] = dict(conn.execute(
        f"SELECT CASE WHEN {VOCAL_SQL} THEN 'vocal' ELSE 'instrumental' END, count(*) "
        "FROM analysis a WHERE a.vocal_prob IS NOT NULL GROUP BY 1").fetchall())
    return out


@app.post("/api/heard")
def mark_heard(ids: list[int] = Body(..., embed=True)):
    """Record tracks the listener has heard (the browser keeps its own copy; this lets searches leave them out)."""
    with sqlite3.connect(DB, timeout=30) as conn:
        conn.executemany("INSERT OR IGNORE INTO heard (track_id, at) VALUES (?, ?)",
                         [(i, time.time()) for i in ids[:100000]])
    return {"ok": True}


@app.get("/api/track/{track_id}")
def track(track_id: int):
    conn = db()
    r = conn.execute(SELECT + " WHERE t.id = ?", (track_id,)).fetchone()
    if not r:
        raise HTTPException(404)
    d = row_out(r)
    tags = conn.execute("SELECT tags FROM analysis WHERE track_id = ?", (track_id,)).fetchone()
    d["tags"] = json.loads(tags[0]) if tags and tags[0] else None
    lyr = conn.execute("SELECT text FROM lyrics WHERE track_id = ?", (track_id,)).fetchone()
    d["lyrics"] = lyr[0] if lyr and lyr[0] else None
    # Simple "similar" until embeddings exist: same genre & mood, nearest tempo.
    if d.get("genre") and d.get("bpm"):
        sim = conn.execute(SELECT + """ WHERE a.genre = ? AND a.mood = ? AND t.id != ?
            ORDER BY abs(a.bpm - ?) LIMIT 8""", (d["genre"], d["mood"], track_id, d["bpm"])).fetchall()
        d["similar"] = [row_out(s) for s in sim]
    return d


@app.get("/api/stream/{track_id}")
def stream(track_id: int, request: Request):
    """Relay a track's audio (with Range) for hosts that refuse hotlinked requests."""
    r = db().execute("SELECT url FROM tracks WHERE id = ?", (track_id,)).fetchone()
    if not r:
        raise HTTPException(404)
    headers = request_headers(r["url"])
    if rng := request.headers.get("range"):
        headers["Range"] = rng
    try:
        up = urllib.request.urlopen(urllib.request.Request(r["url"], headers=headers), timeout=30)
    except urllib.error.HTTPError as e:
        raise HTTPException(e.code) from e
    keep = {k: v for k, v in up.headers.items()
            if k.lower() in ("content-type", "content-length", "content-range", "accept-ranges")}

    def body():
        with up:
            while chunk := up.read(64 * 1024):
                yield chunk
    return StreamingResponse(body(), status_code=up.status, headers=keep)


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")
