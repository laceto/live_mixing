import sqlite3
from pathlib import Path

import pandas as pd

DEFAULT_DB_PATH = Path.home() / "Documents" / "DJUCED" / "djuced.db"


def read_djuced_db(db_path=DEFAULT_DB_PATH, table="tracks", query=None):
    """Read a table (or custom query) from a DJUCED SQLite database into a DataFrame.

    Args:
        db_path: path to djuced.db.
        table: table name to read (default "tracks"). Ignored if `query` is given.
        query: optional raw SQL query, used instead of `table`.

    Returns:
        pandas.DataFrame with the query/table contents.
    """
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"DJUCED database not found: {db_path}")

    sql = query if query is not None else f"SELECT * FROM {table}"

    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(sql, conn)


def read_djuced_playlists(db_path=DEFAULT_DB_PATH):
    """Read the playlists2 table from a DJUCED SQLite database into a DataFrame.

    Args:
        db_path: path to djuced.db.

    Returns:
        pandas.DataFrame with the playlists2 table contents.
    """
    return read_djuced_db(db_path, table="playlists2")


def read_djuced_playlist_tracks(db_path=DEFAULT_DB_PATH):
    """Join playlists2 and tracks to map each playlist to its tracks.

    Only playlists2 rows with type == 3 hold an actual track reference, whose
    `data` column matches `tracks.absolutepath`.

    Args:
        db_path: path to djuced.db.

    Returns:
        pandas.DataFrame with one row per (playlist, track), the playlist's
        `name` and `order_in_list`, plus all columns from `tracks`.
    """
    query = """
        SELECT p.name AS playlist_name, p.order_in_list, t.*
        FROM playlists2 AS p
        JOIN tracks AS t ON t.absolutepath = p.data
        WHERE p.type = 3
        ORDER BY p.name, p.order_in_list
    """
    return read_djuced_db(db_path, query=query)


def read_track_cues(db_path=DEFAULT_DB_PATH, track_absolutepath=None):
    """Read hot cues / saved loops from trackCues, joined with track info.

    `trackCues.trackId` matches `tracks.absolutepath`.

    Args:
        db_path: path to djuced.db.
        track_absolutepath: if given, restrict to this one track (its
            `absolutepath`). If None (default), return cues for all tracks.

    Returns:
        pandas.DataFrame with artist, title, cuename, cuenumber, cuepos,
        loopLength, cueColor, isSavedLoop.
    """
    query = """
        SELECT t.artist, t.title, c.cuename, c.cuenumber, c.cuepos,
               c.loopLength, c.cueColor, c.isSavedLoop
        FROM trackCues AS c
        JOIN tracks AS t ON t.absolutepath = c.trackId
    """
    params = []
    if track_absolutepath is not None:
        query += " WHERE t.absolutepath = ?"
        params.append(track_absolutepath)
    query += " ORDER BY t.artist, t.title, c.cuenumber"

    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"DJUCED database not found: {db_path}")

    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(query, conn, params=params)


def read_track_beatgrid(db_path=DEFAULT_DB_PATH, track_absolutepath=None):
    """Read beatgrid info from trackBeats, joined with track info.

    `trackBeats.trackId` matches `tracks.absolutepath`.

    Args:
        db_path: path to djuced.db.
        track_absolutepath: if given, restrict to this one track (its
            `absolutepath`). If None (default), return beatgrid rows for all
            tracks.

    Returns:
        pandas.DataFrame with artist, title, timesignature, downbeat, grid,
        auftakt, beatpos (raw bytes — a small packed blob, size varies per
        track and isn't a simple scalar).
    """
    query = """
        SELECT t.artist, t.title, b.timesignature, b.downbeat, b.grid,
               b.auftakt, b.beatpos
        FROM trackBeats AS b
        JOIN tracks AS t ON t.absolutepath = b.trackId
    """
    params = []
    if track_absolutepath is not None:
        query += " WHERE t.absolutepath = ?"
        params.append(track_absolutepath)
    query += " ORDER BY t.artist, t.title"

    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"DJUCED database not found: {db_path}")

    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(query, conn, params=params)


def read_djuced_session(db_path=DEFAULT_DB_PATH, start=None, end=None):
    """Reconstruct a play session from tracks.last_played timestamps.

    DJUCED stamps `last_played` on a track each time it's played, so filtering
    tracks by that timestamp range reconstructs the setlist/order for a
    session. Note `last_played` holds only the most recent play per track, so
    a track replayed after `end` won't show up for an earlier session.

    Args:
        db_path: path to djuced.db.
        start: session start, e.g. "2026-08-15T15:04" (inclusive).
        end: session end, e.g. "2026-08-15T17:13" (inclusive).

    Returns:
        pandas.DataFrame of tracks played in [start, end], ordered by
        last_played.
    """
    query = "SELECT * FROM tracks WHERE 1=1"
    params = []
    if start is not None:
        query += " AND last_played >= ?"
        params.append(start)
    if end is not None:
        query += " AND last_played <= ?"
        params.append(end)
    query += " ORDER BY last_played"

    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"DJUCED database not found: {db_path}")

    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(query, conn, params=params)


