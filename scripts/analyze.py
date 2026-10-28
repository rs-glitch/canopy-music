"""Tag every track in data/music.db from a 20 s slice of its audio.

Per track: tempo (BPM), musical key, loudness, and AudioSet tagging (PANNs Cnn14)
for vocals, genre and mood. Resumable: tracks already in `analysis` are skipped.

Usage: .venv/bin/python -I scripts/analyze.py [--limit N] [--workers 8]
"""

import argparse
import http.client
import json
import sqlite3
import sys
import time
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import librosa
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_map  # noqa: E402
from mp3chunk import fetch_slice  # noqa: E402
from schema import SCHEMA  # noqa: E402

DB = Path(__file__).resolve().parent.parent / "data" / "music.db"
CLIP_SECONDS = 20.0
PANNS_SR = 32000


VOCAL = ["Singing", "Male singing", "Female singing", "Child singing", "Choir", "Rapping",
         "Vocal music", "A capella", "Chant", "Yodeling"]
# Coarse genre groups built from AudioSet's music-genre classes.
GENRES = {
    "Electronic": ["Electronic music", "House music", "Techno", "Dubstep", "Drum and bass",
                   "Electronica", "Electronic dance music", "Trance music"],
    "Ambient": ["Ambient music", "New-age music"],
    "Rock": ["Rock music", "Heavy metal", "Punk rock", "Grunge", "Progressive rock",
             "Rock and roll", "Psychedelic rock"],
    "Pop": ["Pop music"],
    "Hip hop": ["Hip hop music"],
    "Jazz & Blues": ["Jazz", "Blues", "Swing music"],
    "Classical": ["Classical music", "Opera"],
    "Folk & Country": ["Folk music", "Country", "Bluegrass", "Traditional music"],
    "R&B, Soul & Funk": ["Rhythm and blues", "Soul music", "Funk", "Disco"],
    "Reggae & Ska": ["Reggae", "Ska"],
    "Latin": ["Music of Latin America", "Salsa music", "Flamenco"],
    "World": ["Music of Africa", "Afrobeat", "Middle Eastern music", "Music of Asia",
              "Carnatic music", "Music of Bollywood"],
    "Gospel": ["Gospel music", "Christian music"],
    "Children's": ["Music for children"],
}
MOODS = {"Happy": "Happy music", "Funny": "Funny music", "Sad": "Sad music",
         "Tender": "Tender music", "Exciting": "Exciting music", "Angry": "Angry music",
         "Scary": "Scary music"}

# Krumhansl-Schmuckler key profiles.
MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
NOTES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def estimate_key(y, sr):
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr).mean(axis=1)
    best = (-2.0, None)
    for i in range(12):
        for profile, mode in ((MAJOR, "major"), (MINOR, "minor")):
            r = np.corrcoef(chroma, np.roll(profile, i))[0, 1]
            if r > best[0]:
                best = (r, f"{NOTES[i]} {mode}")
    return best[1], float(best[0])


def signal_features(y, sr):
    y22 = librosa.resample(y, orig_sr=sr, target_sr=22050)
    tempo, _ = librosa.beat.beat_track(y=y22, sr=22050)
    key, key_conf = estimate_key(y22, 22050)
    rms = float(np.sqrt(np.mean(y22 ** 2)) + 1e-9)
    return float(np.atleast_1d(tempo)[0]), key, key_conf, 20 * np.log10(rms)


