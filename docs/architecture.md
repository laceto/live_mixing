# Architecture — Session Reconstruction

DJUCED has **no session/play-log table**. "Sessions" (a continuous DJ set) are reconstructed
heuristically from `tracks.last_played` timestamps. This is the one piece of real design logic in
the package — everything else is straight reads/joins (see `docs/schemas.md` for the join keys).

## `list_sessions(gap_minutes=15)`

Clusters plays by time gap: a gap larger than `gap_minutes` starts a new session.

- 15 min was **empirically tuned** to separate real back-to-back mixing (gaps of tens of seconds to
  a few minutes, matching track length) from library browsing/cueing (gaps of only a few seconds,
  too short to be a real play). Don't change this default without re-validating against real data.
- Because `last_played` stores only the **most recent** play per track, a track replayed after the
  window you're querying won't show up for an earlier session. This is a real, unfixable limitation
  of the data, not a bug — don't try to "fix" it in code.

## `match_recording_to_session()`

Pairs `recordings` rows to detected sessions.

- Recording filenames only carry time-of-day (see `docs/schemas.md`), so multiple sessions on
  different dates can start at a similar clock time.
- Matching is therefore ranked primarily by **duration** closeness (recording length vs. session
  span), not start-time proximity. Start-time proximity was tried first and produced wrong matches —
  a short recording matched a wrong, unrelated multi-hour session purely by start-time coincidence.
- If you touch this function's ranking logic, preserve the duration-first ranking; don't revert to
  start-time-only matching.

## `snapshot_play_log()` — working around the `last_played` limitation

`list_sessions()`/`read_djuced_session()` reconstruct sessions live from `tracks.last_played`, but
that column only ever holds the *most recent* play — if a track gets replayed later, its earlier
session's timestamp is silently overwritten and becomes unrecoverable from `djuced.db` alone (see
above). `snapshot_play_log(log_dir, db_path)` works around this by keeping its own persistent,
append-only record outside the database:

- Each call reads the current `tracks(id, artist, title, absolutepath, last_played, playcount)`
  and diffs it against `log_dir/play_log_state.csv`, the full snapshot saved by the previous call.
- Any track whose `playcount` increased since that snapshot is logged as one play event, appended
  to `log_dir/play_events.csv`. Because this file is append-only, a later replay that overwrites
  `last_played` in `djuced.db` can no longer erase an already-logged event.
- The state file is then overwritten with the current snapshot, ready for the next diff.

Design choices, and why:

- **Multiple plays between two snapshots collapse into a single event** (`playcount_delta` > 1) —
  there's no way to split them into separate timestamps from `playcount` alone. This is why the
  function is meant to be called right after every session: the shorter the gap between snapshots,
  the finer-grained (and more session-attributable) the log.
- **A playcount decrease (db reset/restore) is rebaselined silently, no event is fabricated** —
  consistent with this module's general philosophy of degrading quietly on data anomalies rather
  than raising (see the error-handling patterns for `read_track_cues`/`read_track_beatgrid` on
  unknown tracks).
- **A track with no entry in the previous snapshot is baselined with no event** — there's no prior
  state to diff it against, so attributing a play to it here would be a guess, not a fact.
- **A track missing from the current read (removed from the library) is simply dropped from the
  state** on the next write — nothing is logged for it, and it won't resurface unless re-added.
- This cannot recover plays that happened *before* the workaround was adopted, or plays that
  occurred and were then overwritten before a snapshot was ever taken — it only protects plays
  going forward from the first `snapshot_play_log()` call.