def list_sessions(db_path=DEFAULT_DB_PATH, gap_minutes=15):
    """Auto-detect DJ session boundaries across the whole play history.

    Clusters tracks.last_played timestamps: a new session starts whenever the
    gap since the previous play exceeds `gap_minutes` (default 15, tuned to
    separate real back-to-back mixing from library browsing/cueing, where
    gaps between plays are only a few seconds).

    Args:
        db_path: path to djuced.db.
        gap_minutes: minutes of silence that splits two plays into separate
            sessions.

    Returns:
        pandas.DataFrame with one row per detected session: session_id, date,
        start, end, duration_min, n_tracks.
    """
    tracks = read_djuced_db(
        db_path,
        query="""
            SELECT artist, title, last_played
            FROM tracks
            WHERE last_played IS NOT NULL
            ORDER BY last_played
        """,
    )
    tracks["last_played"] = pd.to_datetime(tracks["last_played"])
    gap_seconds = tracks["last_played"].diff().dt.total_seconds()
    tracks["session_id"] = (gap_seconds > gap_minutes * 60).cumsum()

    sessions = tracks.groupby("session_id").agg(
        date=("last_played", lambda s: s.iloc[0].date()),
        start=("last_played", "min"),
        end=("last_played", "max"),
        n_tracks=("title", "count"),
    )
    sessions["duration_min"] = (
        (sessions["end"] - sessions["start"]).dt.total_seconds() / 60
    ).round(1)
    return sessions.reset_index()


def match_recording_to_session(
    db_path=DEFAULT_DB_PATH,
    gap_minutes=15,
    start_tolerance_minutes=30,
    ambiguous_margin_seconds=300,
):
    """Match each recorded mix in `recordings` to a detected session.

    `recordings.recordId` filenames only encode a time-of-day range (e.g.
    "My Mix - 15h04m49s to 17h13m16s.mp3"), no date, so several sessions on
    different dates can coincidentally start around the same time of day.
    Session *duration* is a much more discriminating signal than start time
    alone (a recording's length rarely matches an unrelated session by
    chance), so candidates are first shortlisted by start-time-of-day
    proximity, then ranked by closeness of session duration to recording
    duration.

    Args:
        db_path: path to djuced.db.
        gap_minutes: passed through to list_sessions().
        start_tolerance_minutes: max difference between recording start time
            and session start time (both time-of-day only) to shortlist a
            session as a candidate. Wide by default since recording can start
            several tracks after the actual set (see list_sessions).
        ambiguous_margin_seconds: if a second candidate's duration is within
            this many seconds of the best candidate's, the match is flagged
            ambiguous.

    Returns:
        pandas.DataFrame with one row per recording: recording_path,
        rec_start, rec_end, session_id, session_date, session_start,
        session_end, n_tracks, match (bool), ambiguous (bool).
    """
    import re

    recordings = read_djuced_db(db_path, table="recordings")
    sessions = list_sessions(db_path, gap_minutes=gap_minutes)
    session_duration_secs = (sessions["end"] - sessions["start"]).dt.total_seconds()
    session_start_secs = (
        sessions["start"].dt.hour * 3600
        + sessions["start"].dt.minute * 60
        + sessions["start"].dt.second
    )

    pattern = re.compile(
        r"My Mix - (\d{2})h(\d{2})m(\d{2})s to (\d{2})h(\d{2})m(\d{2})s"
    )

    empty_match = {
        "session_id": None,
        "session_date": None,
        "session_start": None,
        "session_end": None,
        "n_tracks": None,
        "match": False,
        "ambiguous": False,
    }

    results = []
    for _, rec in recordings.iterrows():
        m = pattern.search(rec["recordId"])
        if not m:
            results.append({"recording_path": rec["recordId"], "rec_start": None, "rec_end": None, **empty_match})
            continue

        rh, rmi, rs, eh, emi, es = (int(g) for g in m.groups())
        rec_start_secs = rh * 3600 + rmi * 60 + rs
        rec_end_secs = eh * 3600 + emi * 60 + es
        rec_duration_secs = rec_end_secs - rec_start_secs
        if rec_duration_secs < 0:  # crosses midnight
            rec_duration_secs += 24 * 3600
        rec_label = {
            "rec_start": f"{rh:02d}:{rmi:02d}:{rs:02d}",
            "rec_end": f"{eh:02d}:{emi:02d}:{es:02d}",
        }

        start_diff_secs = (session_start_secs - rec_start_secs).abs()
        candidates = sessions[start_diff_secs <= start_tolerance_minutes * 60]

        if candidates.empty:
            results.append({"recording_path": rec["recordId"], **rec_label, **empty_match})
            continue

        duration_diff_secs = (
            session_duration_secs.loc[candidates.index] - rec_duration_secs
        ).abs()
        ranked = duration_diff_secs.sort_values()
        best = sessions.loc[ranked.index[0]]
        ambiguous = (
            len(ranked) > 1 and (ranked.iloc[1] - ranked.iloc[0]) <= ambiguous_margin_seconds
        )

        results.append(
            {
                "recording_path": rec["recordId"],
                **rec_label,
                "session_id": best["session_id"],
                "session_date": best["date"],
                "session_start": best["start"],
                "session_end": best["end"],
                "n_tracks": best["n_tracks"],
                "match": True,
                "ambiguous": ambiguous,
            }
        )

    return pd.DataFrame(results)


