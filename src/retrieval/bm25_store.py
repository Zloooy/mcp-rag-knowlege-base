"""Persistent BM25 index storage.

Serialises the tokenised corpus to disk so that the BM25 keyword search
index does not need to be rebuilt from ChromaDB on every session or
search call.  Pickle is used because ``rank_bm25.BM25Okapi`` objects are
not JSON-friendly; we store only the internal data structures (the
tokenised corpus as ``list[list[str]]``) and reconstruct the BM25Okapi
instance on load.
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Bm25Store:
    """Persistently store and retrieve a BM25 tokenised corpus.

    Parameters
    ----------
    persist_dir : str
        Directory in which the pickled index will be saved.  Will be
        created if it does not exist.
    """

    def __init__(self, persist_dir: str) -> None:
        self._persist_dir = Path(persist_dir)
        self._persist_dir.mkdir(parents=True, exist_ok=True)

        # Where the pickled data lives
        self._index_path = self._persist_dir / "bm25_index.pkl"

        # In-memory state — populated either by load() or update()
        self._corpus: list[list[str]] = []
        self._doc_ids: list[str] = []

        # Attempt to restore from disk immediately on construction
        self.load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, doc_ids: list[str], documents: list[str]) -> None:
        """(Re)build the BM25 tokenised corpus from *documents*.

        This is an **overwrite** — the entire stored corpus is replaced.
        Call this after the underlying vector store has been updated so
        that the BM25 index stays in sync.

        Parameters
        ----------
        doc_ids : list[str]
            IDs corresponding to each document (used for rank lookup).
        documents : list[str]
            Raw text content of each document.
        """
        from retrieval.retriever import _tokenize  # avoid circular top-level import

        self._doc_ids = list(doc_ids)
        self._corpus = [_tokenize(doc) for doc in documents]
        logger.info("BM25 corpus updated: %d documents tokenised", len(self._corpus))

    def save(self) -> None:
        """Write the current corpus and doc_ids to disk via pickle."""
        payload: dict[str, Any] = {
            "corpus": self._corpus,
            "doc_ids": self._doc_ids,
        }
        with open(self._index_path, "wb") as fh:
            pickle.dump(payload, fh, protocol=pickle.HIGHEST_PROTOCOL)
        logger.debug("BM25 index persisted to %s", self._index_path)

    def load(self) -> bool:
        """Load a previously-persisted BM25 index from disk.

        Returns
        -------
        bool
            ``True`` if a valid index file was found and loaded,
            ``False`` otherwise (first run or corrupted file).
        """
        if not self._index_path.exists():
            logger.debug(
                "No existing BM25 index at %s — starting fresh", self._index_path
            )
            return False

        try:
            with open(self._index_path, "rb") as fh:
                payload: dict[str, Any] = pickle.load(fh)

            corpus = payload.get("corpus", [])
            doc_ids = payload.get("doc_ids", [])

            # Sanity check types
            if not isinstance(corpus, list) or not isinstance(doc_ids, list):
                raise ValueError("Unexpected payload structure")
            if len(corpus) != len(doc_ids):
                raise ValueError(
                    f"Corpus ({len(corpus)}) and doc_ids ({len(doc_ids)}) length mismatch"
                )

            self._corpus = corpus
            self._doc_ids = doc_ids
            logger.info("BM25 index loaded from disk: %d documents", len(self._corpus))
            return True

        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to load BM25 index from %s — starting fresh", self._index_path
            )
            self._corpus = []
            self._doc_ids = []
            return False

    # ------------------------------------------------------------------
    # Clear / reset
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Reset in-memory state and delete the persisted BM25 index on disk.

        Use this when the underlying data source has been completely replaced
        (e.g. a new folder is indexed) so that stale tokens from the previous
        index cannot leak into subsequent searches.
        """
        if self._index_path.exists():
            self._index_path.unlink()
            logger.debug("BM25 index file deleted: %s", self._index_path)
        else:
            logger.debug("No BM25 index file to delete")
        self._corpus = []
        self._doc_ids = []
        logger.info("BM25 store cleared")

    # ------------------------------------------------------------------
    # Read-only accessors
    # ------------------------------------------------------------------

    @property
    def corpus(self) -> list[list[str]]:
        """The tokenised corpus (list of lists of tokens)."""
        return self._corpus

    @property
    def doc_ids(self) -> list[str]:
        """Document IDs aligned with *corpus* entries."""
        return self._doc_ids

    @property
    def count(self) -> int:
        """Number of documents in the stored corpus."""
        return len(self._corpus)

    @property
    def is_empty(self) -> bool:
        """Whether the store currently holds any documents."""
        return len(self._corpus) == 0
