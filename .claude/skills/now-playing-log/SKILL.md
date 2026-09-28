---
name: now-playing-log
description: "Append the track(s) the Windows media player is currently playing to data/now_playing.txt in the live_mixing repo, as `Artist,Title,1` lines, skipping duplicates. Uses live_mixing.windows_now_playing() (Windows SMTC). Use when asked to add/log/save what Windows is playing, add the current track to now_playing.txt, or 'add it to the file'."
---

# now-playing-log — log what Windows is playing to `now_playing.txt`

Appends whatever Windows' media player (Media Player, Spotify, Edge tabs... anything that publishes
to the system media controls) is **currently playing** to
`C:/Users/l_ace/Desktop/projects/live_mixing/data/now_playing.txt`, one `Artist,Title,1` line per
track — the same layout as `data/create a playlist with.txt`.

Windows only. Not DJUCED's decks (that's `live_mixing.current_track`).

## Steps

1. Run the snippet below with `python` (the `live_mixing` package is editable-installed on this
   machine; if `import live_mixing` fails, `pip install -e C:/Users/l_ace/Desktop/projects/live_mixing`).
2. Report exactly what it printed — which track(s) were added, or that it was already in the file /
   nothing was playing. Don't claim a track was added without that output.
3. Don't commit or push the file unless asked.

```python
from pathlib import Path

import live_mixing as lm

path = Path("C:/Users/l_ace/Desktop/projects/live_mixing/data/now_playing.txt")
existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []

playing = lm.windows_now_playing()  # Playing sessions only
if playing.empty:
    print("Nothing is playing on Windows right now.")

new_lines = []
for _, row in playing.iterrows():
    line = f"{row['artist']},{row['title']},1"
    if line in existing or line in new_lines:
        print(f"Already in file: {line}")
    else:
        new_lines.append(line)

if new_lines:
    prefix = "\n" if existing and not path.read_text(encoding="utf-8").endswith("\n") else ""
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
  containing commas will break the `Artist,Title,1` layout. Report oddities rather than silently
  rewriting them.
- Duplicate check is an exact-line match, so the same track is only added once.
