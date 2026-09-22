import sqlite3

import pytest

pytest.importorskip("kitai")
pytest.importorskip("langchain_core")

from live_mixing import search  # noqa: E402


def _make_playlist_tracks_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE tracks (id INTEGER PRIMARY KEY, artist TEXT, title TEXT, "
        "album TEXT, absolutepath TEXT)"
    )
    conn.execute(
        "CREATE TABLE playlists2 (name TEXT, path TEXT, data TEXT, "
        "order_in_list INTEGER, type INTEGER)"
    )
    conn.executemany(
        "INSERT INTO tracks (id, artist, title, album, absolutepath) VALUES (?, ?, ?, ?, ?)",
        [
            (1, "Andy Lee", "Lope", None, "/lope.mp3"),
            (2, "Ambivalent", "Nuggets", "R U OK", "/nuggets.mp3"),
        ],
    )
    conn.executemany(
        "INSERT INTO playlists2 (name, path, data, order_in_list, type) VALUES (?, '#', ?, ?, 3)",
        [
            ("20260804", "/lope.mp3", 1),
            ("trip", "/nuggets.mp3", 1),
            ("late night", "/nuggets.mp3", 1),
        ],
    )
    conn.commit()
    conn.close()


def test_build_track_documents_dedups_by_absolutepath_and_collects_playlists(tmp_path):
    db_path = tmp_path / "djuced.db"
    _make_playlist_tracks_db(db_path)

    docs = search.build_track_documents(db_path=db_path)

    assert len(docs) == 2
    by_id = {d.metadata["id"]: d for d in docs}
    assert by_id["/lope.mp3"].metadata["playlists"] == ["20260804"]
    assert by_id["/lope.mp3"].page_content == "Lope — Andy Lee"
    assert by_id["/nuggets.mp3"].metadata["playlists"] == ["late night", "trip"]
    assert by_id["/nuggets.mp3"].page_content == "Nuggets — Ambivalent — R U OK"


def test_build_track_documents_empty_when_no_playlists(tmp_path):
    db_path = tmp_path / "djuced.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE tracks (id INTEGER PRIMARY KEY, artist TEXT, title TEXT, "
        "album TEXT, absolutepath TEXT)"
    )
    conn.execute(
        "CREATE TABLE playlists2 (name TEXT, path TEXT, data TEXT, "
        "order_in_list INTEGER, type INTEGER)"
    )
    conn.commit()
    conn.close()

    assert search.build_track_documents(db_path=db_path) == []
