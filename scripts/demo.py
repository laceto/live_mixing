"""Demo/smoke-test driver: exercises every public function in live_mixing.

Run from the project root:
    python scripts/demo.py

Writes its CSV exports into data/. Session 90 (2026-08-15) is hardcoded as an
example — adjust to a session_id from your own list_sessions() output.
"""

from live_mixing import (
    export_playlists_csv,
    export_session_setlist_csv,
    export_sessions_csv,
    export_setlist_csv,
    export_tracks_csv,
    find_missing_files,
    list_sessions,
    match_recording_to_session,
    read_djuced_db,
    read_djuced_playlist_tracks,
    read_djuced_playlists,
    read_djuced_session,
    read_track_beatgrid,
    read_track_cues,
    top_played_tracks,
)

DATA_DIR = "data"


def main():
    tracks = read_djuced_db()
    print(tracks.shape)
    print(tracks.head())

    playlists = read_djuced_playlists()
    print(playlists.shape)
    print(playlists.head())

    playlist_tracks = read_djuced_playlist_tracks()
    print(playlist_tracks.shape)
    print(playlist_tracks[["playlist_name", "order_in_list", "title", "artist"]].head())

    session = read_djuced_session(start="2026-08-15T14:57", end="2026-08-15T17:13")
    print(session.shape)
    print(session[["last_played", "artist", "title"]])

    setlist = export_setlist_csv(
        f"{DATA_DIR}/setlist_2026-08-15.csv", start="2026-08-15T14:57", end="2026-08-15T17:13"
    )
    print(setlist)

    all_tracks = export_tracks_csv(f"{DATA_DIR}/tracks_export.csv")
    print(all_tracks.shape)

    all_playlists = export_playlists_csv(f"{DATA_DIR}/playlists_export.csv")
    print(all_playlists.shape)

    sessions = list_sessions()
    print(sessions.shape)
    print(sessions)

    matches = match_recording_to_session()
    print(matches.shape)
    print(matches)

    missing = find_missing_files()
    print(missing.shape)
    print(missing.head())

    top = top_played_tracks(10)
    print(top)

    cues = read_track_cues(
        track_absolutepath="C:/Program Files/DJUCED/Demo/DJUCED - House vol1.mp3"
    )
    print(cues.shape)
    print(cues)

    beatgrid = read_track_beatgrid(
        track_absolutepath="C:/Program Files/DJUCED/Demo/LOOPMASTER_ShotsAndBeats/UGE_Gunshot_02.wav"
    )
    print(beatgrid.shape)
    print(beatgrid)

    sessions_csv = export_sessions_csv(f"{DATA_DIR}/sessions_export.csv")
    print(sessions_csv.shape)

    session_setlist = export_session_setlist_csv(90, csv_path=f"{DATA_DIR}/setlist_session_90_2026-08-15.csv")
    print(session_setlist)


if __name__ == "__main__":
    main()
