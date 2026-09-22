# Scripts & Commands Reference

```
pip install -e .
```

Installs `live_mixing` as an editable package. The only required third-party dependency is
`pandas`; `sqlite3`, `pathlib`, and `re` are stdlib.

Optional: `pip install -e ".[search]"` (plus `OPENAI_API_KEY`) adds `live_mixing/search.py`'s
hybrid BM25+semantic track search — see `docs/api-reference.md`. Not required for anything else in
this package.

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

`tests/test_search.py` covers `live_mixing/search.py`'s pure-logic corpus building (no network
calls) and auto-skips via `pytest.importorskip` unless the `search` extra is installed.

There is no linter or CI configured — don't invent commands for these.
