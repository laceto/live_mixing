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
