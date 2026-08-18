import sqlite3

import pandas as pd
import pytest

import live_mixing


def test_public_api_importable():
    for name in live_mixing.__all__:
        assert hasattr(live_mixing, name)


def test_read_djuced_db_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        live_mixing.read_djuced_db(db_path="does/not/exist.db")


def test_default_db_path_is_configurable():
    assert live_mixing.DEFAULT_DB_PATH.name == "djuced.db"


def _make_tracks_db(db_path, rows):
    """rows: list of (id, artist, title, absolutepath, last_played, playcount)."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE tracks (id INTEGER PRIMARY KEY, artist TEXT, title TEXT, "
        "absolutepath TEXT, last_played TEXT, playcount INTEGER)"
    )
    conn.executemany(
        "INSERT INTO tracks (id, artist, title, absolutepath, last_played, playcount) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


def _make_full_tracks_db(db_path, rows):
    """rows: list of (id, artist, title, bpm, key, genre, last_played)."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE tracks (id INTEGER PRIMARY KEY, artist TEXT, title TEXT, "
        "bpm REAL, key INTEGER, genre TEXT, last_played TEXT, absolutepath TEXT)"
    )
    conn.executemany(
        "INSERT INTO tracks (id, artist, title, bpm, key, genre, last_played) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()


def test_current_track_returns_most_recently_played(tmp_path):
    db_path = tmp_path / "djuced.db"
    _make_full_tracks_db(
        db_path,
        [
            (1, "Artist A", "Track A", 120.0, 5, "Techno", "2026-08-15T14:00:00"),
            (2, "Artist B", "Track B", 128.0, 8, "House", "2026-08-15T16:00:00"),
            (3, "Artist C", "Track C", 126.0, 3, "Techno", None),
        ],
    )

    result = live_mixing.current_track(db_path=db_path)

    assert len(result) == 1
    assert result.iloc[0]["artist"] == "Artist B"
    assert result.iloc[0]["title"] == "Track B"


def test_current_track_empty_when_nothing_played(tmp_path):
    db_path = tmp_path / "djuced.db"
    _make_full_tracks_db(
        db_path,
        [(1, "Artist A", "Track A", 120.0, 5, "Techno", None)],
    )

    result = live_mixing.current_track(db_path=db_path)

    assert result.empty


def _set_playcount(db_path, track_id, playcount):
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE tracks SET playcount = ? WHERE id = ?", (playcount, track_id))
    conn.commit()
    conn.close()


def test_snapshot_play_log_first_run_creates_baseline_no_events(tmp_path):
    db_path = tmp_path / "djuced.db"
    _make_tracks_db(
        db_path,
        [
            (1, "Artist A", "Track A", "/a.mp3", None, 0),
            (2, "Artist B", "Track B", "/b.mp3", None, 3),
        ],
    )
    log_dir = tmp_path / "play_log"

    events = live_mixing.snapshot_play_log(log_dir=log_dir, db_path=db_path)

    assert events.empty
    assert list(events.columns) == [
        "event_detected_at", "id", "artist", "title", "absolutepath",
        "playcount_before", "playcount_after", "playcount_delta", "last_played",
    ]
    assert (log_dir / "play_log_state.csv").exists()
    assert not (log_dir / "play_events.csv").exists()

    state = pd.read_csv(log_dir / "play_log_state.csv")
    assert sorted(state["id"]) == [1, 2]


def test_snapshot_play_log_detects_new_plays(tmp_path):
    db_path = tmp_path / "djuced.db"
    _make_tracks_db(
        db_path,
        [
            (1, "Artist A", "Track A", "/a.mp3", None, 0),
            (2, "Artist B", "Track B", "/b.mp3", None, 3),
        ],
    )
    log_dir = tmp_path / "play_log"
    live_mixing.snapshot_play_log(log_dir=log_dir, db_path=db_path)  # baseline

    _set_playcount(db_path, track_id=2, playcount=5)  # played twice since baseline
    events = live_mixing.snapshot_play_log(log_dir=log_dir, db_path=db_path)

    assert len(events) == 1
    row = events.iloc[0]
    assert row["id"] == 2
    assert row["playcount_before"] == 3
    assert row["playcount_after"] == 5
    assert row["playcount_delta"] == 2

    logged = pd.read_csv(log_dir / "play_events.csv")
    assert len(logged) == 1
    assert logged.iloc[0]["id"] == 2

    # a third snapshot with no further change logs nothing new
    more_events = live_mixing.snapshot_play_log(log_dir=log_dir, db_path=db_path)
    assert more_events.empty
    assert len(pd.read_csv(log_dir / "play_events.csv")) == 1


def test_snapshot_play_log_ignores_playcount_decrease(tmp_path):
    db_path = tmp_path / "djuced.db"
    _make_tracks_db(db_path, [(1, "Artist A", "Track A", "/a.mp3", None, 10)])
    log_dir = tmp_path / "play_log"
    live_mixing.snapshot_play_log(log_dir=log_dir, db_path=db_path)  # baseline at 10

    _set_playcount(db_path, track_id=1, playcount=2)  # e.g. db restore/reset
    events = live_mixing.snapshot_play_log(log_dir=log_dir, db_path=db_path)

    assert events.empty
    assert not (log_dir / "play_events.csv").exists()
    state = pd.read_csv(log_dir / "play_log_state.csv")
    assert state.loc[state["id"] == 1, "playcount"].iloc[0] == 2


def test_snapshot_play_log_handles_new_and_removed_tracks(tmp_path):
    db_path = tmp_path / "djuced.db"
    _make_tracks_db(
        db_path,
        [
            (1, "Artist A", "Track A", "/a.mp3", None, 0),
            (2, "Artist B", "Track B", "/b.mp3", None, 0),
        ],
    )
    log_dir = tmp_path / "play_log"
    live_mixing.snapshot_play_log(log_dir=log_dir, db_path=db_path)  # baseline: tracks 1, 2

    # track 2 removed from the library, track 3 newly added
    conn = sqlite3.connect(db_path)
    conn.execute("DELETE FROM tracks WHERE id = 2")
    conn.execute(
        "INSERT INTO tracks (id, artist, title, absolutepath, last_played, playcount) "
        "VALUES (3, 'Artist C', 'Track C', '/c.mp3', NULL, 7)"
    )
    conn.commit()
    conn.close()

    events = live_mixing.snapshot_play_log(log_dir=log_dir, db_path=db_path)

    assert events.empty  # new track has no prior baseline to diff against
    state = pd.read_csv(log_dir / "play_log_state.csv")
    assert sorted(state["id"]) == [1, 3]  # track 2 dropped, track 3 baselined


def _make_tracks_and_cues_db(db_path, cue_rows):
    """cue_rows: list of (trackId, cuename, cuenumber, cuepos, loopLength, cueColor, isSavedLoop)."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE tracks (id INTEGER PRIMARY KEY, artist TEXT, title TEXT, absolutepath TEXT)"
    )
    conn.execute(
        "INSERT INTO tracks (id, artist, title, absolutepath) VALUES (1, 'Artist A', 'Track A', '/a.mp3')"
    )
    conn.execute(
        "CREATE TABLE trackCues (id INTEGER PRIMARY KEY, trackId TEXT, cuename TEXT, "
        "cuenumber INTEGER, cuepos REAL, loopLength REAL, cueColor INTEGER, isSavedLoop INTEGER)"
    )
    conn.executemany(
        "INSERT INTO trackCues (trackId, cuename, cuenumber, cuepos, loopLength, cueColor, isSavedLoop) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        cue_rows,
    )
    conn.commit()
    conn.close()


def test_read_track_cues_excludes_structure_markers_by_default(tmp_path):
    db_path = tmp_path / "djuced.db"
    _make_tracks_and_cues_db(
        db_path,
        [
            ("/a.mp3", "Cue 0", 0, 0.5, 0, 4, 0),      # real: memory cue
            ("/a.mp3", "Cue 1", 1, 10.0, 0, 4, 0),     # real: hot cue pad 1
            ("/a.mp3", "9", 1000, 20.0, 0, 4, 0),      # auto structure marker
            ("/a.mp3", "12", 1007, 90.0, 0, 4, 0),     # auto structure marker
        ],
    )

    real_only = live_mixing.read_track_cues(db_path=db_path)
    assert len(real_only) == 2
    assert sorted(real_only["cuenumber"]) == [0, 1]

    everything = live_mixing.read_track_cues(db_path=db_path, include_structure_markers=True)
    assert len(everything) == 4