class Tagger:
    def __init__(self):
        from panns_inference import AudioTagging, labels
        self.model = AudioTagging(checkpoint_path=None, device="cpu")
        self.idx = {name: i for i, name in enumerate(labels)}
        self.labels = labels

    def __call__(self, clips):
        n = int(PANNS_SR * CLIP_SECONDS)
        batch = np.stack([np.pad(c[:n], (0, max(0, n - len(c)))) for c in clips])
        probs, _ = self.model.inference(batch)
        return [self.summarize(p) for p in probs]

    def summarize(self, p):
        ix = self.idx
        genre_scores = {g: max(p[ix[c]] for c in cs) for g, cs in GENRES.items()}
        mood_scores = {m: p[ix[c]] for m, c in MOODS.items()}
        top = np.argsort(p)[::-1][:10]
        return {
            "vocal_prob": float(max(p[ix[c]] for c in VOCAL)),
            "speech_prob": float(p[ix["Speech"]]),
            "genre": max(genre_scores, key=genre_scores.get),
            "mood": max(mood_scores, key=mood_scores.get),
            "tags": json.dumps({
                "genres": {g: round(float(s), 3) for g, s in genre_scores.items()},
                "moods": {m: round(float(s), 3) for m, s in mood_scores.items()},
                "top": {self.labels[i]: round(float(p[i]), 3) for i in top},
            }),
        }


def load(row, tries=3):
    track_id, url, size, duration = row
    for attempt in range(tries):
        try:
            # Short timeout: one stalled download holds up its whole batch.
            y, sr = fetch_slice(url, size, seconds=CLIP_SECONDS, duration=duration, timeout=20)
            if len(y) < sr * 5:
                raise ValueError(f"only {len(y) / sr:.1f}s decoded")
            return track_id, y, sr, None
        except (OSError, http.client.HTTPException) as e:  # dropped/reset/timed-out connections: retry
            if isinstance(e, urllib.error.HTTPError) and e.code < 500 or attempt == tries - 1:
                return track_id, None, None, f"{type(e).__name__}: {e}"[:300]
            time.sleep(2 * (attempt + 1))
        except Exception as e:
            return track_id, None, None, f"{type(e).__name__}: {e}"[:300]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--batch", type=int, default=16)
    args = ap.parse_args()

    db = sqlite3.connect(DB)
    db.executescript(SCHEMA)
    todo = db.execute("""SELECT id, url, size, duration FROM tracks
                         WHERE id NOT IN (SELECT track_id FROM analysis)
                         ORDER BY random()""").fetchall()
    todo = todo[:args.limit] if args.limit else todo
    print(f"{len(todo)} tracks to analyze", file=sys.stderr)
    tagger = Tagger()
    cols = ["track_id", "bpm", "musical_key", "key_confidence", "loudness_db", "vocal_prob",
            "speech_prob", "genre", "mood", "tags", "error", "analyzed_at"]
    insert = f"INSERT OR REPLACE INTO analysis ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})"

    t0, done = time.time(), 0
    with ThreadPoolExecutor(args.workers) as pool:
        for start in range(0, len(todo), args.batch):
            loaded = list(pool.map(load, todo[start:start + args.batch]))
            ok = [r for r in loaded if r[3] is None]
            rows = [{"track_id": tid, "error": err, "analyzed_at": time.time()}
                    for tid, _, _, err in loaded if err]
            if ok:
                clips = [librosa.resample(y, orig_sr=sr, target_sr=PANNS_SR) for _, y, sr, _ in ok]
                for (tid, y, sr, _), tags in zip(ok, tagger(clips)):
                    try:
                        bpm, key, key_conf, loud = signal_features(y, sr)
                        rows.append({"track_id": tid, "bpm": round(bpm, 1), "musical_key": key,
                                     "key_confidence": round(key_conf, 3), "loudness_db": round(loud, 1),
                                     "analyzed_at": time.time(), **tags})
                    except Exception as e:
                        rows.append({"track_id": tid, "error": f"features: {e}"[:300], "analyzed_at": time.time()})
            db.executemany(insert, [[r.get(c) for c in cols] for r in rows])
            db.commit()
            done += len(loaded)
            rate = done / (time.time() - t0)
            print(f"  {done}/{len(todo)}  {rate:.1f} tracks/s  "
                  f"errors so far: {db.execute('SELECT count(*) FROM analysis WHERE error IS NOT NULL').fetchone()[0]}",
                  file=sys.stderr)
    print(f"mood map: {build_map.build(db)} tracks placed", file=sys.stderr)


if __name__ == "__main__":
    main()
