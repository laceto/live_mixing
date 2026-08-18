# API Reference — `live_mixing`

All functions live in `live_mixing/read_djuced_db.py` and are re-exported from `live_mixing/__init__.py`.
Every function takes `db_path` (default `DEFAULT_DB_PATH` = `~/Documents/DJUCED/djuced.db`), but
**argument order is not fully consistent** — check the signature before assuming positional order
(most `read_*`/`export_*` functions take `db_path` first, but `export_*_csv` functions take
`csv_path` first).

## Core reader

- `read_djuced_db(db_path=DEFAULT_DB_PATH, table="tracks", query=None)` — base helper every other
  `read_*` function goes through. Pass `table` for a plain `SELECT *`, or `query` for custom SQL.

## Reads / joins

- `read_djuced_playlists(db_path=DEFAULT_DB_PATH)` — raw `playlists2` table.
- `read_djuced_playlist_tracks(db_path=DEFAULT_DB_PATH)` — `playlists2` (type=3) joined to `tracks`,
  one row per (playlist, track).
- `read_track_cues(db_path=DEFAULT_DB_PATH, track_absolutepath=None)` — hot cues/loops from
  `trackCues` joined to `tracks`. Restrict to one track via `track_absolutepath`.
- `read_track_beatgrid(db_path=DEFAULT_DB_PATH, track_absolutepath=None)` — beatgrid data from
  `trackBeats` joined to `tracks`. `beatpos` is raw bytes (packed blob, size varies per track).

## Session reconstruction (see `docs/architecture.md` for the heuristic reasoning)

- `read_djuced_session(db_path=DEFAULT_DB_PATH, start=None, end=None)` — tracks played in
  `[start, end]` by `last_played`, ordered chronologically.
- `list_sessions(db_path=DEFAULT_DB_PATH, gap_minutes=15)` — auto-detected session boundaries
  across the whole play history. Returns `session_id, date, start, end, duration_min, n_tracks`.
- `match_recording_to_session(db_path=DEFAULT_DB_PATH, gap_minutes=15, start_tolerance_minutes=30, ambiguous_margin_seconds=300)`
  — pairs `recordings` rows to detected sessions. Returns per-recording match info including
  `match` (bool) and `ambiguous` (bool).

## Library maintenance

- `find_missing_files(db_path=DEFAULT_DB_PATH)` — tracks whose `absolutepath` no longer exists on
  disk.
- `top_played_tracks(n=20, db_path=DEFAULT_DB_PATH)` — top N tracks by `playcount`.

## CSV export

- `export_playlists_csv(csv_path, db_path=DEFAULT_DB_PATH)`
- `export_tracks_csv(csv_path, db_path=DEFAULT_DB_PATH, include_waveform=False)`
- `export_setlist_csv(csv_path, db_path=DEFAULT_DB_PATH, start=None, end=None)`
- `export_session_setlist_csv(session_id, csv_path=None, db_path=DEFAULT_DB_PATH, gap_minutes=15)` —
  raises `ValueError` if `session_id` doesn't match any detected session. `csv_path` defaults to
  `"setlist_session_<session_id>_<date>.csv"` if omitted.
- `export_sessions_csv(csv_path, db_path=DEFAULT_DB_PATH, gap_minutes=15)`
