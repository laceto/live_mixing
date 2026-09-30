---
name: now-playing-log
description: "Append the track(s) the Windows media player is currently playing to data/now_playing.txt in the live_mixing repo, as `Artist,Title,1;Genre;Texture;Energy;Role` lines — all four tags are required — skipping duplicates. Uses live_mixing.windows_now_playing() (Windows SMTC) and live_mixing.format_now_playing_line(). Use when asked to add/log/save what Windows is playing, add the current track to now_playing.txt, or 'add it to the file'."
---

# now-playing-log — log what Windows is playing to `now_playing.txt`

Appends whatever Windows' media player (Media Player, Spotify, Edge tabs... anything that publishes
to the system media controls) is **currently playing** to
`C:/Users/l_ace/Desktop/projects/live_mixing/data/now_playing.txt`, one line per track:

```
Artist,Title,1;Genre;Texture;Energy;Role
```

Windows only. Not DJUCED's decks (that's `live_mixing.current_track`).

## Required tags (4-axis matrix)

Every logged track needs **exactly one value on each of the four axes** — never write a line with
a tag missing. Values are defined in `live_mixing.TRACK_TAGS`; use them verbatim.

**1. Genre / Sub-Genre** — the musical skeleton ("il contenitore")
- `House` — classic/vocal house, 909 organs, pianos, warm/funky bass.
- `Deep House` — soft sounds, dreamy atmospheres, minor (dub) chords, relaxed groove.
- `Tech-House` — straight rhythm, rubbery bass, driving percussion.
- `Minimal` — essential, stripped-down tracks built on small elements.
- `Techno` — hard kick, tight rhythm, dark/industrial atmosphere.

**2. Texture & Vibe** — how it sounds, regardless of genre ("la pasta sonora")
- `Clicks & Pops` — synthetic ticks, micro-noises, surgical frequencies (M_nus style).
- `Organic & Percus` — wood blocks, congas, liquid bubbles, water samples, real percussion
  (Cecille / Cadenza / Desolat style).
- `Soul & Funk` — stabby grooves, happy vocal samples, horns, dancefloor funk.
- `Dub & Deep` — long reverbs, echoes, underwater atmospheres.
- `Acid` — 303 lines, resonance, high "frying" frequencies.

**3. Energy Level** — impact on the dancefloor / when to play it
- `E1_Aperitivo_Lounge` — background, no pressure, soft groove.
- `E2_Warmup` — gets feet moving, warms the floor without pushing.
- `E3_Mid_Groove` — the engine of the night, steady rhythm that keeps people dancing.
- `E4_Peak_Time` — maximum charge, present kick, high tension.

**4. DJ Tool / Role** — how to use it against the other deck
- `Tool` — dry, rhythmic tracks for long groove layering over another track (3-4 minutes).
- `Vocal` — clear voice (spoken or sung), great for breaking the rhythmic hypnosis.
- `Chugg/Roller` — continuous, pushing bassline that drives the flow.
- `Bridge` — "bridge" tracks for moving between genres (e.g. warm Deep House → drier Minimal).

## Steps

1. Run step A below to see what is playing (and whether it's already in the file).
2. For each new track, choose the four tags. If you genuinely know the record, propose tags from
   that knowledge and say they're your proposal; if you don't know it, say so and **ask the user**
   for the tags (offer your best guess from artist/label/remix credit, clearly marked as a guess).
   Don't write the line until all four tags are settled — if the user gave the tags in their
   request, use those.
3. Run step B with the chosen tags. `format_now_playing_line` raises `ValueError` on a missing or
   unknown tag — fix the tag, never bypass it by writing the line by hand.
4. Report exactly what it printed. Don't claim a track was added without that output.
5. Don't commit or push the file unless asked.

The `live_mixing` package is editable-installed on this machine; if `import live_mixing` fails,
`pip install -e C:/Users/l_ace/Desktop/projects/live_mixing`.

### A. What's playing

```python
from pathlib import Path

import live_mixing as lm

path = Path("C:/Users/l_ace/Desktop/projects/live_mixing/data/now_playing.txt")
existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
# Duplicate key = "Artist,Title" (ignores the count and tags), so old untagged lines still match.
logged = {line.split(";", 1)[0].rsplit(",", 1)[0] for line in existing if line.strip()}

playing = lm.windows_now_playing()  # Playing sessions only
if playing.empty:
    print("Nothing is playing on Windows right now.")
for _, row in playing.iterrows():
    key = f"{row['artist']},{row['title']}"
    print(("Already in file: " if key in logged else "New: ") + key)
```

### B. Append with tags

```python
from pathlib import Path

import live_mixing as lm

path = Path("C:/Users/l_ace/Desktop/projects/live_mixing/data/now_playing.txt")
tracks = [
    # (artist, title, genre, texture, energy, role) — fill in from step A + step 2
    ("Artist", "Title", "Minimal", "Clicks & Pops", "E3_Mid_Groove", "Tool"),
]

existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
logged = {line.split(";", 1)[0].rsplit(",", 1)[0] for line in existing if line.strip()}

new_lines = []
for artist, title, *tags in tracks:
    line = lm.format_now_playing_line(artist, title, *tags)  # ValueError on bad/missing tag
    key = line.split(";", 1)[0].rsplit(",", 1)[0]
    if key in logged:
        print(f"Already in file: {key}")
    else:
        logged.add(key)
        new_lines.append(line)

if new_lines:
    raw = path.read_text(encoding="utf-8") if path.exists() else ""
    prefix = "\n" if raw and not raw.endswith("\n") else ""
    with path.open("a", encoding="utf-8") as f:
        f.write(prefix + "\n".join(new_lines) + "\n")
    for line in new_lines:
        print(f"Added: {line}")
```

## Notes

- Only `Playing` sessions are logged; paused ones (e.g. a paused Edge tab) are ignored. To include
  them, call `lm.windows_now_playing(playing_only=False)` — only when the user asks.
- The media session's `artist`/`title` are whatever the app publishes: some apps put the release in
  the artist field (e.g. `Basti Grub feat. Agent! - Walking In My Blues - DESOLAT X014`), and titles
  containing commas are fine for `read_playlist_file` but make the file harder to eyeball. Report
  oddities rather than silently rewriting them.
- Duplicate check is on `Artist,Title` only, so a track is added once regardless of its tags. To
  retag an existing line, edit that line in place (only when the user asks).
- `live_mixing.playlist_analysis.read_playlist_file` returns the tags as `genre`, `texture`,
  `energy`, `role` columns (`""` for older untagged lines).
