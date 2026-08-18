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
- **`trackCues`** — hot cues / saved loops per track.
- **`trackBeats`** — beatgrid data per track.
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
