"""Place every analyzed track on the mood map (table mood_map).

x runs calm -> energetic: the mood scores' arousal, blended with tempo and loudness.
y runs sad -> happy: the mood scores' valence. Both are converted to percentiles,
so the library spreads evenly across the map instead of piling up in the middle.
Rebuilt from scratch each run; analyze.py runs it when it finishes.

Usage: .venv/bin/python -I scripts/build_map.py
"""

import json
import sqlite3
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema import SCHEMA  # noqa: E402

DB = Path(__file__).resolve().parent.parent / "data" / "music.db"
VALENCE = {"Happy": 1.0, "Funny": 0.8, "Tender": 0.4, "Exciting": 0.3, "Sad": -1.0, "Angry": -0.8, "Scary": -0.8}
AROUSAL = {"Exciting": 1.0, "Angry": 1.0, "Scary": 0.5, "Happy": 0.3, "Funny": 0.2, "Tender": -1.0, "Sad": -0.6}


def rank(v):
    """Percentile of each value, 0..1. Tied values share their average percentile, so a block of
    identical scores (say, every track with no mood signal) lands in one spot instead of a stripe."""
    order = np.argsort(v, kind="stable")
    ranks = np.empty(len(v))
    ranks[order] = np.arange(len(v))
    _, inverse, counts = np.unique(v, return_inverse=True, return_counts=True)
    mean = np.bincount(inverse, weights=ranks) / counts
    return mean[inverse] / max(1, len(v) - 1)


def build(conn):
    conn.executescript(SCHEMA)
    rows = conn.execute("SELECT track_id, tags, bpm, loudness_db FROM analysis "
                        "WHERE error IS NULL AND tags IS NOT NULL").fetchall()
    ids, val, aro, bpm, loud = [], [], [], [], []
    for tid, tags, b, l in rows:
        moods = json.loads(tags).get("moods") or {}
        total = sum(moods.values()) or 1
        share = {m: v / total for m, v in moods.items()}
        ids.append(tid)
        val.append(sum(VALENCE.get(m, 0) * s for m, s in share.items()))
        aro.append(sum(AROUSAL.get(m, 0) * s for m, s in share.items()))
        bpm.append(b or 0)
        loud.append(l if l is not None and l > -60 else -60)   # silence reads as -180 dB
    energy = 0.55 * rank(np.array(aro)) + 0.2 * rank(np.array(bpm)) + 0.25 * rank(np.array(loud))
    # a little scatter so tracks with identical scores read as a cloud, not a single dot
    jitter = np.random.default_rng(0).normal(0, 0.012, (2, len(ids)))
    x, y = (np.clip(rank(v) + j, 0, 1) for v, j in ((energy, jitter[0]), (np.array(val), jitter[1])))
    conn.execute("DELETE FROM mood_map")
    conn.executemany("INSERT INTO mood_map VALUES (?, ?, ?)",
                     zip(ids, (round(float(v), 4) for v in x), (round(float(v), 4) for v in y)))
    conn.commit()
    return len(ids)


if __name__ == "__main__":
    print(build(sqlite3.connect(DB)), "tracks placed")
