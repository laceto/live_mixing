# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An installable Python package (`live_mixing`) for reading and exporting data from a DJUCED DJ software
SQLite database (`djuced.db`, default location `~/Documents/DJUCED/djuced.db`, overridable via the
`db_path` arg on every function). All logic lives in one module, `live_mixing/read_djuced_db.py`; the
package `__init__.py` re-exports every public function. The only third-party dependency is `pandas`;
`sqlite3`, `pathlib`, and `re` are stdlib.

## Running

```
pip install -e .
python scripts/demo.py    # runnable demo of every public function; writes CSVs to data/
pytest -q                 # smoke tests (no real djuced.db required)
```

There is no linter or CI configured — don't invent commands for these.

## Database shape

- `tracks` — the music library (artist/title/genre/bpm/key/rating/playcount/`last_played`/`absolutepath`/
  `waveform` blob, etc.). `waveform` is an ~8KB binary blob per row — always excluded from CSV export by
  default (`export_tracks_csv(..., include_waveform=False)`).
- `playlists2` — mixed-purpose table distinguished by `type`: `type=0` rows are playlist/crate name
  headers, `type=3` rows are actual track entries (their `data` column holds the track's file path),
  `type=5` is a single special "AllSongsUnalyzed" marker row.
- `trackCues`, `trackBeats` — hot cues/loops and beatgrid data per track.
- `recordings` — paths to recorded mix audio files, named like
  `"My Mix - 15h04m49s to 17h13m16s.mp3"` — **time-of-day only, no date**.
- `samples`, `temporary`, `tblFolderScan`, `tblAdmin` — minor/auxiliary tables.

**Join key convention**: `tracks.absolutepath` is the join key everywhere — `playlists2.data`,
`trackCues.trackId`, and `trackBeats.trackId` all match against it directly (not against `tracks.id`).

## Core patterns in `live_mixing/read_djuced_db.py`

- `read_djuced_db(db_path, table="tracks", query=None)` is the base helper every other `read_*` function
  goes through — either pass `table` for a plain `SELECT *`, or `query` for custom SQL.
- **DJUCED has no session/play-log table.** "Sessions" (a continuous DJ set) are reconstructed
  heuristically from `tracks.last_played` timestamps:
  - `list_sessions(gap_minutes=15)` clusters plays by time gap — a gap larger than `gap_minutes` starts a
    new session. 15 min was empirically tuned to separate real back-to-back mixing (gaps of tens of
    seconds to a few minutes, matching track length) from library browsing/cueing (gaps of only a few
    seconds, too short to be a real play).
  - Because `last_played` stores only the *most recent* play per track, a track replayed after the window
    you're querying won't show up for an earlier session — this is a real, unfixable limitation of the
    data, not a bug.
  - `match_recording_to_session()` pairs `recordings` rows to detected sessions. Since recording filenames
    only carry time-of-day, multiple sessions on different dates can start at a similar clock time —
    matching is therefore ranked primarily by **duration** closeness (recording length vs. session span),
    not start-time proximity, which was tried first and produced wrong matches (a short recording matched
    a wrong, unrelated multi-hour session purely by start-time coincidence).
- Functions that pass a pandas `Timestamp` into a raw sqlite3 query parameter must call `.isoformat()`
  first — `sqlite3` cannot bind `Timestamp` objects directly (hit and fixed in
  `export_session_setlist_csv`).
- Argument order is not fully consistent across functions — most `read_*`/`export_*` functions take
  `db_path` (or `csv_path`) first with a keyword default of `DEFAULT_DB_PATH`, but check the signature
  before assuming positional order.
