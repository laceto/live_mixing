"""
live_mixing/search.py
======================
Optional hybrid (BM25 + semantic) search over the DJUCED track library,
built on top of `kitai` (https://github.com/laceto/kitai) and OpenAI's
Batch API. This is NOT part of the pandas-only core described in
CLAUDE.md — nothing in `live_mixing/__init__.py` imports this module, so
`import live_mixing` never requires these extra dependencies. Import it
explicitly: `from live_mixing import search`.

Install:
    pip install -e ".[search]"

Requires OPENAI_API_KEY in the environment (or a .env file loaded by the
caller) to build or query the index — this module never calls
`load_dotenv()` itself (no module-level side effects, matching kitai's
own convention).

Pipeline (mirrors kitai/scripts/hybrid_rag.py):

    build_track_documents()   tracks+playlists -> list[Document], one per
                               unique track (absolutepath); metadata carries
                               every playlist the track belongs to
        |
    submit_embedding_job()    Documents -> OpenAI Batch API job, skipping
                               any track already present in the embedding
                               cache (see below)
        |
    fetch_embeddings()        poll the job, download results, append new
                               (id, embedding) rows to the cache CSV
        |
    load_track_index()        cache CSV + Documents -> FAISS vectorstore
        |
    build_hybrid_retriever()  FAISS + BM25 -> EnsembleRetriever
        |
    search_tracks()           free-text query -> ranked track/playlist matches

Caching: embeddings are cached in a CSV keyed by track absolutepath
(default EMBEDDING_CACHE_PATH = data/track_embeddings_cache.csv, gitignored
like every other data/*.csv export). `submit_embedding_job` only embeds
tracks not yet in the cache, so re-running the pipeline after the library
changes costs OpenAI calls for only the new/changed tracks, not the whole
library — this is the "optimize for cost" half of the design; match
*quality* comes from the hybrid retriever itself (BM25 catches exact
keyword/typo-tolerant matches, semantic search catches free-text/vibe
queries that share no words with the track metadata).
"""

import ast
from pathlib import Path

import numpy as np
import pandas as pd

from live_mixing.read_djuced_db import DEFAULT_DB_PATH, read_djuced_playlist_tracks

EMBEDDING_CACHE_PATH = Path("data") / "track_embeddings_cache.csv"
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_EMBEDDING_DIMENSIONS = 1536


def _require_search_deps():
    try:
        import kitai  # noqa: F401
        from langchain_core.documents import Document  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "live_mixing.search requires the optional 'search' extra "
            '(pip install -e ".[search]") plus kitai, which is not on PyPI: '
            "pip install git+https://github.com/laceto/kitai.git"
        ) from exc


def _clean(value):
    return "" if pd.isna(value) else str(value)


def build_track_documents(db_path=DEFAULT_DB_PATH):
    """Build one Document per unique track that appears in at least one playlist.

    Groups `read_djuced_playlist_tracks()` rows by `absolutepath` (a track
    can be in several playlists) so each track is embedded once regardless
    of how many playlists it belongs to.

    Args:
        db_path: path to djuced.db.

    Returns:
        list[langchain_core.documents.Document]: `page_content` is
        "<title> — <artist> — <album>" (album omitted if blank); `metadata`
        has `id` (the track's absolutepath, used as the embedding cache
        key), `title`, `artist`, and `playlists` (sorted list of playlist
        names the track belongs to). Empty list if no playlist has tracks.
    """
    _require_search_deps()
    from langchain_core.documents import Document

    rows = read_djuced_playlist_tracks(db_path)
    if rows.empty:
        return []

    docs = []
    for absolutepath, group in rows.groupby("absolutepath"):
        title = _clean(group.iloc[0]["title"])
        artist = _clean(group.iloc[0]["artist"])
        album = _clean(group.iloc[0]["album"])
        page_content = f"{title} — {artist} — {album}" if album else f"{title} — {artist}"
        docs.append(
            Document(
                page_content=page_content,
                metadata={
                    "id": absolutepath,
                    "title": title,
                    "artist": artist,
                    "playlists": sorted(group["playlist_name"].unique().tolist()),
                },
            )
        )
    return docs


