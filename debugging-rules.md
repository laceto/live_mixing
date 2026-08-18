# Debugging Rules

Known gotchas, in order of how likely you are to hit them:

- **`sqlite3.ProgrammingError` binding a pandas `Timestamp`** — `sqlite3` cannot bind `Timestamp`
  objects directly as query params. Call `.isoformat()` on it first before passing to
  `pd.read_sql_query(..., params=[...])`. Already fixed once in `export_session_setlist_csv`; if you
  see this error elsewhere, it's the same root cause.
- **A session/setlist looks incomplete or wrong** — `tracks.last_played` stores only the *most
  recent* play per track. If a track was replayed after the session window you're querying, it won't
  show up for the earlier session. This is a real limitation of the source data, not a bug in
  `list_sessions`/`read_djuced_session` — don't "fix" it by changing the query logic. See
  `docs/architecture.md`.
- **`match_recording_to_session` picks the wrong session** — this was a real bug previously caused
  by ranking candidates by start-time proximity alone; multiple sessions on different dates can
  start at a similar clock time since recording filenames only carry time-of-day. The fix was
  ranking by session-duration closeness instead. If a match still looks wrong, check
  `ambiguous_margin_seconds` and `start_tolerance_minutes` before changing the ranking algorithm —
  see `docs/architecture.md`.
- **Unexpected `TypeError`/`FileNotFoundError` calling a `read_*`/`export_*` function positionally**
  — argument order is not fully consistent across functions (most take `db_path` first, `export_*`
  functions take `csv_path` first). Check the actual signature in
  `live_mixing/read_djuced_db.py` — see `docs/api-reference.md`.
- **`FileNotFoundError: DJUCED database not found`** — expected behavior when `db_path` doesn't
  exist; every read function checks this explicitly before connecting. Verify the path, don't
  suppress the check.
- **`snapshot_play_log()` events look "missing" or undercounted** — a track played more than once
  between two snapshot calls collapses into a single event with `playcount_delta > 1`; it does not
  split into separate timestamped events. This isn't a bug — snapshot more often (e.g. right after
  every session) for finer granularity. See `docs/architecture.md`.
