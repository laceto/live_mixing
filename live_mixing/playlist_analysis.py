"""
live_mixing/playlist_analysis.py
================================
Optional OpenAI-powered playlist analysis. NOT part of the pandas-only core — nothing in
`live_mixing/__init__.py` imports this module, so `import live_mixing` never needs `openai`.
Import it explicitly: `from live_mixing import playlist_analysis`.

Install:
    pip install -e ".[analysis]"

Requires OPENAI_API_KEY, taken from the environment or, if unset, from a `.env` file (see
`load_env_file`), or pass your own `openai.OpenAI` client. `.env` is read only when
`analyze_playlist()` has to create the client — never at import time — and it never overrides
variables that are already set.

    read_playlist_file()   "Artist,Title,1" text file -> DataFrame (artist, title)
        |
    analyze_playlist()     tracks -> OpenAI -> journey description + set order by phase
"""

import json
import os
from pathlib import Path

import pandas as pd

DEFAULT_PLAYLIST_PATH = Path("data") / "now_playing.txt"
# Looked up in order: current directory, then the repo root (editable installs).
DEFAULT_ENV_PATHS = (Path(".env"), Path(__file__).resolve().parent.parent / ".env")
DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_TEMPERATURE = 0.2
DEFAULT_CONTEXT = (
    "techno, minimal and tech house from the minimal era (roughly 2004-2012)"
)
PHASES = ("warm_up", "building", "peak", "breakdown")
TAG_COLUMNS = ("genre", "texture", "energy", "role", "context")

_SYSTEM_PROMPT = (
    "You are an experienced club DJ and music historian working in the field of {context}. You "
    "are given a numbered playlist. For every track, first decide whether you genuinely recognise "
    "that exact record (this artist, title and remix/version). If you do, describe it from that "
    "knowledge. If you do not, you may make a reasonable, best-effort inference from what you do "
    "know — the artist's usual style, the label, the era, the remix credit, the rest of the "
    "playlist — but you must say plainly that the track is not known to you and that your "
    "comments are an inference, never presenting a guess as fact. Never invent specifics such as "
    "a label, year, BPM or key. Use the track numbers exactly as given."
)

_USER_PROMPT = (
    "Playlist:\n{tracks}\n\n"
    "1. Describe the overall journey the DJ has created with this playlist: mood, energy arc, "
    "sound palette, and what kind of set or venue it suits. Cover the whole playlist, but make "
    "clear which parts rest on tracks you know and which on inference about tracks you do not, "
    "and say how many tracks you do not know.\n"
    "2. Propose the order of these tracks for a DJ set, split into four phases in this order: "
    "warm_up, building, peak, breakdown. Give each track's number once, in play order within its "
    "phase, and set `known` to true only if you genuinely recognise the record. For a known "
    "track, give a short reason (energy/groove/role in the set) from what you know about it. For "
    "an unknown track, set `known` to false and start the reason with 'Not known - inferred: ' "
    "followed by your best-effort reasoning for placing it. Every track must be placed in "
    "exactly one phase."
)