def _load_cached_ids(cache_path):
    cache_path = Path(cache_path)
    if not cache_path.exists():
        return set()
    return set(pd.read_csv(cache_path, usecols=["id"])["id"])


def submit_embedding_job(
    docs,
    client,
    cache_path=EMBEDDING_CACHE_PATH,
    model=DEFAULT_EMBEDDING_MODEL,
    dimensions=DEFAULT_EMBEDDING_DIMENSIONS,
):
    """Submit an OpenAI Batch API embedding job for tracks not yet cached.

    Args:
        docs: Documents from `build_track_documents()`.
        client: an initialised `openai.OpenAI` client.
        cache_path: CSV tracking already-embedded track ids (see module docstring).
        model: embedding model name, passed to `kitai.batch.build_embedding_tasks`.
        dimensions: embedding dimensionality, passed through the same way.

    Returns:
        str | None: the new batch job id, or None if every doc in `docs`
        already has a cached embedding (nothing to submit).
    """
    _require_search_deps()
    from kitai.batch import build_embedding_tasks, submit_batch_job

    cached_ids = _load_cached_ids(cache_path)
    new_docs = [d for d in docs if d.metadata["id"] not in cached_ids]
    if not new_docs:
        return None

    tasks = build_embedding_tasks(new_docs, model=model, dimensions=dimensions)
    return submit_batch_job(client, tasks, metadata={"description": "live_mixing track embeddings"})


