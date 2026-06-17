"""Retriever: hybrid search combining vector and BM25 with RRF fusion."""

from __future__ import annotations

import logging
import os
import string
from pathlib import Path
from operator import itemgetter

import chromadb
from llm import get_embedding_model
from rank_bm25 import BM25Okapi

from mcp_server.schemas import SearchResult
from retrieval.bm25_store import Bm25Store
from retrieval.embedding_fn import make_chroma_embedding_fn

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# NLTK stopwords — replaces the former hardcoded STOPWORDS constant
# ---------------------------------------------------------------------------


def _ensure_nltk_data() -> None:
    """Download NLTK ``stopwords`` corpus if not already cached."""
    try:
        nltk.data.find("corpora/stopwords")
    except LookupError:
        nltk.download("stopwords", quiet=True)


# Import NLTK after ensuring data; this avoids downloading on cold-import when
# the corpus is already present.
import nltk  # noqa: E402 (after _ensure_nltk_data so import order stays clean)

_ensure_nltk_data()
STOPWORDS: frozenset[str] = frozenset(nltk.corpus.stopwords.words("english"))


def _tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split, remove stopwords."""
    text = text.lower()
    text = text.translate(str.maketrans("", "", string.punctuation))
    tokens = text.split()
    return [t for t in tokens if t not in STOPWORDS]


class Retriever:
    """Hybrid retriever over ChromaDB using vector + BM25 → RRF."""

    def __init__(self, persist_dir: str | None = None) -> None:
        from typing import Any

        self._persist_dir = persist_dir or self._get_setting("CHROMA_PERSIST_DIR")
        self._client = chromadb.PersistentClient(path=self._persist_dir)
        collection_name = self._get_setting("CHROMA_COLLECTION")

        embed_model = get_embedding_model()
        embed_kwargs: dict[str, Any] = {}
        if embed_model is not None:
            chroma_ef = getattr(embed_model, "_embeddings", None)
            if chroma_ef is not None:
                embed_kwargs["embedding_function"] = make_chroma_embedding_fn(
                    chroma_ef, name="langchain_openai_embeddings"
                )

        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
            **embed_kwargs,
        )

        # Persistent BM25 index stored within the Chroma persist directory
        bm25_persist = f"{self._persist_dir}/bm25_index"
        self._bm25_store = Bm25Store(persist_dir=bm25_persist)

    # -- public API -----------------------------------------------------------

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Return the top-*k* most relevant chunks for *query*.

        Uses Reciprocal Rank Fusion of a ChromaDB vector search and a
        BM25 keyword search.

        Returns
        -------
        list[SearchResult]
            Typed search results with ``content``, ``metadata``, and ``score``.
        """
        if not self._collection.count():
            logger.warning("Index is empty — nothing to retrieve")
            return []

        # --- vector retrieval (ChromaDB) ------------------------------------
        vector_results = self._collection.query(
            query_texts=[query],
            n_results=top_k * 3,  # oversample to allow filtering later
            include=["documents", "metadatas", "distances"],
        )

        vector_ranked: dict[str, float] = {}  # doc_id → rank score
        if vector_results["ids"] and vector_results["ids"][0]:
            ids_list = vector_results["ids"][0]
            dists = vector_results["distances"][0]
            docs = vector_results["documents"][0]
            metas = vector_results["metadatas"][0]
            for i, chunk_id in enumerate(ids_list):
                # Convert distance to a relevance-like score
                score = 1.0 / (1.0 + dists[i]) if len(dists) > i else 0.0
                vector_ranked[chunk_id] = score

        # --- BM25 retrieval (uses persisted store) --------------------------
        bm25_ranked = self._bm25_search(query, top_k=top_k * 3)

        # --- RRF fusion -----------------------------------------------------
        rrf_k = self._get_setting("RRF_K")
        fused = self._rrf_fuse(vector_ranked, bm25_ranked, k=rrf_k)

        # Build final result sorted by fused score
        results: list[SearchResult] = []
        for chunk_id, rrf_score in fused[:top_k]:
            meta = self._collection.get(ids=[chunk_id])
            if meta and meta["ids"]:
                results.append(
                    SearchResult(
                        content=meta["documents"][0],
                        metadata={"source": meta["metadatas"][0].get("source", "")},
                        score=round(rrf_score, 6),
                    )
                )

        return results

    def refresh_bm25(self) -> int:
        """Rebuild the BM25 index from current ChromaDB documents and persist it.

        Call this after indexing new documents so the BM25 store stays in sync.

        Returns
        -------
        int
            Number of documents the BM25 index now contains.
        """
        all_ids = self._collection.get(include=[])["ids"]
        all_docs = self._collection.get()["documents"]

        if not all_ids:
            self._bm25_store.update([], [])
            self._bm25_store.save()
            return 0

        self._bm25_store.update(all_ids, all_docs)
        self._bm25_store.save()
        return self._bm25_store.count

    # -- internal helpers -----------------------------------------------------

    @staticmethod
    def _get_setting(name: str):
        """Lazy-access settings to avoid stale-module issues when mcp.* modules
        are cleared (e.g. during test isolation).  Importing here ensures we
        always resolve the current ``mcp_server.config.settings`` singleton."""
        from core.settings import settings

        return getattr(settings, name)

    def _bm25_search(self, query: str, top_k: int = 15) -> dict[str, float]:
        """Run BM25 scoring against the persisted tokenised corpus."""
        corpus = self._bm25_store.corpus
        doc_ids = self._bm25_store.doc_ids

        if not corpus:
            # Fallback: rebuild on-the-fly if store is empty (e.g. first run)
            corpus = [_tokenize(doc) for doc in self._collection.get()["documents"]]
            doc_ids = self._collection.get(include=[])["ids"]
            if not doc_ids:
                return {}

        bm25 = BM25Okapi(corpus)
        query_tokens = _tokenize(query)
        scores = bm25.get_scores(query_tokens)

        ranked: list[tuple[str, float]] = sorted(
            zip(doc_ids, scores), key=itemgetter(1), reverse=True
        )
        return {chunk_id: score for chunk_id, score in ranked[:top_k]}

    @staticmethod
    def _rrf_fuse(
        vector_ranked: dict[str, float],
        bm25_ranked: dict[str, float],
        k: int,
    ) -> list[tuple[str, float]]:
        """Reciprocal Rank Fusion of two ranked dictionaries."""
        scores: dict[str, float] = {}
        for chunk_id in vector_ranked:
            if chunk_id not in scores:
                scores[chunk_id] = 1.0 / (k + 1)  # rank 1 placeholder
            scores[chunk_id] += 1.0 / (k + 1)
        for chunk_id in bm25_ranked:
            if chunk_id not in scores:
                scores[chunk_id] = 1.0 / (k + 1)
            scores[chunk_id] += 1.0 / (k + 1)

        # Sort descending by fused score
        return sorted(scores.items(), key=itemgetter(1), reverse=True)
