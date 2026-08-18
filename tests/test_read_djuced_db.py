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
