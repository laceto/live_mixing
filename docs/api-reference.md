# API Reference — `live_mixing`

All functions live in `live_mixing/read_djuced_db.py` and are re-exported from `live_mixing/__init__.py`.
Every function takes `db_path` (default `DEFAULT_DB_PATH` = `~/Documents/DJUCED/djuced.db`), but
**argument order is not fully consistent** — check the signature before assuming positional order
(most `read_*`/`export_*` functions take `db_path` first, but `export_*_csv` functions take
`csv_path` first).

## Optional: hybrid track search

`live_mixing/search.py` — hybrid (BM25 + semantic) free-text track search, built on
[`kitai`](https://github.com/laceto/kitai) and OpenAI's Batch API. Not part of the pandas-only
core; not imported by `live_mixing/__init__.py`. Install with `pip install -e ".[search]"` plus
`pip install git+https://github.com/laceto/kitai.git`, and set `OPENAI_API_KEY`. See the module
docstring for the full pipeline (`build_track_documents` → `submit_embedding_job` →
`fetch_embeddings` → `load_track_index` → `build_hybrid_retriever` → `search_tracks`) and its
embedding cache (`EMBEDDING_CACHE_PATH`, default `data/track_embeddings_cache.csv`) that skips
re-embedding tracks already indexed.

## Core reader

- `read_djuced_db(db_path=DEFAULT_DB_PATH, table="tracks", query=None)` — base helper every other
  `read_*` function goes through. Pass `table` for a plain `SELECT *`, or `query` for custom SQL.

## Reads / joins

- `read_djuced_playlists(db_path=DEFAULT_DB_PATH)` — raw `playlists2` table.
- `read_djuced_playlist_tracks(db_path=DEFAULT_DB_PATH)` — `playlists2` (type=3) joined to `tracks`,
  one row per (playlist, track).
- `find_track_playlists(search, db_path=DEFAULT_DB_PATH)` — which playlist(s) contain tracks
  matching `search` (case-insensitive substring against title/artist/albumartist/filename).
- `create_playlist(name, absolutepaths, db_path=DEFAULT_DB_PATH)` — create a new DJUCED playlist;
  raises `ValueError` if `name` already exists. DJUCED must be closed first.
- `add_track_to_playlist(name, absolutepaths, db_path=DEFAULT_DB_PATH)` — append tracks to an
  existing playlist; raises `ValueError` if `name` doesn't exist. DJUCED must be closed first.
- `read_track_cues(db_path=DEFAULT_DB_PATH, track_absolutepath=None, include_structure_markers=False)`
  — real hot cues/loops from `trackCues` joined to `tracks`, filtered to `cuenumber < 1000` by
  default (see `docs/schemas.md` — most `trackCues` rows are auto-detected structure markers, not
  real cues). Restrict to one track via `track_absolutepath`; pass
  `include_structure_markers=True` to get the unfiltered table.
- `read_track_beatgrid(db_path=DEFAULT_DB_PATH, track_absolutepath=None)` — beatgrid data from
  `trackBeats` joined to `tracks`. `beatpos` is raw bytes (packed blob, size varies per track).

## Now playing

- `current_track(db_path=DEFAULT_DB_PATH)` — the single most-recently-played track (by
  `last_played`). Returns a DataFrame with 0 or 1 rows (empty if no track has ever been played).
  Same query pattern used by external now-playing pollers (e.g. unbox's DJUCED integration).

## Session reconstruction (see `docs/architecture.md` for the heuristic reasoning)

- `read_djuced_session(db_path=DEFAULT_DB_PATH, start=None, end=None)` — tracks played in
  `[start, end]` by `last_played`, ordered chronologically.
- `list_sessions(db_path=DEFAULT_DB_PATH, gap_minutes=15)` — auto-detected session boundaries
  across the whole play history. Returns `session_id, date, start, end, duration_min, n_tracks`.
- `match_recording_to_session(db_path=DEFAULT_DB_PATH, gap_minutes=15, start_tolerance_minutes=30, ambiguous_margin_seconds=300)`
  — pairs `recordings` rows to detected sessions. Returns per-recording match info including
  `match` (bool) and `ambiguous` (bool).

## Play-log tracking (see `docs/architecture.md` for the design rationale)

- `snapshot_play_log(log_dir, db_path=DEFAULT_DB_PATH)` — diffs the current `tracks` table
  against the previous snapshot in `log_dir`, appends any newly detected plays to
  `log_dir/play_events.csv`, and updates `log_dir/play_log_state.csv` for the next call. Returns
  the newly appended events as a DataFrame (empty on the first call or if nothing changed). Call
  it right after each session, before starting a new one — it's the workaround for
  `last_played` only ever holding the *most recent* play per track.

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
