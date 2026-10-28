# Canopy: brief

**Self-authored under explicit creative delegation.** The user asked to "redesign
the website. make it calm and relaxing - think outer space, calm forest, tc. use
your judgement for the vibe", and mid-build added: "make the music player ...
close-able. that should remove the player and stop the track currently playing.
additionally, make it translucent overlay". Everything below that is not a quote
is an authored decision.

## Constraints from the user (verbatim intent)

- Calm and relaxing. Outer space, calm forest.
- Keep every existing function: search, filters (vocals, genre, mood, tempo,
  key, year, source, license), results, details drawer, waveform player.
- Player: closable (close stops playback and removes the player) and a
  translucent overlay.
- Personal use and learning. No audience, no conversion goal.

## The eight topics

1. **Vibe (authored):** night forest under deep space; still, cool, quiet,
   one warm light. References: the last blue of dusk over a pine ridge; a long
   exposure of the Milky Way from a forest clearing; fireflies at the edge of
   a meadow.
2. **Journey (authored):** you arrive at the treeline at dusk with the search
   already waiting; you browse, and as the list scrolls the camera rises out of
   the trees; you play something and the sky responds; at the top of the sky
   the stars you listened to are waiting; you name tonight's constellation.
3. **Energy curve:** low throughout. The only rise is the lift above the
   treeline, and even that is slow.
4. **Feeling, stage by stage, and the one moment:** see the curve below. The
   moment: rising above the trees and finding your listening drawn as stars.
5. **One thing no site does:** every track you play becomes a star in the sky,
   joined to the last, so the session leaves a constellation behind.
6. **Range:** quiet, dense enough to be a tool. Not premium-minimal marketing;
   a working surface set inside a calm place.
7. **One world or scenes:** one world, fixed behind the tool. The tool
   scrolls; the world answers the scroll with altitude, it does not cut.
8. **Assets:** none supplied; no image-generation key and no ffmpeg on this
   machine. The world is drawn in code (canvas and SVG), which gives genuine
   alpha planes with no spend. This is an illustrated world by necessity and
   by fit: a night sky rendered as light points and silhouettes is honest
   about being drawn.

## Grammar

**Live surface.** The page is the tool. App chrome is the navigation, the hero
is the surface already in a state (search ready, results listed), the close is
a real input. No marketing headline, no scrims over photos, no kinetic type.
The other seven lost because this is a working tool for one person: filmic,
editorial, poster and cutlist are argument or brand shapes; gallery would
fight the search-first use; split stage has no two sides; continuous world
would put copy inside a fixed canvas and break a long, filterable list.

## Feeling curve

```
1  Stillness    dusk at the treeline, fireflies, the search field waiting on the horizon
2  Curiosity    results listed, mood chips glowing faintly, the sky deepening as you browse
3  Absorption   a track plays, the stars breathe with its low end, the waveform is amber
4  Awe (peak)   the list has carried you above the trees, the Milky Way opens, your stars are joined
5  Belonging    an input asks you to name tonight's constellation, and it keeps the name
```

## Peak

> "I scrolled and floated up out of the forest, and every song I'd played was
> up there as a star, joined into a constellation."

Lives at the top of the altitude range (deep scroll). It gets the most scroll
room (the whole result list is the climb) and the quiet before it (dusk, no
motion beyond fireflies).

## It's the site where

> it's the site where every song you play becomes a star, and scrolling lifts
> you out of the forest to see them.

## Signature move

**Listening constellation.** A track that plays for 20 seconds lights a star at
a sky position derived from its id, linked by a faint line to the previous
star. Stars are hoverable and clickable (replay). Stored per-viewer in
localStorage. The close names it.

## Authored silence

The opening screen holds the search and a single row of mood chips above the
results with open sky behind them. That gap is intentional dusk, not dead
scroll.

## Layer contract

| Plane | Rendering | Altitude travel (of max) | Notes |
|---|---|---|---|
| Sky ground | CSS gradient, regraded by altitude | none, colour shifts | dusk teal at bottom, deep space at top |
| Milky Way + far stars | canvas | 6% | twinkle, breathe with audio |
| Constellation | canvas (same layer as near stars) | 10% | signature |
| Moon | DOM disc | 14% | high right |
| Mountain ridge | SVG | 35% | low contrast, bluish |
| Far pines | SVG, generated | 60% | darker |
| Mist | gradient band | 75% | slow lateral drift |
| Near pines | SVG, generated | 110% | darkest, frames bottom |
| Fireflies | canvas | 120% | amber, few, foreground atmosphere |
| Tool (chrome, list, player) | HTML | scrolls normally | translucent panels |

## Palette

Deep forest night with bone and amber (taste.md rotation): canvas #08121A,
surface rgba(14,27,33,.72), ink #E7ECE4, ink-soft #9FB3AA, accent (firefly
amber) #F0C36A, accent-ink #1B1406. Fonts: Outfit (display), Geist (text).

## Feel check (cold scroll, then diffed against the curve)

| Stage | Intended | Felt on the screenshots | Change made |
|---|---|---|---|
| 1 | Stillness at the treeline | First pass: "sky", not dusk; forest hidden behind panels | Raised the horizon to 46vh (40vh phone), solid ground below each silhouette, fireflies moved up to the treeline |
| 2 | Curiosity | Forest sinking as the list scrolls; reads as rising | none |
| 3 | Absorption | Player overlay quiet and legible over the scene; breathing not observable headless | none (unverified, see report) |
| 4 | Awe (peak) | Open sky, Milky Way, joined stars, moon; clearly the largest change | none |
| 5 | Belonging | Naming input lands as an ending, kept list below | none |

## Verification (Playwright, Chromium, local)

- Desktop 1440x900 at 0, 35, 70, 100% of scroll; phone 390x844 top, playing, bottom; reduced motion.
- Playback starts from a row; closing the player pauses media, clears its source, hides the overlay, clears the playing row.
- Quick mood chips and sidebar mood chips stay in sync; naming a constellation archives it and shows it.
- No console errors; no horizontal overflow on the phone.
- Not verified: a real phone, Safari, and the audio-reactive breathing (headless audio output).
