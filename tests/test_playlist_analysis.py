import json
import os
from types import SimpleNamespace

import pandas as pd
import pytest

from live_mixing import playlist_analysis as pa


def _fake_client(payload, calls=None):
    """Stand-in for openai.OpenAI: chat.completions.create returns `payload` as JSON content."""

    def create(**kwargs):
        if calls is not None:
            calls.append(kwargs)
        message = SimpleNamespace(content=json.dumps(payload))
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def _tracks():
    return pd.DataFrame(
        {
            "artist": ["A1", "A2", "A3", "A4"],
            "title": ["T1", "T2", "T3", "T4"],
        }
    )


def test_read_playlist_file_parses_lines(tmp_path):
    f = tmp_path / "p.txt"
    f.write_text(
        "Artist One,Title One,1\n"
        "\n"
        "Artist Two,Title, with comma,1\n"
        "Artist Three,No Count\n"
        "garbage-line-without-comma\n",
        encoding="utf-8",
    )

    df = pa.read_playlist_file(f)

    assert list(df["artist"]) == ["Artist One", "Artist Two", "Artist Three"]
    assert list(df["title"]) == ["Title One", "Title, with comma", "No Count"]


def test_read_playlist_file_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        pa.read_playlist_file(tmp_path / "nope.txt")


def test_load_env_file_sets_new_vars_without_overriding(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text(
        "# comment\n"
        "\n"
        "LM_TEST_NEW=abc\n"
        'LM_TEST_QUOTED="with quotes"\n'
        "export LM_TEST_EXPORT='single'\n"
        "LM_TEST_EXISTING=from_file\n"
        "not a valid line\n",
        encoding="utf-8",
    )
    for name in ("LM_TEST_NEW", "LM_TEST_QUOTED", "LM_TEST_EXPORT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LM_TEST_EXISTING", "from_env")

    loaded = pa.load_env_file(env)

    assert sorted(loaded) == ["LM_TEST_EXPORT", "LM_TEST_NEW", "LM_TEST_QUOTED"]
    assert os.environ["LM_TEST_NEW"] == "abc"
    assert os.environ["LM_TEST_QUOTED"] == "with quotes"
    assert os.environ["LM_TEST_EXPORT"] == "single"
    assert os.environ["LM_TEST_EXISTING"] == "from_env"
    for name in ("LM_TEST_NEW", "LM_TEST_QUOTED", "LM_TEST_EXPORT"):
        monkeypatch.delenv(name)


def test_load_env_file_missing_returns_empty(tmp_path):
    assert pa.load_env_file(tmp_path / "nope.env") == []


def test_analyze_playlist_empty_raises():
    with pytest.raises(ValueError):
        pa.analyze_playlist(pd.DataFrame(columns=["artist", "title"]), client=_fake_client({}))


def test_analyze_playlist_orders_by_phase_and_maps_tracks():
    payload = {
        "journey": "A slow-burning minimal journey.",
        "phases": [
            # deliberately out of phase order: result must be sorted warm_up -> breakdown
            {"phase": "peak", "tracks": [{"number": 4, "known": True, "reason": "biggest"}]},
            {"phase": "warm_up", "tracks": [{"number": 2, "known": True, "reason": "gentle"}]},
            {"phase": "breakdown", "tracks": [{"number": 1, "known": True, "reason": "release"}]},
            {"phase": "building", "tracks": [{"number": 3, "known": True, "reason": "rising"}]},
        ],
    }
    calls = []

    result = pa.analyze_playlist(_tracks(), client=_fake_client(payload, calls), model="m-test")

    assert result["journey"] == "A slow-burning minimal journey."
    order = result["set_order"]
    assert list(order["phase"]) == ["warm_up", "building", "peak", "breakdown"]
    assert list(order["title"]) == ["T2", "T3", "T4", "T1"]
    assert list(order["position"]) == [1, 2, 3, 4]
    assert list(order["known"]) == [True, True, True, True]
    assert result["unassigned"] == []
    assert calls[0]["model"] == "m-test"
    assert "1. A1 - T1" in calls[0]["messages"][1]["content"]


def test_analyze_playlist_forwards_temperature_with_default_and_override():
    payload = {"journey": "j", "phases": [{"phase": "peak", "tracks": [{"number": 1, "known": True, "reason": "r"}]}]}
    calls = []

    pa.analyze_playlist(_tracks(), client=_fake_client(payload, calls))
    pa.analyze_playlist(_tracks(), client=_fake_client(payload, calls), temperature=0.5)

    assert calls[0]["temperature"] == pa.DEFAULT_TEMPERATURE == 0.2
    assert calls[1]["temperature"] == 0.5


def test_analyze_playlist_ignores_invented_and_duplicate_numbers_and_reports_unassigned():
    payload = {
        "journey": "j",
        "phases": [
            {
                "phase": "warm_up",
                "tracks": [
                    {"number": 1, "known": True, "reason": "ok"},
                    {"number": 99, "known": True, "reason": "invented"},
                    {"number": 1, "known": True, "reason": "duplicate"},
                ],
            },
            {"phase": "peak", "tracks": [{"number": 2, "known": True, "reason": "ok"}]},
        ],
    }

    result = pa.analyze_playlist(_tracks(), client=_fake_client(payload))

    assert list(result["set_order"]["title"]) == ["T1", "T2"]
    assert result["unassigned"] == ["A3 - T3", "A4 - T4"]


def test_analyze_playlist_reads_path(tmp_path):
    f = tmp_path / "p.txt"
    f.write_text("Only Artist,Only Title,1\n", encoding="utf-8")
    payload = {
        "journey": "j",
        "phases": [{"phase": "peak", "tracks": [{"number": 1, "known": True, "reason": "r"}]}],
    }

    result = pa.analyze_playlist(f, client=_fake_client(payload))

    assert list(result["set_order"]["artist"]) == ["Only Artist"]


def test_analyze_playlist_prompt_labels_inference_and_carries_known_flag():
    payload = {
        "journey": "j",
        "phases": [
            {
                "phase": "building",
                "tracks": [
                    {"number": 1, "known": True, "reason": "recognised"},
                    {"number": 2, "known": False, "reason": "Not known - inferred: same artist style."},
                ],
            },
        ],
    }
    calls = []

    result = pa.analyze_playlist(_tracks().head(2), client=_fake_client(payload, calls))

    system, user = (m["content"] for m in calls[0]["messages"])
    assert "best-effort inference" in system
    assert "Never invent specifics" in system
    assert "Not known - inferred" in user
    assert "`known`" in user
    assert list(result["set_order"]["known"]) == [True, False]
    schema_item = calls[0]["response_format"]["json_schema"]["schema"]["properties"]["phases"]["items"]
    assert "known" in schema_item["properties"]["tracks"]["items"]["required"]
