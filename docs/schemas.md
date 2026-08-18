# Database Schema — djuced.db

SQLite database, default location `~/Documents/DJUCED/djuced.db` (overridable via `db_path` on
every function).

## Tables

- **`tracks`** — the music library (artist/title/genre/bpm/key/rating/playcount/`last_played`/
  `absolutepath`/`waveform` blob, etc.). `waveform` is an ~8KB binary blob per row — always excluded
  from CSV export by default (`export_tracks_csv(..., include_waveform=False)`).
- **`playlists2`** — mixed-purpose table distinguished by `type`:
  - `type=0` — playlist/crate name header rows
  - `type=3` — actual track entries (their `data` column holds the track's file path)
  - `type=5` — a single special "AllSongsUnalyzed" marker row
- **`trackCues`** — hot cues / saved loops per track, but **`cuenumber` spans two unrelated
  ranges** (reverse-engineered independently by
  [DjucedToRekordBoxXML](https://github.com/binomed/DjucedToRekordBoxXML), cross-checked against
  this package's own library): `0..8` are real cue points a DJ placed (`0` = memory/main cue,
  `1..8` = hot cue pads 1-8); `1000+` are DJUCED's own auto-detected track-structure markers —
  never something a user placed, and the large majority of rows in this table (91% in this
  package's own library: 9,598 of 10,542). `read_track_cues()` filters to `cuenumber < 1000` by
  default — don't query this table directly without that filter, or "cues" will mostly be noise.
- **`trackBeats`** — beatgrid data per track. `timesignature` is unreliable — don't build logic on
  it (checked against this package's real data: only ~53% of rows are `0`, the rest are
  large/garbage-looking values with no discernible pattern).
- **`recordings`** — paths to recorded mix audio files, named like
  `"My Mix - 15h04m49s to 17h13m16s.mp3"` — **time-of-day only, no date**.
- **`samples`, `temporary`, `tblFolderScan`, `tblAdmin`** — minor/auxiliary tables, not covered by
  dedicated read functions.

## Join key convention

`tracks.absolutepath` is the join key **everywhere**:

- `playlists2.data` (for `type=3` rows) matches `tracks.absolutepath`
- `trackCues.trackId` matches `tracks.absolutepath`
- `trackBeats.trackId` matches `tracks.absolutepath`

None of these join against `tracks.id`. Any new query joining to `tracks` should use
`absolutepath`, not `id`, unless you've verified otherwise.
