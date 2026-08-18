# Coding Rules — Python (`live_mixing`)

- All logic lives in `live_mixing/read_djuced_db.py`. There is no package structure beyond it — new
  functions go in that module, and any new public name must be added to both the `from .read_djuced_db
  import (...)` list and `__all__` in `live_mixing/__init__.py`.
- New read functions should go through `read_djuced_db(db_path, table=..., query=...)` rather than
  opening their own `sqlite3.connect`, unless they need `params=` binding (see below) — in that case
  follow the existing pattern in `read_track_cues`/`read_track_beatgrid`/`read_djuced_session`
  (check `db_path.exists()` and raise `FileNotFoundError` before connecting).
- Any join to `tracks` must use `tracks.absolutepath`, not `tracks.id` — see `docs/schemas.md` for
  the join-key convention.
- Functions that pass a pandas `Timestamp` into a raw `sqlite3` query parameter must call
  `.isoformat()` first — `sqlite3` cannot bind `Timestamp` objects directly (see
  `export_session_setlist_csv` for the working pattern).
- Keep `db_path` (or `csv_path`) as the parameter with the `DEFAULT_DB_PATH` keyword default on new
  functions, consistent with the rest of the module — but note the existing inconsistency in
  argument *order* documented in `docs/api-reference.md`; don't "fix" it as a drive-by change.
- If you touch `list_sessions()` or `match_recording_to_session()`, read `docs/architecture.md`
  first — both encode heuristics that were empirically tuned against real failure modes, not
  arbitrary defaults.