_RESPONSE_SCHEMA = {
    "name": "playlist_analysis",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": ["journey", "phases"],
        "properties": {
            "journey": {"type": "string"},
            "phases": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["phase", "tracks"],
                    "properties": {
                        "phase": {"type": "string", "enum": list(PHASES)},
                        "tracks": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["number", "known", "reason"],
                                "properties": {
                                    "number": {"type": "integer"},
                                    "known": {"type": "boolean"},
                                    "reason": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
        },
    },
}


def read_playlist_file(path=DEFAULT_PLAYLIST_PATH):
    """Read an `Artist,Title,1` text file into a DataFrame.

    Each line is `artist,title,<count>`, optionally followed by `;genre;texture;energy;role;context` tags
    (see `live_mixing.format_now_playing_line`). The artist ends at the first comma and the
    trailing `,<integer>` is stripped, so titles may themselves contain commas. Blank lines are
    skipped; a line with no comma is skipped as unparseable.

    Args:
        path: text file to read (default data/now_playing.txt).

    Returns:
        pandas.DataFrame with columns artist, title, genre, texture, energy, role, context (file
        order,
        duplicates kept). Tag columns are "" on untagged lines.

    Raises:
        FileNotFoundError: if `path` doesn't exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"playlist file not found: {path}")

    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or "," not in line:
            continue
        tags = [""] * len(TAG_COLUMNS)
        head, sep, tail = line.partition(";")
        # Tags only follow the `,<count>` field, so a `;` inside a bare title is left alone.
        if sep and head.rpartition(",")[2].strip().isdigit():
            line = head
            parts = [t.strip() for t in tail.split(";")][: len(TAG_COLUMNS)]
            tags[: len(parts)] = parts
        head, _, tail = line.rpartition(",")
        if tail.strip().isdigit() and "," in head:
            line = head
        artist, _, title = line.partition(",")
        rows.append(
            {"artist": artist.strip(), "title": title.strip(), **dict(zip(TAG_COLUMNS, tags))}
        )
    return pd.DataFrame(rows, columns=["artist", "title", *TAG_COLUMNS])


def load_env_file(path=None):
    """Load `KEY=VALUE` lines from a `.env` file into `os.environ` without overriding.

    Blank lines and `#` comments are skipped; an optional `export ` prefix and surrounding single
    or double quotes on the value are stripped. Variables already set in the environment win.

    Args:
        path: `.env` file to read. If None, the first that exists of ./.env and the repo-root
            .env is used.

    Returns:
        list[str]: names of the variables that were newly set (values are never returned).
        Empty if no file was found or everything was already set.
    """
    if path is None:
        path = next((p for p in DEFAULT_ENV_PATHS if p.is_file()), None)
    if path is None or not Path(path).is_file():
        return []

    loaded = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded


def _require_openai():
    try:
        import openai
    except ImportError as exc:
        raise ImportError(
            'live_mixing.playlist_analysis requires the optional "analysis" extra: '
            'pip install -e ".[analysis]"'
        ) from exc
    return openai


def analyze_playlist(
    tracks=None,
    client=None,
    model=DEFAULT_MODEL,
    context=DEFAULT_CONTEXT,
    temperature=DEFAULT_TEMPERATURE,
):
    """Ask OpenAI to describe a playlist's journey and order it into a DJ set.

    Args:
        tracks: DataFrame with artist and title columns, or a path to an `Artist,Title,1` text
            file. Defaults to data/now_playing.txt.
        client: an initialised `openai.OpenAI` client. If None, `.env` is loaded (see
            `load_env_file`) and a client is created from OPENAI_API_KEY.
        model: chat model name; must support structured outputs (JSON schema).
        context: genre/era description injected into the system prompt.
        temperature: sampling temperature (lower = more deterministic). Models that only accept
            their default temperature will reject other values.

    Returns:
        dict with
            journey: str — description of the overall journey the playlist creates.
            set_order: pandas.DataFrame — columns phase, position (1-based over the whole set),
                artist, title, known (False when the model says it doesn't recognise the record —
                it is told not to infer anything about those), reason; rows in suggested play
                order (warm_up, building, peak, breakdown).
            unassigned: list[str] — "artist - title" of tracks the model left out of every phase
                (empty normally; the model is told to place every track).

    Raises:
        ValueError: if the playlist has no tracks.
        FileNotFoundError: if `tracks` is a path that doesn't exist.
        ImportError: if the `openai` package isn't installed.
    """
    if tracks is None:
        tracks = DEFAULT_PLAYLIST_PATH
    if not isinstance(tracks, pd.DataFrame):
        tracks = read_playlist_file(tracks)
    if tracks.empty:
        raise ValueError("playlist is empty — nothing to analyze")
    tracks = tracks.reset_index(drop=True)

    if client is None:
        openai = _require_openai()
        load_env_file()
        client = openai.OpenAI()

    numbered = "\n".join(
        f"{i}. {row['artist']} - {row['title']}" for i, row in enumerate(tracks.to_dict("records"), 1)
    )
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT.format(context=context)},
            {"role": "user", "content": _USER_PROMPT.format(tracks=numbered)},
        ],
        response_format={"type": "json_schema", "json_schema": _RESPONSE_SCHEMA},
    )
    payload = json.loads(response.choices[0].message.content)

    phase_rank = {p: i for i, p in enumerate(PHASES)}
    placed = set()
    rows = []
    for phase in sorted(payload["phases"], key=lambda p: phase_rank[p["phase"]]):
        for item in phase["tracks"]:
            number = item["number"]
            # Ignore numbers the model invented or repeated — only real, first-time tracks count.
            if number in placed or not 1 <= number <= len(tracks):
                continue
            placed.add(number)
            track = tracks.iloc[number - 1]
            rows.append(
                {
                    "phase": phase["phase"],
                    "position": len(rows) + 1,
                    "artist": track["artist"],
                    "title": track["title"],
                    "known": item["known"],
                    "reason": item["reason"],
                }
            )

    unassigned = [
        f"{t['artist']} - {t['title']}"
        for n, t in enumerate(tracks.to_dict("records"), 1)
        if n not in placed
    ]
    set_order = pd.DataFrame(
        rows, columns=["phase", "position", "artist", "title", "known", "reason"]
    )
    return {"journey": payload["journey"], "set_order": set_order, "unassigned": unassigned}