def find_missing_files(db_path=DEFAULT_DB_PATH):
    """Find tracks whose absolutepath no longer exists on disk.

    Useful after moving/renaming/deleting music folders — DJUCED keeps stale
    references in the library until they're re-scanned or removed.

    Args:
        db_path: path to djuced.db.

    Returns:
        pandas.DataFrame (subset of tracks columns: id, artist, title,
        absolutepath) for tracks whose file is missing.
    """
    tracks = read_djuced_db(
        db_path, query="SELECT id, artist, title, absolutepath FROM tracks"
    )
    missing = tracks[~tracks["absolutepath"].apply(lambda p: Path(p).exists())]
    return missing.reset_index(drop=True)


def top_played_tracks(n=20, db_path=DEFAULT_DB_PATH):
    """Return the n most-played tracks by playcount.

    Args:
        n: number of tracks to return.
        db_path: path to djuced.db.

    Returns:
        pandas.DataFrame (artist, title, playcount, last_played) sorted by
        playcount descending.
    """
    return read_djuced_db(
        db_path,
        query=f"""
            SELECT artist, title, playcount, last_played
            FROM tracks
            ORDER BY playcount DESC
            LIMIT {int(n)}
        """,
    )


def export_playlists_csv(csv_path, db_path=DEFAULT_DB_PATH):
    """Export the full playlists2 table to CSV.

    Args:
        csv_path: output CSV file path.
        db_path: path to djuced.db.

    Returns:
        pandas.DataFrame with all playlists2 rows that was written to `csv_path`.
    """
    playlists = read_djuced_playlists(db_path)
    playlists.to_csv(csv_path, index=False)
    return playlists


def export_tracks_csv(csv_path, db_path=DEFAULT_DB_PATH, include_waveform=False):
    """Export the full tracks table to CSV.

    Args:
        csv_path: output CSV file path.
        db_path: path to djuced.db.
        include_waveform: if False (default), drops the `waveform` column —
            an ~8KB binary blob per track that isn't meaningful as CSV text.

    Returns:
        pandas.DataFrame with all tracks that was written to `csv_path`.
    """
    tracks = read_djuced_db(db_path, table="tracks")
    if not include_waveform:
        tracks = tracks.drop(columns=["waveform"])
    tracks.to_csv(csv_path, index=False)
    return tracks


def export_setlist_csv(csv_path, db_path=DEFAULT_DB_PATH, start=None, end=None):
    """Export a reconstructed setlist (see read_djuced_session) to CSV.

    Args:
        csv_path: output CSV file path.
        db_path: path to djuced.db.
        start: session start, e.g. "2026-08-15T15:04" (inclusive).
        end: session end, e.g. "2026-08-15T17:13" (inclusive).

    Returns:
        pandas.DataFrame with columns [last_played, artist, title] that was
        written to `csv_path`.
    """
    session = read_djuced_session(db_path, start=start, end=end)
    setlist = session[["last_played", "artist", "title"]].rename(
        columns={"last_played": "timestamp"}
    )
    setlist.to_csv(csv_path, index=False)
    return setlist


def export_session_setlist_csv(session_id, csv_path=None, db_path=DEFAULT_DB_PATH, gap_minutes=15):
    """Export the setlist of one detected session (see list_sessions) to CSV.

    Args:
        session_id: session_id from list_sessions() to export.
        csv_path: output CSV file path. If None (default), generated as
            "setlist_session_<session_id>_<date>.csv".
        db_path: path to djuced.db.
        gap_minutes: passed through to list_sessions().

    Returns:
        pandas.DataFrame with columns [timestamp, artist, title] that was
        written to `csv_path`.

    Raises:
        ValueError: if session_id doesn't match any detected session.
    """
    sessions = list_sessions(db_path, gap_minutes=gap_minutes)
    match = sessions[sessions["session_id"] == session_id]
    if match.empty:
        raise ValueError(f"No session with session_id={session_id!r}")
    session = match.iloc[0]

    if csv_path is None:
        csv_path = f"setlist_session_{session_id}_{session['date']}.csv"

    return export_setlist_csv(
        csv_path,
        db_path=db_path,
        start=session["start"].isoformat(),
        end=session["end"].isoformat(),
    )


def export_sessions_csv(csv_path, db_path=DEFAULT_DB_PATH, gap_minutes=15):
    """Export detected session boundaries (see list_sessions) to CSV.

    Args:
        csv_path: output CSV file path.
        db_path: path to djuced.db.
        gap_minutes: passed through to list_sessions().

    Returns:
        pandas.DataFrame with columns [session_id, date, start, end,
        n_tracks, duration_min] that was written to `csv_path`.
    """
    sessions = list_sessions(db_path, gap_minutes=gap_minutes)
    sessions.to_csv(csv_path, index=False)
    return sessions
