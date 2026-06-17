"""Tests for the retriever stub."""

from __future__ import annotations

import json
from pathlib import Path

import chromadb

import pytest

from core.settings import settings
from mcp_server.schemas import SearchResult
from retrieval import Retriever, _tokenize, STOPWORDS


class TestTokenize:
    """Verify the simple tokenizer."""

    def test_lowercase_and_strip(self) -> None:
        tokens = _tokenize("Hello, WORLD!")
        assert "hello" in tokens
        assert "world" in tokens
        assert "," not in tokens
        assert "!" not in tokens

    def test_stopwords_removed(self) -> None:
        tokens = _tokenize("the quick brown fox")
        assert "the" not in tokens
        assert "quick" in tokens
        assert "brown" in tokens
        assert "fox" in tokens

    def test_empty_string(self) -> None:
        assert _tokenize("") == []


class TestRetriever:
    """Test ChromaDB vector retrieval and BM25 scoring."""

    def test_vector_search_returns_results(
        self, populated_index: Path, chroma_dir: Path
    ) -> None:
        """ChromaDB query should return documents when index is populated."""
        retriever = Retriever(persist_dir=str(chroma_dir))
        results = retriever.search(query="Python programming", top_k=5)
        assert len(results) > 0
        for r in results:
            assert isinstance(r, SearchResult)
            assert r.content
            assert r.metadata.get("source")
            assert r.score > 0

    def test_bm25_search_returns_results(
        self, populated_index: Path, chroma_dir: Path
    ) -> None:
        """BM25 scoring should work on indexed corpus."""
        bm25_ranked = Retriever(persist_dir=str(chroma_dir))._bm25_search(
            "python variables", top_k=10
        )
        assert len(bm25_ranked) > 0

    def test_rrf_fusion_ordering(self) -> None:
        """RRF should correctly combine two ranked lists."""
        v = {"A": 0.9, "B": 0.5, "C": 0.1}
        b = {"B": 0.8, "C": 0.4, "D": 0.2}
        fused = Retriever._rrf_fuse(v, b, k=60)
        # B appears in both → highest RRF score
        assert fused[0][0] == "B"
        # C appears in both → second highest
        assert fused[1][0] == "C"

    def test_rrf_single_list(self) -> None:
        """If only one list provides a doc, it still gets a valid score."""
        v = {"X": 0.7}
        b: dict[str, float] = {}
        fused = Retriever._rrf_fuse(v, b, k=60)
        assert len(fused) == 1
        assert fused[0][0] == "X"
        assert fused[0][1] > 0

    def test_hybrid_search_better_score_for_overlap(
        self, populated_index: Path, chroma_dir: Path
    ) -> None:
        """Docs matching the query by both methods should rank higher."""
        retriever = Retriever(persist_dir=str(chroma_dir))
        results = retriever.search(query="Python", top_k=5)
        assert len(results) > 0
        # Scores should be descending
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_empty_index_returns_empty(self, empty_index: Path) -> None:
        """Searching an empty index should return no results."""
        retriever = Retriever(persist_dir=str(empty_index))
        results = retriever.search(query="anything", top_k=5)
        assert results == []
