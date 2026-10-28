"""Estimate how many legally free music tracks the Internet Archive holds.

Step 1: list every item in each source collection (item-level metadata).
Step 2: fetch the file list for a random sample of items to learn tracks/item.
Step 3: extrapolate track counts, split by language tag.

Usage: python3 -I scripts/count_ia.py [--sample N] [--refresh]
"""

import argparse
import json
import math
import random
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
UA = {"User-Agent": "canopy-census/0.1 (research count)"}

# Openly licensed sources only. Pre-1925 78rpm material is excluded by request.
SOURCES = {
    "jamendo": "collection:jamendo-albums",
    "fma": "collection:freemusicarchive",
    "ia_cc_music": "collection:audio_music AND licenseurl:*creativecommons*",
    "netlabels_cc": "collection:netlabels AND mediatype:audio AND licenseurl:*creativecommons*",
}
EXCLUDE = " AND NOT collection:georgeblood"
FIELDS = ["identifier", "title", "creator", "year", "date", "language", "licenseurl", "collection"]
AUDIO_FORMATS = re.compile(r"mp3|flac|ogg|vorbis|wave|aiff|m4a|aac|opus", re.I)
MIN_YEAR = 1925


def get_json(url, tries=5, timeout=60):
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return json.load(r)
        except Exception as e:  # network hiccups and IA rate limits
            if attempt == tries - 1:
                raise
            time.sleep(2 ** attempt)
            print(f"  retry {url[:80]}: {e}", file=sys.stderr)


def list_items(name, query):
    """Fetch all items in one request: advancedsearch caps paging at 10k results
    but allows an unpaged request of any size."""
    out = DATA / f"items_{name}.jsonl"
    q = query + EXCLUDE
    total = get_json("https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(
        [("q", q), ("rows", 0), ("output", "json")]))["response"]["numFound"]
    params = [("q", q), ("rows", total + 100), ("output", "json")] + [("fl[]", fl) for fl in FIELDS]
    docs = get_json("https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(params), timeout=900)["response"]["docs"]
    print(f"  {name}: {len(docs)}/{total}", file=sys.stderr)
    with out.open("w") as f:
        for d in docs:
            f.write(json.dumps(d) + "\n")
    return out


def load_items(name):
    path = DATA / f"items_{name}.jsonl"
    return [json.loads(line) for line in path.open()]


def lang_bucket(item):
    langs = item.get("language") or []
    langs = [langs] if isinstance(langs, str) else langs
    langs = {l.strip().lower() for l in langs if l}
    if not langs:
        return "untagged"
    if langs & {"english", "eng", "en", "en-us", "en-gb"}:
        return "english"
    if langs & {"instrumental", "zxx", "none", "no linguistic content"}:
        return "instrumental"
    return "other_language"


def year_ok(item):
    y = item.get("year")
    try:
        return int(str(y)[:4]) >= MIN_YEAR
    except (TypeError, ValueError):
        return True  # unknown year; CC licensing post-dates 2002 anyway


# Public-domain labels on community uploads almost always mark old commercial
# recordings rather than artists releasing their own work. CC0 is kept, except
# for a large bulk upload of 1924-1960 jazz 78s mislabelled as CC0.
OLD_RECORDING_LICENSES = ("publicdomain/mark", "licenses/publicdomain")
MISLABELLED_DUMP = re.compile(r"^JV-\d+-\d{4}-")


def plausibly_licensed(item):
    lic = str(item.get("licenseurl") or "")
    return not (any(m in lic for m in OLD_RECORDING_LICENSES) or MISLABELLED_DUMP.match(item["identifier"]))


def tracks_in_item(identifier):
    """Count original audio files (one per track) in an item."""
    meta = get_json(f"https://archive.org/metadata/{urllib.parse.quote(identifier)}")
    files = meta.get("files", [])
    originals = [f for f in files if f.get("source") == "original" and AUDIO_FORMATS.search(f.get("format", ""))]
    if originals:
        # Some albums upload the same track as FLAC and MP3; count distinct stems.
        return len({re.sub(r"\.[^.]+$", "", f["name"]) for f in originals})
    derived = [f for f in files if AUDIO_FORMATS.search(f.get("format", ""))]
    return len({re.sub(r"\.[^.]+$", "", f["name"]) for f in derived})


def mean_ci(xs):
    n = len(xs)
    m = sum(xs) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1)) if n > 1 else 0
    return m, 1.96 * sd / math.sqrt(n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=200)
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    DATA.mkdir(exist_ok=True)
    random.seed(42)

    seen_ids, report = set(), {}
    for name, query in SOURCES.items():
        if args.refresh or not (DATA / f"items_{name}.jsonl").exists():
            print(f"listing {name}", file=sys.stderr)
            list_items(name, query)
        items = [i for i in load_items(name)
                 if i["identifier"] not in seen_ids and year_ok(i) and plausibly_licensed(i)]
        seen_ids.update(i["identifier"] for i in items)

        sample = random.sample(items, min(args.sample, len(items)))
        counts = []
        for k, it in enumerate(sample):
            try:
                counts.append(tracks_in_item(it["identifier"]))
            except Exception as e:
                print(f"  skip {it['identifier']}: {e}", file=sys.stderr)
            if k % 25 == 0:
                print(f"  sampling {name}: {k}/{len(sample)}", file=sys.stderr)
        m, ci = mean_ci(counts)

        buckets = {}
        for it in items:
            b = lang_bucket(it)
            buckets[b] = buckets.get(b, 0) + 1
        report[name] = {
            "items": len(items),
            "tracks_per_item": round(m, 2),
            "tracks_per_item_ci95": round(ci, 2),
            "sampled": len(counts),
            "empty_items_in_sample": sum(1 for c in counts if c == 0),
            "est_tracks": round(len(items) * m),
            "est_tracks_low": round(len(items) * (m - ci)),
            "est_tracks_high": round(len(items) * (m + ci)),
            "items_by_language": buckets,
        }
        print(json.dumps({name: report[name]}, indent=2))

    (DATA / "census_ia.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
