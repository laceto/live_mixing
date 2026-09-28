---
name: now-playing
description: "Report what the Windows media player is playing right now (read-only — writes nothing). Uses live_mixing.windows_now_playing() (Windows SMTC), so it sees Media Player, Spotify, Edge/Chrome tabs, etc. Use when asked 'what is playing now?', 'what's on?', 'what is the Windows player playing?'. To save the track to data/now_playing.txt use the now-playing-log skill instead."
---

# now-playing — what is Windows playing right now? (read-only)

Reports the current state of every Windows media session. Does **not** write any file — to log the
track to `data/now_playing.txt`, use `now-playing-log`. Not DJUCED's decks (that's
`live_mixing.current_track`).

## Steps

1. Run the snippet below with `python` (the `live_mixing` package is editable-installed on this
   machine; if `import live_mixing` fails, `pip install -e C:/Users/l_ace/Desktop/projects/live_mixing`).
2. Answer from that output only — never from an earlier check, since the track changes. Lead with
   the session whose status is `Playing`; mention paused sessions briefly (e.g. a paused Edge tab).
3. Optionally say whether the playing track is already in `data/now_playing.txt`, and offer to add
   it via `now-playing-log`. Don't add it unprompted.

```python
import live_mixing as lm

sessions = lm.windows_now_playing(playing_only=False)
print(sessions.to_string() if not sessions.empty else "No Windows media sessions.")
```

## Notes

- `artist`/`title` are whatever the app publishes, so they can hold oddities (a catalogue number in
  the title, the release in the artist field). Quote them as reported.
- Windows only — `windows_now_playing` raises `RuntimeError` elsewhere.
