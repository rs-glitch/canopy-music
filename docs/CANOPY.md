# Canopy: the whole story

Canopy is a personal music library of about 95,000 songs that anyone may legally
stream. It is set in a night forest under a real sky. Every song you play becomes
a star.

This document covers what Canopy is, why it looks and behaves the way it does,
how every part was built, and how to rebuild it from nothing. The
[README](../README.md) is the short operating manual; this is the long version.

Canopy is for personal use and learning only. It is not a product, has no
audience and no business model. It hosts no audio: every song streams from the
site the artist put it on.

---

## Contents

1. [What Canopy is](#1-what-canopy-is)
2. [How it came to be](#2-how-it-came-to-be)
3. [The library](#3-the-library)
4. [How the pieces fit](#4-how-the-pieces-fit)
5. [The data pipeline](#5-the-data-pipeline)
6. [Listening to the audio: analysis](#6-listening-to-the-audio-analysis)
7. [The server](#7-the-server)
8. [Designing the world](#8-designing-the-world)
9. [The page, piece by piece](#9-the-page-piece-by-piece)
10. [Every feature: the idea and how it works](#10-every-feature-the-idea-and-how-it-works)
11. [What lives where](#11-what-lives-where)
12. [Rebuilding Canopy from scratch](#12-rebuilding-canopy-from-scratch)
13. [How it was tested](#13-how-it-was-tested)
14. [Known limits and honest caveats](#14-known-limits-and-honest-caveats)
15. [Roads not taken](#15-roads-not-taken)
16. [Ideas waiting](#16-ideas-waiting)
17. [File map](#17-file-map)

---

## 1. What Canopy is

**In one sentence:** Canopy is the site where every song you play becomes a star,
and scrolling lifts you out of the forest to see them.

**What it does**

- **Search and browse** about 95,000 openly licensed songs:
  - search by title, artist or album;
  - filter by vocals, language, genre, mood, tempo, key, year, source and licence;
  - filter to songs you've never heard, or songs with lyrics.
- **Play** songs in a waveform player with shuffle, a DJ crossfade mode,
  "more like this", and endless stations.
- **Explore** a mood map where every song is a dot, placed from calm to energetic
  and from sad to happy. Drag a circle over an area to play what's there.
- **Live under a real sky.** The moon shows tonight's actual phase, and the sky
  colour follows the clock. Shooting stars cross it, and fireflies flash on the
  beat. Your listening is drawn as a constellation with a generated name and myth.
- **Read lyrics** for about 24,000 songs.
- **Grow on its own.** Every Sunday it collects new uploads, analyses them, and
  offers them as a "New this week" station.

**Ground rules set at the start**

- Only legally free music: Creative Commons, public domain, or platforms that
  license third-party streaming.
- Nothing recorded before 1925.
- Instrumentals are included.
- Personal and learning use only, which is why non-commercial licences are fine.

---

## 2. How it came to be

The project began as "a searchable repository of free songs, searchable by song,
year, album and artist, with playback". It went through these stages.

| Stage | What happened |
|---|---|
| **Census** | Before building anything: how much legally free music exists? A script counted the Internet Archive's openly licensed collections and estimated **about 1.29 million tracks from 1925 on**. That figure is after removing mislabelled uploads (see §3). |
| **Honest reality check** | Searching by song name suits music people already know, and almost none of that is free. Canopy became a place to *discover* music, not to look up known songs. It also settled as a personal learning project rather than a product. |
| **Steps 1 and 2** | Built the basics: a 5,000-track sample, full-text search and a waveform player. Then audio analysis (tempo, key, loudness, vocals, genre, mood) exposed as filters. |
| **The redesign** | The site was rebuilt with the scroll-craft design skill as **Canopy**, a calm night forest under deep space (§8). The player became a closable, translucent overlay. |
| **Scale-up** | Grew 5k → 10k → 20k tracks across four Internet Archive sources. Added a shuffle button. |
| **"Everything is super old and/or instrumental"** | Recent free music exists only because artists choose Creative Commons, and most who do make background instrumentals. Canopy switched to opening on **With vocals + Newest**. It then added **ccMixter** (5,000 vocal tracks) and **Jamendo's live API** (all 46,578 English vocal songs). Column headings were added to the list. |
| **A name in the sky** | The name "Canopy" was tried in large cursive (Pinyon Script) across the night sky. After several rounds of size, position and opacity changes, it was removed entirely. The small wordmark in the header stayed. |
| **More sources** | About ten sources were surveyed. **Audius** was added: 10,000 trending tracks, streamed under its Open Music License. |
| **Spanish and languages** | All of Jamendo's ~8,300 Spanish vocal songs were imported, and a language filter was added. |
| **Clean-up** | Fixed titles that arrived HTML-escaped (`Don&amp;#039;t` → `Don't`). Added a button to clear the stars. |
| **Features 1–10** | Real moon, clock sky, shooting stars, song-coloured stars, named constellations, beat fireflies, more like this, DJ mode, stations with endless play, and the mood map. |
| **Features 11–13** | Never heard, the weekly refresh with "New this week", and lyrics. The weekly job was scheduled with launchd and needed Full Disk Access for Python (§12). |

---

## 3. The library

### What's in it

| Source | Key | Tracks | Licence | How it streams |
|---|---|---|---|---|
| Jamendo, live API | `jamendo_api` | 54,856 | Creative Commons (mostly NC) | `prod-1.storage.jamendo.com`, direct |
| Audius | `audius` | 14,391 | Audius Open Music License (stream only); a few CC | Audius API stream URL (redirects) |
| Free Music Archive (IA mirror) | `fma` | 5,144 | usually unrecorded ("Unknown") | archive.org, direct |
| Netlabels (IA) | `netlabels_cc` | 5,105 | Creative Commons | archive.org, direct |
| Jamendo (older IA mirror) | `jamendo` | 5,061 | Creative Commons | archive.org, direct |
| IA community CC uploads | `ia_cc_music` | 5,026 | uploader-asserted CC | archive.org, direct |
| ccMixter | `ccmixter` | 5,006 | Creative Commons | **relayed** through Canopy's server, because ccMixter refuses hotlinks |
| **Total** | | **94,589** | | |

These counts are from 28 October 2026. The weekly refresh changes them.

**Coverage as of that date**

- **Vocals:** 46,229 songs are classed as vocal and 47,888 as instrumental. 472
  couldn't be analysed.
- **Language:** 47,488 English and 8,265 Spanish. Language tags come from Jamendo
  and from Internet Archive metadata. Most other tracks have none.
- **Lyrics:** 23,946 songs have them.
- **Mood map:** 94,117 songs are placed on it.
- **Database size:** `data/music.db` is about 150 MB.

### The census (`scripts/count_ia.py`)

- **Method:** list every item in four Internet Archive collections, open the file
  lists of 200 random items per collection to count tracks per item, then scale up
  with a 95% confidence interval. The results are in `data/census_ia.json`.
- **Year filter:** items dated before 1925 are dropped. Undated items are kept,
  since Creative Commons licensing post-dates 2002 anyway.
- **Mislabelled uploads, the big find:** 41% of the community collection was
  mislabelled. One bulk upload of 39,513 commercial jazz 78s from 1924–1960
  (identifiers `JV-…`) was marked CC0. `plausibly_licensed()` drops that upload
  and the "Public Domain Mark" items, which almost always label old commercial
  recordings.
- **Corrected estimate:** about 1.29M tracks (95% range 1.0M–1.57M):

  | Collection | Estimated tracks |
  |---|---|
  | Jamendo mirror | ~669k |
  | Netlabels | ~374k |
  | Community uploads | ~147k |
  | Free Music Archive | ~95k |

- **Deliberately excluded:** 78rpm records from 1926 on. Labels sued the Internet
  Archive over them, and they only began entering the US public domain in 2026.

### Why each source is legal

- **Creative Commons** (Jamendo, ccMixter, netlabels, community uploads): artists
  chose to share. Non-commercial (NC) licences are fine for personal listening.
  Canopy's "Commercial use allowed" filter shows only CC licences without NC.
- **Audius:** uploaders agree to the
  [Open Music License](https://audius.org/open-music-license.pdf). It licenses
  music-player apps to stream their tracks through the official API, and the
  uploader warrants they hold the rights.
  - Most Audius tracks are otherwise all rights reserved: listen, don't reuse.
  - The importer skips covers, DJ mixes, bootlegs, mashups, leaks, gated or
    unlisted tracks, and non-music genres. Unlabelled covers can still slip through.
- **Canopy never stores audio.** It keeps an index and streams from the source.
  A removed upload simply stops playing.

---

## 4. How the pieces fit

```
  Internet Archive ─┐                            ┌─> lyrics      (fetch_lyrics.py)
  ccMixter API ─────┤  ingest_*.py ─> tracks ────┼─> analysis    (analyze.py: librosa + PANNs)
  Jamendo API ──────┤  (refresh.py weekly)       │      └─> mood_map (build_map.py)
  Audius API ───────┘                            └─> tracks_fts  (SQLite FTS5)

                        data/music.db (SQLite)
                                 │
                 app/server.py (FastAPI, read-only except /api/heard)
                                 │  /api/search /api/map /api/facets /api/track /api/stream /api/heard
                                 ▼
                 app/static/index.html (one file: HTML + CSS + JS module)
                     WaveSurfer 7 · Web Audio · canvas · SVG · localStorage
```

**Stack**

- **Back end:** Python 3.12, SQLite with FTS5, FastAPI and uvicorn.
- **Analysis:** librosa, soundfile, numpy, PyTorch and `panns-inference`.
- **Front end:** one hand-written HTML file. No framework and no build step. Its
  only outside dependencies are WaveSurfer.js 7 (loaded from unpkg) and two
  Google Fonts.

---

## 5. The data pipeline

Every script is resumable and safe to rerun: inserts use `INSERT OR IGNORE`, and
analysis skips tracks it has already done. Run the importers with the system
`python3 -I`, since they need only the standard library. Run anything that needs
numpy or PyTorch with `.venv/bin/python -I`.

### Schema (`scripts/schema.py`)

| Table | Holds |
|---|---|
| `tracks` | One row per playable file: `source`, `item_id`, `file_name` (unique together), `title`, `artist`, `album`, `year`, `track_no`, `duration`, `size`, `language`, `license_url`, `license`, `genre_tag` (uploader's own tags), `url` |
| `tracks_fts` | An FTS5 index over title, artist and album, with `remove_diacritics 2` so "cancion" finds "canción". Rebuilt after every import |
| `analysis` | Per track: `bpm`, `musical_key`, `key_confidence`, `loudness_db`, `vocal_prob`, `speech_prob`, `genre`, `mood`, `tags` (JSON with the full score breakdown), `error`, `analyzed_at` |
| `mood_map` | `x` (calm → energetic) and `y` (sad → happy), both 0–1 |
| `lyrics` | `text`. An empty string means "checked, none found", so a track isn't asked about twice |
| `heard` | Track ids the listener has played for 20 s or more, mirrored from the browser |
| `refreshes` | One row per weekly run: `ran_at`, `first_id` (every track with id ≥ this arrived in it), `added`, `by_source` |

### Internet Archive (`count_ia.py`, then `ingest.py`)

- **Listing:** `count_ia.py` lists items through the scrape API and writes
  `data/items_<source>.jsonl`.
- **Sampling:** `ingest.py` samples items until it reaches
  `--tracks-per-source` (default 1,250; Canopy used 5,000). For each item it
  fetches `archive.org/metadata/<id>` and writes one row per MP3.
- **Skipped:**
  - bulk dumps, matched by title words such as "collection", "discography",
    "backup" or "podcast";
  - items that fail `plausibly_licensed()`;
  - anything before 1925.
- **Stored details:** year comes from item metadata, and licence labels such as
  "CC BY-NC-SA 3.0" are read from the licence URL.

### ccMixter (`ingest_ccmixter.py`)

- **Query:** `ccmixter.org/api/query`, newest first, for the tags
  `female_vocals`, `male_vocals` and `vocals`, minus `acappella`. Bare vocal stems
  are raw material for remixes, not songs.
- **Two quirks handled:**
  - The API echoes a huge header that breaks Python's 64 KB header-line limit,
    hence `http.client._MAXLINE`.
  - A few uploads contain cp1252 bytes, so the response is decoded with `replace`.
- **Playback:** ccMixter refuses audio requests without its own `Referer`, so
  `/api/stream/{id}` relays them with Range support. It relays only URLs already
  in the database.

### Jamendo (`ingest_jamendo.py`)

- **Query:** `api.jamendo.com/v3.0/tracks` with `vocalinstrumental=vocal`, a
  `lang` and `order=releasedate_desc`, 200 per page (the maximum).
- **Client ID:** free, from devportal.jamendo.com. It goes in `.jamendo_client_id`
  (git-ignored) or `JAMENDO_CLIENT_ID`. Only the Client ID is needed; never the
  secret.
- **Stream URL:** the stable form `prod-1.storage.jamendo.com/?trackid=…&format=mp32`,
  without the session token the API adds.
- **API quirks:**
  - It sometimes returns an empty page, so those are retried.
  - It takes at most 50 ids per multi-id request.
- **Clean text:** `clean()` unescapes HTML entities until stable, because some
  titles arrive escaped twice.
- **The `--tracks` gotcha:** `--tracks` is the target total of *all*
  `jamendo_api` rows, not of the language being imported. The Spanish import was
  therefore run as `--lang es --tracks 56000`.
- **Length limits:** tracks shorter than 30 s or longer than 20 minutes are
  skipped.

### Audius (`ingest_audius.py`)

- **Charts:** the trending chart only pages about 300 deep. The importer walks
  every music genre across three time windows (week, month, all time) plus the
  underground chart.
- **Requests:** it sends `app_name=canopy-learning`, as Audius asks, and a custom
  User-Agent, because Cloudflare refuses Python's default.
- **Filter:** `acceptable()` keeps only streamable, ungated, listed tracks from
  30 s to 20 min, outside the non-music genres. It rejects titles matching
  bootleg, mashup, leak, unreleased, snippet, DJ mix, live set or cover, and
  anything with a cover-original-artist field.
- **Licence:** CC tracks keep their CC licence. Everything else is labelled
  "Audius Open Music License (stream only)".

### Lyrics (`fetch_lyrics.py`)

- **Jamendo:** its API has a `lyrics` field that artists fill in.
  - Live-API tracks use their track id.
  - Tracks from the older archive.org copy carry the Jamendo id inside the file
    name (`01-1899563-Album-Title.mp3`).
  - Fetched in batches of 50 (the API's limit), 4 requests at a time.
- **ccMixter:** has no lyrics field, but some artists paste lyrics into the
  description under a heading ("Lyrics", "LYRICS:", "Rêves et Perspectives
  Lyrics").
  - The heading is found with a regex.
  - The text after it counts as lyrics only if it has 4 or more lines averaging
    under 80 characters, so prose that merely mentions lyrics is ignored.
- **Tidying:** line endings are normalised and long runs of blank lines collapsed.
  Some artists leave a blank line after every line; that's detected (blank-line
  breaks outnumber single breaks more than two to one) and single-spaced, keeping
  a gap before `[Verse]`/`[Chorus]` labels.
- **Errors:** a failed batch is skipped and retried on the next run.
- **Not covered:** Audius and the other archive collections provide no lyrics.

### The weekly refresh (`refresh.py`)

1. **Jamendo** (English and Spanish) and **ccMixter**: newest first, stopping at
   the first page that adds nothing new. There's a 40-page backstop.
2. **Audius:** this week's trending chart for every genre, plus underground.
3. **Log:** a `refreshes` row is written and the FTS index rebuilt.
4. **Follow-up:** if anything arrived, it runs `fetch_lyrics.main()` and then
   `analyze.py`, which rebuilds the mood map at the end.

- **Failures:** one source failing is logged and doesn't stop the others.
- **Schedule:** `scripts/canopy.refresh.plist` runs it from launchd on Sundays
  at 04:00 under `caffeinate -i`, with low I/O priority and `nice 5`. A missed
  run happens on the next wake. The log is `~/Library/Logs/canopy-refresh.log`.
- **First runs:** the first added 3,634 tracks and the second 777. Audius
  dominates while its weekly charts keep turning up tracks the capped first import
  missed.

---

## 6. Listening to the audio: analysis

`scripts/analyze.py` tags every track from a **20-second slice**. It never
downloads whole files.

### Getting the slice (`mp3chunk.py`)

- **Range request:** it asks for about 0.5 MB starting 35% of the way into the
  file. For sources that don't record the file size, it first asks the server for
  it.
- **Finding a frame:** a slice cut from the middle of an MP3 starts mid-frame.
  `mp3chunk` scans for a valid MPEG Layer III frame header, checking sync bits,
  bitrate and sample-rate tables, and that the next frame follows where the frame
  length says it should. It decodes from there with soundfile.
- **Result:** about 0.5 MB of transfer per track instead of 5–10 MB.

### What's measured

- **Tempo:** `librosa.beat.beat_track` at 22.05 kHz. Expect occasional half- or
  double-time readings.
- **Key:** mean CQT chroma correlated against the Krumhansl–Schmuckler major
  and minor profiles in all 12 rotations. The best match wins and its correlation
  is stored as `key_confidence`.
- **Loudness:** RMS in dB.
- **Vocals, genre and mood:**
  [PANNs](https://github.com/qiuqiangkong/audioset_tagging_cnn) Cnn14, an AudioSet
  tagger with 527 classes, run at 32 kHz in batches of 16.
  - **Vocals:** the maximum over the singing, rapping, choir, a cappella, chant
    and yodelling classes.
  - **Genre:** AudioSet's music-genre classes, pooled into 14 coarse groups
    (Electronic, Rock, Ambient, Pop, Hip hop, Jazz & Blues, and so on).
  - **Mood:** the highest of AudioSet's 7 mood classes: Happy, Funny, Sad, Tender,
    Exciting, Angry, Scary.
  - **Saved scores:** the full breakdown is stored in `tags` and drawn as bars in
    the details panel.

### The vocal rule

- **The problem:** PANNs under-scores sung vocals in full mixes, and hears dense
  rock or rap vocals as "Speech".
- **The rule:** after studying the score distribution, a track counts as vocal
  when `vocal_prob ≥ 0.10` or `speech_prob ≥ 0.15`.
- **Effect:** the first strict cutoff called about 4% of tracks vocal. This rule
  calls about a third of the archive tracks vocal, and roughly 80% of hip hop and
  pop. It's calibrated by eye, not against labelled data.

### Running it

- **Workers:** eight threads fetch slices while the model tags them in batches.
- **Speed:** about 1.5–1.9 tracks/s on the CPU, or 0.7 when the machine is busy.
- **Failures:** about 0.5%. Causes include archive.org server errors, slices with
  no MP3 frame, access-restricted items and very short files. Failures are stored
  in `error`; those tracks play but have no tags.
- **Long runs:** keep the Mac awake with `caffeinate -i` and on mains power.
  Locking the screen doesn't stop it; sleep does.
- **The model file:** `Cnn14_mAP=0.431.pth`, about 330 MB, lives in
  `~/panns_data`, where `panns_inference` looks for it. Its MD5 is
  `541141fa2ee191a88f24a3219fff024e`, from
  [Zenodo record 3987831](https://zenodo.org/records/3987831). Downloading from
  Zenodo took seconds; the library's default download had been crawling.

### The mood map (`build_map.py`)

Every analysed track gets a position:

- **x (energy)** = 0.55 × arousal + 0.20 × tempo + 0.25 × loudness. Each part is a
  percentile rank, and arousal is a weighted sum of the mood scores.
- **y (valence)** = the percentile rank of a weighted sum of the mood scores:
  happy and funny pull up, sad and angry pull down.

Two problems were fixed along the way:

- **Stripes from ties:** many tracks share scores, and plain ranking produced
  stripes. Tied values get their average rank, plus a little gaussian jitter
  (σ = 0.012).
- **Outliers:** loudness below −60 dB is clamped so silence doesn't stretch the
  axis.

The result is sensible: Angry lands at (0.83, 0.12), Happy at (0.36, 0.86),
Sad at (0.16, 0.17) and Tender at (0.17, 0.44).

---

## 7. The server

`app/server.py`, run with `.venv/bin/uvicorn app.server:app --port 8765`.

- **Connections:** the database is opened read-only per request. The only write
  is `POST /api/heard`.
- **Compression:** responses over 2 KB are gzipped. That matters for the map,
  about 324 KB gzipped for every track.
- **Schema:** it runs `SCHEMA` on startup so new tables exist before the pipeline
  reaches them.

| Endpoint | Does |
|---|---|
| `GET /api/search` | Filters (below), plus `sort` (relevance, newest, oldest, bpm, title, random), `limit` ≤ 200 and `offset`. Returns `{total, results}` |
| `GET /api/map` | The same filters. Returns `{moods, x[], y[], m[]}`: coordinates in thousandths and a mood index, kept compact |
| `GET /api/facets` | Counts for every filter, plus total, analysed, lyrics, heard, and `fresh` (the latest refresh from the last 8 days that added anything) |
| `GET /api/track/{id}` | Everything about one track, including its score breakdown, lyrics and 8 similar tracks |
| `GET /api/stream/{id}` | Relays audio, with Range, for hosts that refuse hotlinks |
| `POST /api/heard` | `{ids: [...]}`, added to the heard table |

**Filters**, shared by search and the map through FastAPI's `Depends`:

- **Text:** `q` (FTS prefix match: "blue sk" becomes `"blue"* "sk"*`).
- **Lists:** `genre`, `mood`, `source` and `language` can each be repeated.
- **Simple values:** `vocals` (vocal or instrumental), `bpm_min/max`, `key`,
  `year_min/max`, `commercial`.
- **Discovery:** `unheard`, `lyrics`, and `since_id`.
- **More like this:** `like`. Keeps tracks with tempo within ±8%, the same vocal
  class, and the same mood or genre. It orders them by
  `mood match + genre match + 0.8 × key compatible − tempo distance`, then randomly.
- **Mood map area:** `map_x`, `map_y`, `map_r`, `map_ry`. The selection is an
  ellipse, because the map is wider than it is tall, so a circle on screen covers
  a taller range in map units.

**Harmonic compatibility** (`compatible_keys`) counts a key as blending with:
itself, its neighbours a fifth up and down, and its relative major or minor. This
is the Camelot-wheel rule DJs use. The page has the same logic in JavaScript for
DJ mode.

**Language** is normalised in SQL: Internet Archive metadata says `english` or
`untagged`, while Jamendo uses ISO codes.

**Every result** also gets these computed fields:

- `vocals` (true, false or null);
- `has_lyrics`;
- `source_page` (the jamendo.com, ccmixter.org, audius.co or archive.org page);
- `commercial_ok`: true only for CC licences without NC, never for the Audius
  licence.

---

## 8. Designing the world

The look came from one request: *"redesign the website. make it calm and
relaxing, think outer space, calm forest, etc. use your judgement for the vibe."*
It was designed with the **scroll-craft** skill. The brief, feeling curve and
full brief is in [docs/design/BRIEF.md](design/BRIEF.md).

### The brief, condensed

- **Vibe:** night forest under deep space. Still, cool, quiet, with one warm
  light. The references were the last blue of dusk over a pine ridge, a long
  exposure of the Milky Way from a forest clearing, and fireflies at the edge of a
  meadow.
- **Structure:** "Live surface". The page *is* the tool, with no marketing
  headline. App chrome is the navigation, and the opening screen is the tool
  already in use, with search ready and results listed.
- **One world, not scenes:** the forest and sky are fixed behind the tool. The
  tool scrolls, and the world responds with *altitude* instead of cutting between
  scenes.
- **Energy:** low throughout. The only rise is lifting above the treeline, and
  even that is slow.

**Feeling curve**

| Stage | Feeling | What causes it |
|---|---|---|
| 1 | Stillness | Dusk at the treeline, fireflies, the search field waiting on the horizon |
| 2 | Curiosity | Results listed, mood chips glowing faintly, the sky deepening as you browse |
| 3 | Absorption | A track plays, the stars breathe with its low end, the waveform is amber |
| 4 | Awe (the peak) | The list has carried you above the trees, the Milky Way opens, and your stars are joined |
| 5 | Belonging | An input asks you to name tonight's constellation, and keeps the name |

**The signature move:** every track played for 20 seconds becomes a star, joined
to the last, so each session leaves a constellation behind.

### Drawn entirely in code

- **Why code:** there was no image-generation key and no ffmpeg on the machine,
  and a night sky drawn as points of light and silhouettes is honest about being
  drawn.
- **What it costs:** nothing. No images, video or paid assets.
- **How it's layered:** each plane is real, with transparency, and moves at its
  own speed as you climb:

| Plane | Rendering | Moves with altitude |
|---|---|---|
| Sky gradient | CSS, regraded by `--alt` and the hour palette | colour only |
| Milky Way and far stars | canvas, painted once into a texture 1.2× the viewport tall | 6% |
| Twinkling bright stars | canvas, every frame | with the texture |
| Your constellation | DOM buttons with SVG lines | 10% |
| Moon | SVG disc | 14% |
| Mountain ridge | SVG path from summed sines | 90% |
| Far pines | SVG, 70 generated trees | 102% |
| Mist | gradient band, slow drift | 108% |
| Near pines | SVG, 26 larger trees | 120% |
| Fireflies | canvas | 120% |
| The tool (header, list, player) | HTML, translucent panels | scrolls normally |

**How the scene is drawn**

- **Pines:** generated by a seeded random function (`seeded(11)` and
  `seeded(29)`), so the forest is the same on every visit. Each tree is 4–6 notched
  tiers drawn as one path.
- **Ground:** each silhouette continues as solid ground below its horizon, so
  climbing never shows a gap.
- **Horizon:** sits at 46% of the screen height, 40% on phones.
- **Altitude:** scroll position from 0 to 1, eased towards its target each frame.
  It moves the layers and regrades the sky from dusk teal to deep space.
- **Reduced motion:** with `prefers-reduced-motion` on, the scene holds one calm
  composition (altitude 0.35), and twinkling, drifting and breathing stop.

### Palette and type

- **Colours:**

  | Role | Colour |
  |---|---|
  | Canvas | `#08121a` |
  | Ink | `#e7ece4` |
  | Soft ink | `#9fb3aa` |
  | Faint ink | `#6f857d` |
  | Accent (firefly amber) | `#f0c36a` |
  | Accent ink | `#1b1406` |

  Panels are `rgba(12, 25, 31, 0.74)` with a light frosted blur.
- **Fonts:** **Outfit** for display text (the wordmark, details-panel titles) and
  **Geist** for everything else. Numbers use tabular figures so columns line up.
- **Hour palettes:** the sky's three colour tokens change with the hour:

  | Sky | `--dusk` | `--low` | `--space` |
  |---|---|---|---|
  | Night | `#133540` | `#08192a` | `#02060c` |
  | Dawn | `#86aeb8` | `#36627a` | `#13263d` |
  | Day | `#5f8f9e` | `#2c5a73` | `#17324d` |

  The first day and dawn palettes were too subtle and were brightened.
- **Motion:** one easing curve, `cubic-bezier(0.23, 1, 0.32, 1)`, for everything
  that slides.

### Design decisions that were reversed

- **The cursive name in the sky:** tried in Pinyon Script beside the moon, then
  full width behind the list, then back beside the moon (smaller and lighter),
  then removed. The panel blur was lightened from 14 px to 2.5 px so the script
  could show through, and it stayed light after the script was removed.

---

## 9. The page, piece by piece

From top to bottom:

1. **Header:** the Canopy wordmark (an amber dot and "Canopy" in Outfit), the
   search field, library stats ("94,589 tracks · 94,117 listened to"), and a
   "★ N in your sky" counter that jumps to the clearing.
2. **Tonight:** a line written from real data, e.g. *"94,589 openly licensed
   tracks under a full moon. Late now. Tender songs suit the hour."*
   - Below it, the quick mood chips, with the hour's suggested mood first and
     marked with a gold dot.
   - Below those, the **Stations** row.
3. **Filters panel (left):** Vocals, Language, Discover (Never heard, With
   lyrics), Genre, Mood, Tempo, Key, Year, Source, License, and "Clear filters".
   - Every chip shows its count.
   - On a phone the panel collapses to a "Filters" summary.
4. **Results (centre):**
   - **Toolbar:** the count, active pills such as "More like “X” ×", "Patch of the
     mood map ×" and "Added this week ×", the **Mood map** button, and the sort
     menu.
   - **Columns:** `# · Title · Artist · Album · Year · Length · Vocals · Genre ·
     Mood`. A phone shows only #, Title · Artist and Length.
   - **Rows:** each has tags (vocals, genre, mood, key, lyrics, bpm) and an ⓘ
     button for details.
5. **The clearing (bottom):** open sky with your stars.
   - The constellation's generated name and myth.
   - A name field, **Keep it**, **Clear stars** (tap twice to confirm), and **Save
     as image**.
   - Kept constellations are listed below and can be viewed again.
6. **Details panel (right):** a frosted panel with these sections:
   - title and artist;
   - tags;
   - source and licence links;
   - lyrics, with "Show all";
   - genre, mood and "sounds heard" score bars;
   - ready-to-paste credit text with **Copy credit**;
   - **More like this**;
   - 8 similar tracks.
7. **Player (floating, translucent):** title and artist (tap to open details and
   lyrics), previous, play/pause, next, more like this, DJ, shuffle, the
   waveform, time, and × to close.
   - Closing stops playback and slides the player away.
   - On a phone it's three rows: title and ×, then controls, then the waveform.
     With six buttons, one row had squeezed the title to a few letters.
8. **Mood map (dialog):** a canvas with axis labels (Happy, Sad, Calm, Energetic)
   and mood names at their centres. Drag to draw a circle; Esc, × or clicking the
   backdrop closes it.

**Keyboard**

| Key | Does |
|---|---|
| Space | play / pause |
| ← / → | previous / next |
| S | shuffle |
| D | DJ mode |
| L | more like the current song |
| Esc | close the map, then details, then the player |

Shortcuts are ignored while typing in a field.

**Accessibility**

- **Labels:** every icon button has an `aria-label` and a tooltip.
- **Focus:** shown with an amber outline.
- **Motion:** reduced motion is respected throughout.
- **Phones:** layouts were checked at 390 px wide, with 16 px side gutters and no
  sideways scrolling.

---

## 10. Every feature: the idea and how it works

### Search, filters and opening view

- **Search:** FTS5 prefix search, debounced by 200 ms.
- **Chips:** any combination works. The quick moods and the sidebar moods are the
  same filter, kept in sync.
- **Opening view:** **With vocals + Newest**, so recent songs come first. This was
  the answer to "everything is super old and/or instrumental". Your own changes to
  vocals or sort are remembered.
- **Newest:** sorts by year, then by id descending. The later-added live sources
  therefore beat this year's archival uploads, whose "year" is the upload year.
- **Late responses:** only the latest search may draw. A slower earlier response
  is dropped, which fixed a bug where a station's list could be overwritten by the
  opening list.

### Waveform player and shuffle

- **Waveform:** WaveSurfer 7 draws an amber waveform you can click to seek.
- **Shuffle** (S):
  - plays a random order through the current results with no repeats until all
    have played;
  - "previous" retraces what actually played, by track id, so it survives a new
    search;
  - the setting is remembered.

### 1. The real moon

- **Idea:** the moon in the sky should be tonight's moon.
- **Phase:** computed from a known new moon (6 January 2000, 18:14 UTC) and the
  synodic month (29.530588853 days).
- **Drawing:** the lit shape is an SVG path made of two arcs, the outer limb and
  the terminator, used as a clip over a gradient disc. There are a few craters and
  a faint earthshine on the dark side.
- **Glow:** brightness follows how much of the moon is lit (`--illum`).
- **Words:** phase names include "moon" ("waxing crescent moon"), so the tonight
  line reads naturally.
- **Full moon mix:** on a full moon (over 97% lit) the page opens once per night on
  the Full moon mix: tender and eerie vocal songs, shuffled.

### 2. The sky follows the clock

- **Idea:** the place should know what time it is.
- **Hours:** each band has its own sky, suggested mood and line under the sky:

  | Hours | Sky | Suggested mood |
  |---|---|---|
  | 21:00–05:00 | night | Tender |
  | 05:00–08:00 | dawn | Happy |
  | 08:00–17:00 | day | Happy |
  | 17:00–21:00 | dusk | Exciting |

- **Starlight:** stars dim in daylight (night 1, dusk 0.9, dawn 0.5, day 0.3).
- **Updates:** checked every minute.

### 3. Shooting stars

- **Idea:** a small surprise that rewards looking up.
- **Timing:** the first meteor comes 12–32 s after load, then every 25–70 s. It
  streaks across the upper sky on the canvas.
- **Catching one:** where it lands, a glowing ember (a real button) waits for 9 s.
  Catch it to play a song you've never heard. It asks the server for random
  `unheard` songs, honouring your vocals filter.

### 4. Song stars

- **Idea:** stars should say something about the songs.
- **Colour:** the song's mood. Gold is happy, orange exciting, pale yellow funny,
  rose tender, blue sad, violet scary, red angry.
- **Size:** 4 px plus up to 6 px for listening time (one more pixel per 45 s).
- **Glow:** brightens with each replay. Replaying says "Brighter in your sky".
- **Bookkeeping:** listening time counts only real playback steps, not seeks, and
  is saved every 10 s.
- **Position:** a hash of the track id, so a song always lands in the same place
  in the sky.

### 5. Named constellations

- **Idea:** each night's constellation becomes a little myth.
- **The name:** an adjective from the dominant mood (Sleeping, Weeping, Laughing,
  Running, Dancing, Hollow, Burning) plus a noun from the dominant genre (Stag,
  Lantern, Drummer, Wanderer, Mist, Lark…), as in "The Sleeping Lantern".
- **The myth:** *"8 songs, mostly tender electronic, all sung in Spanish. Drawn on
  October 26 under a full moon."*
- **Keeping it:** **Keep it** uses the generated name unless you type one.
- **Save as image:** renders the sky and constellation to a canvas at screen size
  × pixel density and downloads a PNG, which suits a wallpaper.

### 6. Fireflies on the beat

- **Idea:** the forest should feel the music.
- **How:** while a song with a known tempo plays, beat = current time × bpm ÷ 60.
  The fireflies are split into four groups that take turns flashing, one per beat,
  each flash fading as e^(−3.2t).
- **Breathing:** separately, the stars "breathe" with the low end. A Web Audio
  analyser reads the lowest frequency bins and brightens the sky slightly.

### 7. More like this

- **Idea:** a seed song should lead somewhere.
- **Where:** the sparkle button in the player, L, or the button in the details
  panel.
- **How:** sends `like=<id>`; the server keeps and orders tracks as described in
  §7. Your other filters still apply.
- **Undo:** a pill "More like “X” ×" returns to the full list.

### 8. DJ mode

- **Idea:** songs should flow into each other, not stop and start.
- **Two decks:** two `Audio` elements, each routed through its own Web Audio gain
  node. There's a fallback to element volume if Web Audio isn't available.
- **Picking the next song:** `djPick()` scores candidates on:
  - tempo closeness, allowing half and double time;
  - key compatibility;
  - same mood;
  - a little randomness.
- **The crossfade:** with 9 s left, the next deck starts at zero gain and both
  gains ramp over **8 seconds**. The player and waveform then switch to the new
  deck.
  - WaveSurfer's `setMediaElement` re-binds to it. URLs are made absolute because
    WaveSurfer skips loading a URL it thinks is already current.
  - Skipping or closing mid-blend silences the leaving deck cleanly.
  - Tracks under 45 s aren't blended.

### 9. Stations and endless play

- **Idea:** pick a vibe and never have to choose again.
- **Built-in stations:**
  - **Spanish rain:** Spanish, sad or tender, vocal, shuffled.
  - **2am lo-fi:** tender or sad electronic, ambient or hip hop at 60–95 bpm.
  - **Run 160:** exciting or happy vocal songs at 150–175 bpm.
  - **Fresh this year:** this year's vocal songs, newest first.
  - **Full moon mix:** shown on full moons.
  - **New this week:** shown after a refresh brings songs.
- **Your own stations:** **+ Save these filters** names the current filters as a
  station; × removes it. A station lights up when your filters match it exactly.
- **Endless play:** when the queue nears its end, the next 50 results load (one
  load at a time, with duplicates removed), so every list plays forever.

### 10. Mood map

- **Idea:** see the whole library as a landscape and play a region of it.
- **Drawing:** every song matching your current filters is a dot, coloured by mood
  and blended additively so dense areas glow.
  - Opacity adapts to the number of dots (between 0.27 and 0.85).
  - Dots shrink above 15,000 points.
  - Each mood's name is drawn at its centre.
- **Selecting:** drag a circle; on release Canopy searches that area and starts
  playing it. A "Patch of the mood map ×" pill shows the selection is active.

### 11. Never heard

- **Idea:** keep discovering instead of hearing the same songs again.
- **What counts as heard:** a song played for 20 s or more.
- **Storage:** heard songs are kept in the browser (`canopy.heard`) and mirrored
  to the server's `heard` table, so searches can exclude them with `unheard=true`.
  On load, the browser sends its whole set if it knows more than the server does.
  Stars count as heard.
- **Where it applies:** the Discover chip works with stations, the map and more
  like this. Shooting stars always use it.

### 12. New this week (the weekly refresh)

- **Idea:** the library should grow without anyone remembering to do it.
- **How:** see §5. The page builds a "New this week" station from
  `facets.fresh`, using `since_id` set to that run's `first_id`. Its tooltip says
  how many songs arrived and on what day.
- **Undo:** an "Added this week ×" pill clears it.

### 13. Lyrics

- **Idea:** read along.
- **Where:** a "lyrics" tag in the list, a With lyrics filter, and a Lyrics
  section in the details panel. Lyrics are clipped with a soft fade and a "Show
  all" button.
- **While playing:** tap the title in the player to open them.

### Smaller touches

- **Credit:** every song has ready-to-paste credit text: title, artist, licence,
  licence URL and source page.
- **Commercial filter:** one click shows only CC licences that allow commercial
  use.
- **Clean titles:** HTML entities in titles are decoded at import. 1,444 existing
  titles, artists and albums were fixed in place.
- **Clear stars:** asks for a second tap ("Clear all N?") within 4 s.

---

## 11. What lives where

| Kept in | What |
|---|---|
| `data/music.db` | the whole library, analysis, lyrics, mood map, heard ids, refresh log |
| Browser localStorage | `canopy.sky` (your stars), `canopy.kept` (kept constellations), `canopy.heard`, `canopy.stations`, `canopy.view` (vocals and sort), `canopy.shuffle`, `canopy.dj`, `canopy.fullmoon` (night of the last full-moon mix) |
| `.jamendo_client_id` | the Jamendo Client ID (git-ignored) |
| `~/panns_data/` | the PANNs model checkpoint and its class labels |
| `~/Library/LaunchAgents/canopy.refresh.plist` | the installed weekly schedule |
| `~/Library/Logs/canopy-refresh.log` | the weekly job's log |

Stars, kept constellations and custom stations exist only in the browser that
made them. They can't be rebuilt from the database, and clearing site data erases
them.

---

## 12. Rebuilding Canopy from scratch

**Time and transfer:** a few hours of importing and most of a day of analysis.
Analysis downloads about 0.5 MB per track, so about 50 GB for 95,000 tracks.
None of it is kept.

### 1. Prerequisites

- **macOS** (the schedule uses launchd; everything else works on any Unix).
- **Python 3.12** at `/Library/Frameworks/Python.framework/Versions/3.12/` (the
  python.org installer), plus **uv**.
- **A free Jamendo developer account:** at
  [devportal.jamendo.com](https://devportal.jamendo.com), create an app and copy
  its Client ID, an 8-character hex string. Any email works.

### 2. Environment

```bash
cd canopy                              # the project folder
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r requirements.txt
echo YOUR_CLIENT_ID > .jamendo_client_id
```

`requirements.txt` pins the versions Canopy runs on. Newer ones will probably work, but these
are known to.

### 3. The model checkpoint

```bash
mkdir -p ~/panns_data
curl -L -o ~/panns_data/Cnn14_mAP=0.431.pth \
  "https://zenodo.org/records/3987831/files/Cnn14_mAP%3D0.431.pth?download=1"
md5 -q ~/panns_data/Cnn14_mAP=0.431.pth   # must print 541141fa2ee191a88f24a3219fff024e
```

`panns_inference` also needs AudioSet's class labels in the same folder. It tries
to fetch them with `wget`, which macOS doesn't have, so download them yourself:

```bash
curl -L -o ~/panns_data/class_labels_indices.csv \
  "http://storage.googleapis.com/us_audioset/youtube_corpus/v1/csv/class_labels_indices.csv"
```

### 4. Build the library, in this order

```bash
python3 -I scripts/count_ia.py                          # census + item lists (data/items_*.jsonl)
python3 -I scripts/ingest.py --tracks-per-source 5000   # ~5k each from the 4 Internet Archive sources
python3 -I scripts/ingest_ccmixter.py --tracks 5000     # newest ccMixter vocal songs
python3 -I scripts/ingest_jamendo.py --lang en --tracks 50000   # every English vocal Jamendo song (~47k)
python3 -I scripts/ingest_jamendo.py --lang es --tracks 60000   # every Spanish one (--tracks = total Jamendo rows)
python3 -I scripts/ingest_audius.py --tracks 10000      # trending Audius tracks
caffeinate -i .venv/bin/python -I scripts/analyze.py    # tags every track, then builds the mood map
python3 -I scripts/fetch_lyrics.py                      # lyrics (rerun once to retry failed batches)
```

- **Approximate:** the Internet Archive sample is random, and the live sources
  change daily, so a rebuild gets a similar library, not an identical one.
- **The rest of today's library:** about 4,400 tracks came from weekly refreshes,
  mostly Audius. Run `.venv/bin/python -I scripts/refresh.py` to catch up.

### 5. Run it

```bash
.venv/bin/uvicorn app.server:app --port 8765
open http://localhost:8765
```

To restart after code changes:

```bash
pkill -f "uvicorn app.server"
nohup .venv/bin/uvicorn app.server:app --port 8765 > data/server.log 2>&1 &
```

### 6. Schedule the weekly refresh

```bash
sed -e "s|__CANOPY__|$PWD|g" -e "s|__HOME__|$HOME|g" \
  scripts/canopy.refresh.plist > ~/Library/LaunchAgents/canopy.refresh.plist
launchctl load ~/Library/LaunchAgents/canopy.refresh.plist
launchctl start canopy.refresh            # optional test run
```

Two macOS details matter:

- **Python needs Full Disk Access.** macOS keeps background jobs out of
  `~/Documents`. Without it, Python hangs at startup trying to read the virtual
  environment's config. Go to System Settings → Privacy & Security → Full Disk
  Access, click +, and add
  `/Library/Frameworks/Python.framework/Versions/3.12/Resources/Python.app`.
- **The log lives outside Documents.** launchd can't open log files under
  `~/Documents` itself (the job fails with exit code 78), so the plist logs to
  `~/Library/Logs/canopy-refresh.log` and sets no working directory.

launchd needs absolute paths, so the plist in the repo holds two placeholders
(`__CANOPY__` for the project folder, `__HOME__` for your home folder) that the
`sed` line fills in. If the project moves, install it again.

---

## 13. How it was tested

There is no test suite in the repository. Every change was checked in headless
Chromium with Playwright, at desktop (1440×900) and phone (390×844) sizes, and
with reduced motion. The scripts lived in a temporary folder. Each run checked
for:

- **errors:** no page errors and no console errors;
- **layout:** no sideways scrolling on the phone, and screenshots read by eye;
- **behaviour:** real actions such as clicking chips, playing songs, catching
  embers, dragging on the map, saving stations and naming constellations, then
  checking the resulting API calls and page state.

Special techniques:

- **Faking the date:** `page.clock.install` to test the moon phase and the hour
  skies.
- **Autoplay:** `--autoplay-policy=no-user-gesture-required` so audio plays
  headless.
- **DJ mode:** an `Audio` constructor spy to watch both decks during a crossfade.
  Both played during the overlap, then the old deck paused and cleared.
- **Endless play:** the list grew from 50 to 100 rows as playback passed the end.

**Not verified:** a real phone, Safari, and anything that depends on hearing the
audio, such as the bass breathing.

---

## 14. Known limits and honest caveats

- **Language:** tagged only for Jamendo and some Internet Archive items. Most
  other songs have no language, so language filters only see tagged songs.
- **Community uploads** carry uploader-asserted licences. The obvious mislabelled
  dumps are filtered, but others will remain.
- **Free Music Archive** mirror items record no licence and show as "Unknown".
- **Year** is the upload year for community uploads, so some archival recordings
  show a recent year.
- **ccMixter** is full of remixes, by design.
- **Audius** tracks are stream-only, and unlabelled covers can slip through.
  Starting playback takes 3–8 s because the stream redirects to an audio server.
- **Duplicates:** older Jamendo songs may appear twice, once from the archive.org
  copy and once from the live API. No de-duplication has been done.
- **Analysis:** tempo can read half or double time. The vocal rule is calibrated
  by eye. Genre and mood come from coarse AudioSet classes; "Exciting" covers a
  lot (about 34,000 songs).
- **Mood map** positions are relative ranks, not absolute measurements.
- **Heard songs** are shared by every browser that uses the same server.
- **Not in the repo:** the library itself (`data/music.db`, about 150 MB), the
  Internet Archive item lists and the run logs are git-ignored. §12 rebuilds them.

---

## 15. Roads not taken

| Idea | Why not (yet) |
|---|---|
| A business: a free-music finder for creators | Crowded. Openverse, the YouTube Audio Library, Pixabay and others already exist. Canopy stayed personal |
| Searching for songs you already know | Almost no known music is free; Canopy became about discovery |
| 78rpm records from 1926 on | Litigated, and only just entering the public domain |
| Live Music Archive (concert tapes) | Legal and huge, but Audius was chosen first |
| SoundCloud, Bandcamp, YouTube Audio Library, Pixabay, live FMA | Closed APIs, no API, or mostly all rights reserved |
| Openverse | Its music is the same Jamendo catalogue |
| Audio embeddings (CLAP, OpenL3) for true "sounds like" and text search | Not built. "More like this" and the mood map use the analysis tags instead |
| Whisper for transcribed lyrics and sung language | Not built. Lyrics come from the sources |
| GPU analysis | Offered (it could roughly halve analysis time), not done |
| The full ~1.29M-track Internet Archive catalogue | Would take about 8 days of CPU analysis. Canopy stopped at a sample |

---

## 16. Ideas waiting

From the feature list, numbers 14–19, not built:

- **14. Sleep timer:** fade out after 15, 30 or 60 minutes, or at the end of the
  song.
- **15. Lock-screen and media-key controls:** song name, artwork and play/skip on
  the phone lock screen and keyboard media keys.
- **16. Install as an app:** add to the home screen, open full screen, and keep
  favourites for offline listening (only songs whose licence allows downloads).
- **17. Faster Audius start:** look up the next Audius stream ahead of time so it
  starts instantly.
- **18. Year in stars:** a yearly recap of top moods, languages and genres, the
  most-played artist and total stars, shown as a sky.
- **19. Artist pages:** all of an artist's songs in Canopy, with links to support
  them on their own site.

---

## 17. File map

```
canopy/
├── README.md                 short operating manual
├── PROGRESS.md               how the project grew, stage by stage
├── requirements.txt          pinned Python packages for analysis and the server
├── .jamendo_client_id        Jamendo Client ID (you create it; git-ignored)
├── app/
│   ├── server.py             FastAPI: search, map, facets, track, stream relay, heard
│   └── static/index.html     the whole front end (≈1,450 lines: HTML, CSS, JS module)
├── scripts/
│   ├── schema.py             every table
│   ├── count_ia.py           Internet Archive census + item lists + licence/year filters
│   ├── ingest.py             Internet Archive sample → tracks
│   ├── ingest_ccmixter.py    ccMixter vocal uploads → tracks
│   ├── ingest_jamendo.py     Jamendo live API (by language) → tracks
│   ├── ingest_audius.py      Audius trending charts → tracks
│   ├── mp3chunk.py           range-request a mid-file MP3 slice and decode it
│   ├── analyze.py            tempo, key, loudness, PANNs vocals/genre/mood → analysis
│   ├── build_map.py          analysis → mood_map
│   ├── fetch_lyrics.py       Jamendo + ccMixter lyrics → lyrics
│   ├── refresh.py            the weekly job: new uploads → lyrics → analysis → map
│   └── canopy.refresh.plist  launchd schedule template (Sundays 04:00)
├── data/
│   ├── census_ia.json        census results
│   ├── music.db              the library (built by the scripts; git-ignored)
│   ├── items_*.jsonl         Internet Archive item lists (git-ignored)
│   └── *.log                 run logs (git-ignored)
└── docs/
    ├── CANOPY.md             this document
    ├── design/BRIEF.md       the scroll-craft design brief, feeling curve and feel check
    └── screenshots/          desktop and phone screenshots
```
