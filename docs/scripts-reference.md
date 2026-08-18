# Scripts & Commands Reference

```
pip install -e .
```

Installs `live_mixing` as an editable package. The only third-party dependency is `pandas`;
`sqlite3`, `pathlib`, and `re` are stdlib.

## Demo

```
python scripts/demo.py
```

Runnable walkthrough of every public function in `live_mixing`. Writes CSV artifacts into `data/`
(gitignored): `tracks_export.csv`, `playlists_export.csv`, `sessions_export.csv`, `setlist_*.csv`.
Session `90` (2026-08-15) is hardcoded as an example inside the script — adjust it to a
`session_id` from your own `list_sessions()` output when re-running against a different database.

## Tests

```
pytest -q
```

Smoke tests only (`tests/test_read_djuced_db.py`) — they don't require a real `djuced.db`. They
check the public API is importable, `read_djuced_db` raises `FileNotFoundError` for a missing db
path, and `DEFAULT_DB_PATH` is configurable.

There is no linter or CI configured — don't invent commands for these.
