---
name: djuced-db
description: "Read, query, and write a DJUCED DJ software SQLite database (djuced.db) via the `live_mixing` Python package (https://github.com/laceto/live_mixing) — tracks, playlists, sessions/setlists, play-log snapshots, CSV exports, and playlist create/append. Use when asked to query djuced.db, look up tracks or playlists, reconstruct DJ sessions, export setlists/CSVs, or create/add to DJUCED playlists."
---

# djuced-db — DJUCED Database Helper (`live_mixing`)

**Source:** https://github.com/laceto/live_mixing
**Install (inside the `live_mixing` repo):** already editable-installed (`pip install -e .`)
**Install (from another project, on this machine):**
`pip install -e C:/Users/l_ace/Desktop/projects/live_mixing` or
`pip install git+https://github.com/laceto/live_mixing.git`

Single third-party dependency: `pandas`. All logic lives in one module,
`live_mixing/read_djuced_db.py`, re-exported from `live_mixing/__init__.py`.

## Default DB location

`DEFAULT_DB_PATH` = `~/Documents/DJUCED/djuced.db`. Every function takes `db_path` as an override —
**argument order is inconsistent**: most `read_*`/`export_*` functions take `db_path` first, but
`export_*_csv` functions take `csv_path` first. Check the signature before assuming positional order.

## Public API

```python
from live_mixing import (
    DEFAULT_DB_PATH,
    read_djuced_db,                 # (db_path, table="tracks", query=None) generic base reader
    read_djuced_playlists,          # (db_path) raw playlists2 table
    read_djuced_playlist_tracks,    # (db_path) playlists2(type=3) JOIN tracks
    find_track_playlists,           # (search, db_path) which playlist(s) contain a matching track
    create_playlist,                # (name, absolutepaths, db_path) new playlist; ValueError if it exists
    add_track_to_playlist,          # (name, absolutepaths, db_path) append to existing playlist; ValueError if missing
    read_track_cues,                # (db_path, track_absolutepath=None, include_structure_markers=False)
    read_track_beatgrid,            # (db_path, track_absolutepath=None)
    current_track,                  # (db_path) most recently played track, 0 or 1 row
    read_djuced_session,            # (db_path, start=None, end=None) tracks played in a window
    list_sessions,                  # (db_path, gap_minutes=15) auto-detected session boundaries
    match_recording_to_session,     # (db_path, gap_minutes=15, start_tolerance_minutes=30, ambiguous_margin_seconds=300)
    snapshot_play_log,              # (log_dir, db_path) append-only play-event log, workaround for last_played
    find_missing_files,             # (db_path) tracks whose absolutepath no longer exists on disk
    top_played_tracks,              # (n=20, db_path)
    export_playlists_csv,           # (csv_path, db_path)
    export_tracks_csv,              # (csv_path, db_path, include_waveform=False)
    export_setlist_csv,             # (csv_path, db_path, start=None, end=None)
    export_session_setlist_csv,     # (session_id, csv_path=None, db_path, gap_minutes=15)
    export_sessions_csv,            # (csv_path, db_path, gap_minutes=15)
)
```

Optional, not imported by default: `from live_mixing import search` — hybrid BM25+semantic track
search built on `kitai` (`pip install -e ".[search]"`, needs `OPENAI_API_KEY`). See the module
docstring in `live_mixing/search.py` for the full pipeline.

## Schema quick reference

- `tracks` — the library: artist/title/genre/bpm/key/rating/playcount/`last_played`/`absolutepath`/
  `waveform` (blob, ~8KB, excluded from CSV export by default).
- `playlists2` — `type=0` playlist header rows, `type=3` track entries (`data` column = track path),
  `type=5` a single "AllSongsUnalyzed" marker row.
- `trackCues` — hot cues/loops; `cuenumber` 0..8 are real user-placed cues, 1000+ are DJUCED's own
  auto-detected structure markers (~91% of rows) — always filter `cuenumber < 1000` unless you
  explicitly want the noise.
- `trackBeats` — beatgrid data; `timesignature` is unreliable, don't build logic on it.
- `recordings` — recorded mix audio; filenames carry **time-of-day only, no date**.

**Join key everywhere is `tracks.absolutepath`** — never `tracks.id`. `playlists2.data`,
`trackCues.trackId`, `trackBeats.trackId` all match `absolutepath`.

## Common tasks

### Find which playlist(s) a track is in
```python
from live_mixing import find_track_playlists
find_track_playlists("andy lee lope")  # tokenized, case-insensitive substring match
                                        # across title/artist/albumartist/filename
```

### Create a new playlist / append to an existing one
```python
from live_mixing import create_playlist, add_track_to_playlist
create_playlist("new_set", [path1, path2])   # fails if "new_set" already exists
add_track_to_playlist("build", [path3])      # fails if "build" doesn't exist yet
```
**DJUCED must be closed before any write** — it holds an exclusive lock on `djuced.db` while running.

### Reconstruct sessions / export a setlist
```python
from live_mixing import list_sessions, export_session_setlist_csv
sessions = list_sessions()                  # session_id, date, start, end, duration_min, n_tracks
export_session_setlist_csv(session_id=120)  # writes setlist_session_120_<date>.csv
```
`gap_minutes=15` is empirically tuned to separate real mixing from library browsing — don't change
it without re-validating against real data.

### Track plays over time (works around `last_played` only holding the most recent play)
```python
from live_mixing import snapshot_play_log
snapshot_play_log("data")   # call right after each session, before the next one starts
```

### Library maintenance
```python
from live_mixing import find_missing_files, top_played_tracks
find_missing_files()   # tracks whose absolutepath no longer exists on disk
top_played_tracks(n=20)
```

## Gotchas

- Argument order inconsistency: `read_*`/`export_*` → `db_path` first; `export_*_csv` → `csv_path`
  first.
- `waveform` blob is excluded from `export_tracks_csv` by default — pass `include_waveform=True` to
  include it.
- `read_track_cues` filters `cuenumber < 1000` by default — most rows in `trackCues` are
  auto-detected structure markers, not real cues.
- Any write (`create_playlist`, `add_track_to_playlist`) requires DJUCED to be closed first — it
  holds an exclusive lock on the db file.
- `snapshot_play_log` degrades quietly on data anomalies (e.g. a playcount decrease from a db reset)
  rather than raising — by design, don't "fix" this into an exception.

## Running from the `live_mixing` repo

```
pip install -e .            # editable install
python scripts/demo.py      # walkthrough of every public function, writes CSVs to data/
pytest -q                   # smoke tests, no real djuced.db required
```
