# live_mixing — Agent Router

An installable Python package for reading and exporting data from a DJUCED DJ software SQLite
database (`djuced.db`). All logic lives in one module, `live_mixing/read_djuced_db.py`; the only
third-party dependency is `pandas`. This file routes you to the right context — load only what your
task needs.

## Identify Your Task

**CODING (Python)** — adding/extending a function in `read_djuced_db.py`, fixing a bug, changing a
query
→ READ: `coding-rules.md`
→ ALSO READ: `docs/schemas.md` for join-key conventions; `docs/architecture.md` if touching session
reconstruction

**TESTING** — writing new tests or expanding coverage
→ READ: `testing-rules.md`

**DEBUGGING** — a function errors, raises unexpectedly, or output looks wrong (missing tracks, bad
session match, etc.)
→ READ: `debugging-rules.md`
→ ALSO READ: `docs/architecture.md` for the session-reconstruction heuristics

**DATA / QUERY / EXPORT** — exploring the database, running the demo, calling the public API,
exporting CSVs, tracking plays over time (`snapshot_play_log`)
→ READ: `docs/api-reference.md`
→ ALSO READ: `docs/schemas.md` for table shapes; `docs/scripts-reference.md` for how to run things;
`docs/architecture.md` if touching `snapshot_play_log`

## Repo Layout

```
live_mixing/       package: read_djuced_db.py (all logic) + __init__.py (public re-exports)
scripts/           demo.py — runnable walkthrough of every public function
tests/             pytest smoke tests (no real djuced.db required)
data/              generated CSV exports (gitignored, except setlist_session_*.csv — tracked)
docs/              reference docs — see table below
```

Root holds only: `CLAUDE.md`, rule files (`coding-rules.md`, `testing-rules.md`,
`debugging-rules.md`), `README.md`, `pyproject.toml`, `requirements.txt`.

## Reference Docs (load only what your task requires)

| File | Contents |
|---|---|
| `docs/architecture.md` | Session-reconstruction heuristics (`list_sessions`, `match_recording_to_session`) and why they're designed this way |
| `docs/schemas.md` | Database tables and the `tracks.absolutepath` join-key convention |
| `docs/api-reference.md` | Every public function — signature, args, return shape |
| `docs/scripts-reference.md` | Install, demo, and test commands |

## Instructions

1. Identify your task above.
2. Load the rule file for that task.
3. Load only the reference docs the task actually requires.
4. Do not load all docs — load what you need.
5. If unsure which category fits, ask — do not guess.