def fetch_embeddings(client, batch_id, cache_path=EMBEDDING_CACHE_PATH, poll_interval=10.0):
    """Block until `batch_id` completes, then append its embeddings to the cache CSV.

    Args:
        client: an initialised `openai.OpenAI` client.
        batch_id: id returned by `submit_embedding_job`.
        cache_path: CSV to append new (id, embedding) rows to.
        poll_interval: seconds between status polls (see
            `kitai.batch.poll_until_complete`; OpenAI batch jobs can take up
            to the configured completion window, default 24h, so this call
            can block for a long time).

    Returns:
        int: number of embeddings newly written to the cache.

    Raises:
        RuntimeError: if the batch job did not finish in a "completed" state.
    """
    _require_search_deps()
    from kitai.batch import download_batch_results, parse_embedding_results, poll_until_complete

    completed = poll_until_complete(client, [batch_id], poll_interval=poll_interval)
    if batch_id not in completed:
        raise RuntimeError(f"batch job {batch_id} did not complete successfully")

    results = download_batch_results(client, batch_id)
    pairs = parse_embedding_results(results)  # [(custom_id, embedding), ...]

    new_rows = pd.DataFrame(
        [
            {"id": custom_id.removeprefix("custom_id_"), "embedding": str(embedding)}
            for custom_id, embedding in pairs
        ]
    )

    cache_path = Path(cache_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists():
        new_rows = pd.concat([pd.read_csv(cache_path), new_rows], ignore_index=True)
    new_rows.to_csv(cache_path, index=False)
    return len(pairs)


class _BatchQueryEmbeddings:
    """LangChain `Embeddings` shim backed directly by the `openai` client.

    kitai avoids depending on `langchain_openai` for compatibility with its
    langchain-core pin (see kitai/scripts/hybrid_rag.py's `_OpenAIEmbeddings`),
    so callers supply their own thin wrapper for query-time encoding — FAISS
    never re-embeds the stored documents (those come from the batch-embedding
    cache), only the query string at search time.
    """

    def __init__(self, client, model=DEFAULT_EMBEDDING_MODEL):
        self._client = client
        self._model = model

    def embed_documents(self, texts):
        response = self._client.embeddings.create(input=texts, model=self._model)
        return [item.embedding for item in response.data]

    def embed_query(self, text):
        return self.embed_documents([text])[0]


def load_track_index(docs, client, cache_path=EMBEDDING_CACHE_PATH, model=DEFAULT_EMBEDDING_MODEL):
    """Build a FAISS vectorstore from cached embeddings for the given Documents.

    Args:
        docs: Documents from `build_track_documents()`.
        client: an initialised `openai.OpenAI` client (used only to encode
            queries at search time, not to re-embed `docs`).
        cache_path: CSV written by `fetch_embeddings()`.
        model: embedding model name; must match the one used to build the cache.

    Returns:
        langchain_community.vectorstores.FAISS

    Raises:
        FileNotFoundError: if cache_path doesn't exist.
        ValueError: if any doc in `docs` has no cached embedding yet — run
            `submit_embedding_job`/`fetch_embeddings` first.
    """
    _require_search_deps()
    from kitai.index import create_faiss_vectorstore_from_embeddings

    cache_path = Path(cache_path)
    if not cache_path.exists():
        raise FileNotFoundError(f"embedding cache not found: {cache_path}")

    cache = pd.read_csv(cache_path)
    cache["embedding"] = cache["embedding"].apply(ast.literal_eval)
    embedding_by_id = dict(zip(cache["id"], cache["embedding"]))

    missing = [d.metadata["id"] for d in docs if d.metadata["id"] not in embedding_by_id]
    if missing:
        raise ValueError(
            f"{len(missing)} track(s) have no cached embedding yet "
            f"(e.g. {missing[0]!r}) — run submit_embedding_job/fetch_embeddings first."
        )

    embeddings = np.array([embedding_by_id[d.metadata["id"]] for d in docs], dtype=np.float32)
    query_encoder = _BatchQueryEmbeddings(client, model=model)
    return create_faiss_vectorstore_from_embeddings(docs, embeddings, query_encoder)


def build_hybrid_retriever(vectorstore, docs, k_semantic=8, k_bm25=8, weights_sparse=0.5):
    """Wire a BM25 + semantic EnsembleRetriever over the track corpus.

    Args:
        vectorstore: FAISS vectorstore from `load_track_index()`.
        docs: the same Documents used to build `vectorstore` — BM25 needs
            its own copy of the corpus so the two retrievers never drift
            out of sync (see kitai/scripts/hybrid_rag.py).
        k_semantic: docs to retrieve from the semantic (FAISS) retriever.
        k_bm25: docs to retrieve from the BM25 retriever.
        weights_sparse: BM25's weight in [0, 1] for the ensemble merge;
            semantic gets `1 - weights_sparse`. 0.5 balances both; raise it
            toward 1.0 for more keyword-driven results, lower toward 0.0
            for more semantic/free-text results.

    Returns:
        an EnsembleRetriever (from kitai._langchain_compat).
    """
    _require_search_deps()
    from kitai.retriever import create_BM25retriever_from_docs, create_hybrid_retriever, create_retriever

    bm25 = create_BM25retriever_from_docs(docs=docs, k=k_bm25)
    semantic = create_retriever(vs=vectorstore, search_type="similarity", search_kwargs={"k": k_semantic})
    return create_hybrid_retriever(sparse_retriever=bm25, semantic_retriever=semantic, weights_sparse=weights_sparse)


def search_tracks(query, retriever):
    """Run a free-text hybrid search and return matches as a DataFrame.

    Unlike `read_djuced_db.find_track_playlists` (exact substring/token
    matching), this tolerates typos, reordered words, and semantically
    related queries that share no literal text with the track's metadata.

    Args:
        query: free-text search string.
        retriever: an EnsembleRetriever from `build_hybrid_retriever()`.

    Returns:
        pandas.DataFrame with columns title, artist, playlists (comma-joined
        playlist names), one row per matched track, in retriever rank order.
    """
    docs = retriever.invoke(query)
    return pd.DataFrame(
        {
            "title": [d.metadata["title"] for d in docs],
            "artist": [d.metadata["artist"] for d in docs],
            "playlists": [", ".join(d.metadata["playlists"]) for d in docs],
        }
    )
