# Testing Rules

- Run with `pytest -q` (see `docs/scripts-reference.md`).
- Tests in `tests/test_read_djuced_db.py` are smoke tests and must not require a real `djuced.db` —
  they check import surface, error handling on a missing db path, and config defaults. Keep new
  tests in this style unless a real fixture database is added deliberately.
- For tests that need actual table data (e.g. `snapshot_play_log`'s diff logic), build a minimal
  synthetic sqlite db in `tmp_path` rather than pointing at a real `djuced.db` — see the
  `_make_tracks_db`/`_set_playcount` helpers in `tests/test_read_djuced_db.py` for the pattern.
- There is no coverage tool, linter, or CI configured for this project — don't invent commands for
  them or assume they exist.
- When adding a new public function, add at minimum an importability check (it's auto-covered if you
  add the name to `__all__` in `live_mixing/__init__.py` — see `coding-rules.md`) and, if it can
  raise on bad input (e.g. missing db path, invalid `session_id`), a test for that error path —
  follow the pattern of `test_read_djuced_db_missing_file_raises`.
