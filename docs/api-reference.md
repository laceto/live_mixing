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

## Optional: OpenAI playlist analysis

`live_mixing/playlist_analysis.py` — sends a playlist to OpenAI and asks for the overall journey
and a DJ-set order. Not part of the core; not imported by `live_mixing/__init__.py`
(`from live_mixing import playlist_analysis`). Install with `pip install -e ".[analysis]"` and set
`OPENAI_API_KEY` in the environment or in a `.env` file (gitignored) in the current directory or
repo root — `.env` is read only when `analyze_playlist()` creates its own client, never at import,
and never overrides variables already set.

- `load_env_file(path=None)` — loads `KEY=VALUE` lines from `.env` into `os.environ` (no override;
  handles comments, `export `, quotes). Returns the names of newly set variables, never values.

- `read_playlist_file(path="data/now_playing.txt")` — parses `Artist,Title,1` lines into a
  DataFrame (`artist`, `title`, `genre`, `texture`, `energy`, `role`, `context`); titles may contain commas.
  Optional `;genre;texture;energy;role;context` tags after the count fill the tag columns (`""` when a
  line is untagged).
- `analyze_playlist(tracks=None, client=None, model="gpt-4.1-mini", context=<minimal-era 2004-2012>, temperature=0.2)` —
  `tracks` is a DataFrame (`artist`, `title`) or a file path (default `data/now_playing.txt`).
  Returns a dict: `journey` (str), `set_order` (DataFrame: `phase`, `position`, `artist`, `title`,
  `known`, `reason`, ordered warm_up → building → peak → breakdown) and `unassigned` (tracks the
  model left out). The model answers with track *numbers*, so it can't invent tracks. The prompt
  lets the model make a best-effort inference about tracks it doesn't recognise but requires it to
  say so and never to invent specifics (label, year, BPM, key): each track comes back with `known`
  (True only if the model says it recognises that exact record); unknown tracks get a reason
  starting "Not known - inferred: ". `known` is the model's self-report, not something verified. Raises `ValueError` on an
  empty playlist, `FileNotFoundError` on a missing file. Sends the track list to OpenAI.

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
- `windows_now_playing(playing_only=True, timeout=15)` — what the Windows media player(s) are
  playing, read from the system media transport controls (SMTC) via `powershell.exe` (no extra
  dependency). Returns a DataFrame with columns `source`, `status`, `artist`, `title`, `album`, one
  row per media session (Media Player, Edge tabs, Spotify...); `playing_only=True` keeps only
  `Playing` rows. Not DJUCED-specific — use `current_track` for DJUCED. Raises `RuntimeError` off
  Windows or if the PowerShell query fails.
- `TRACK_TAGS` — dict of the five required tag axes for `data/now_playing.txt` and their allowed
  values: `genre` (House, Deep House, Tech-House, Minimal, Techno), `texture` (Clicks & Pops,
  Organic & Percus, Soul & Funk, Dub & Deep, Acid), `energy` (E1_Aperitivo_Lounge, E2_Warmup,
  E3_Mid_Groove, E4_Peak_Time), `role` (Tool, Vocal, Chugg/Roller, Bridge), `context` (Ctx_Listening_Aperitivo, Ctx_Clubbing,
  Ctx_Afterhour).
- `format_now_playing_line(artist, title, genre, texture, energy, role, context)` — returns the
  tagged log line `Artist,Title,1;genre;texture;energy;role;context`. Tags are matched case-insensitively against
  `TRACK_TAGS` and returned in canonical spelling. Raises `ValueError` if any tag is missing or
  unknown, or artist/title is empty.

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
