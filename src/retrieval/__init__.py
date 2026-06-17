"""Retrieval package — BM25 persistence + hybrid search.

Re-exports the core classes so callers can use::

    from retrieval import Indexer, Retriever, Bm25Store
"""

from __future__ import annotations

from retrieval.bm25_store import Bm25Store
from retrieval.indexer import Indexer
from retrieval.retriever import Retriever, _tokenize, STOPWORDS

__all__ = ["Indexer", "Retriever", "Bm25Store", "_tokenize", "STOPWORDS"]
