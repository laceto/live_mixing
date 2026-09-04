# live_mixing

Read, join, and export data from a [DJUCED](https://www.hercules.com/en-us/product/djuced/) DJ
software SQLite database (`djuced.db`).

## Install

```
pip install -e .
```

## After each session

Run this **once, right after you finish mixing, before starting a new session** (even casual
library browsing that might replay a track):

```python
import live_mixing as lm

new_events = lm.snapshot_play_log(log_dir="play_log")
```

**Why**: DJUCED has no play-log table — `tracks.last_played` only ever stores the *most recent*
play per track. If you replay a track later, its earlier session's timestamp is silently
overwritten and becomes unrecoverable from `djuced.db` alone, which makes `list_sessions()` and
`read_djuced_session()` miss it retroactively. `snapshot_play_log()` works around this by diffing
`playcount` against the last snapshot in `log_dir` and appending any newly detected plays to an
append-only `play_events.csv` — once a play is logged there, a later replay can no longer erase
it. Pick one `log_dir` and reuse it every time; the shorter the gap between calls, the more
precisely each detected play can be attributed to a specific session. See `docs/architecture.md`
for the full design rationale.

Then export and publish that session's tracklist to GitHub:

```python
sessions = lm.list_sessions()
last = sessions.iloc[-1]
lm.export_session_setlist_csv(session_id=int(last["session_id"]))
```

```
git add data/setlist_session_<id>_<date>.csv
git commit -m "chore(data): commit setlist for session <id> (<date>)"
git push
```

**Why**: every DJ set's tracklist is meant to be visible on GitHub, not just kept locally.
`data/*.csv` exports are gitignored by default (they're reproducible from `djuced.db`), except
`data/setlist_session_*.csv` — `.gitignore` carves out an explicit exception for that filename
pattern so session setlists are tracked and pushed every time.

## Usage

```python
import live_mixing as lm

tracks = lm.read_djuced_db()  # defaults to ~/Documents/DJUCED/djuced.db
playlists = lm.read_djuced_playlists()
playlist_tracks = lm.read_djuced_playlist_tracks()

# What's playing right now (the most-recently-played track)
now_playing = lm.current_track()

# Hot cues / beatgrid for one track
cues = lm.read_track_cues(track_absolutepath="C:/path/to/track.mp3")
beatgrid = lm.read_track_beatgrid(track_absolutepath="C:/path/to/track.mp3")

# Reconstruct a DJ session (DJUCED has no play-log table — sessions are
# inferred from tracks.last_played timestamps)
sessions = lm.list_sessions()
setlist = lm.export_session_setlist_csv(session_id=90)

# Pair recorded mix audio files to a detected session
matches = lm.match_recording_to_session()

# Track plays permanently across replays — see "After each session" above
new_events = lm.snapshot_play_log(log_dir="play_log")

# Library maintenance
missing = lm.find_missing_files()
top = lm.top_played_tracks(n=20)
```

Every function accepts a `db_path` argument if your database isn't at the default location.

Run `python scripts/demo.py` from the project root for a runnable walkthrough of the full API
(writes its outputs to `data/`).

## Project structure

```
live_mixing/
├── live_mixing/
│   ├── __init__.py            # public API re-exports
│   └── read_djuced_db.py      # all read/export/session-reconstruction logic
├── scripts/
│   └── demo.py                # runnable demo of every function
├── data/                       # generated CSV exports (gitignored, except setlist_session_*.csv)
├── tests/
│   └── test_read_djuced_db.py
└── pyproject.toml
```

See `CLAUDE.md` for database schema notes, join-key conventions, and the reasoning behind the
session-reconstruction heuristics.
