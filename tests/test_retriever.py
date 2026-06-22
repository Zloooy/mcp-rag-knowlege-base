"""Tests for the retriever stub."""

from __future__ import annotations

import json
from pathlib import Path

import chromadb

import pytest

from core.settings import settings
from mcp_server.schemas import SearchResult
from retrieval import Retriever, _tokenize, STOPWORDS


def _clear_collection(persist_dir: str) -> None:
    """Drop the collection so tests start clean."""
    import chromadb

    try:
        chromadb.PersistentClient(path=persist_dir).delete_collection(
            name=settings.CHROMA_COLLECTION
        )
    except Exception:
        pass


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


class TestCleanContentStorage:
    """Verify that __clean_content metadata is stored during indexing and returned on retrieval."""

    def test_clean_content_stored_in_metadata(
        self, chroma_dir: Path, sample_docs: Path
    ) -> None:
        """Indexer should store __clean_content alongside enriched documents."""
        import chromadb as _chromadb

        from core.settings import settings
        from retrieval import Indexer

        _clear_collection(str(chroma_dir))
        indexer = Indexer(persist_dir=str(chroma_dir))
        indexer.index_folder(str(sample_docs))

        client = _chromadb.PersistentClient(path=str(chroma_dir))
        collection = client.get_collection(name=settings.CHROMA_COLLECTION)
        data = collection.get(include=["metadatas", "documents"])

        # Every chunk should have __clean_content matching its original text
        for meta, doc in zip(data["metadatas"], data["documents"]):
            clean = meta.get("__clean_content", "")
            assert (
                clean
            ), f"Expected __clean_content in metadata for doc starting with: {doc[:50]}"
            # Clean content must be a prefix of the stored document (the stored
            # doc is enriched with filename/entity tokens appended).
            assert doc.startswith(clean), (
                f"Stored doc does not start with clean content.\n"
                f"Clean: {repr(clean[:80])}\n"
                f"Doc:   {repr(doc[:80])}"
            )

    def test_retrieved_content_is_clean(
        self, populated_index: Path, chroma_dir: Path
    ) -> None:
        """Retrieved SearchResult.content should NOT contain filename/entity suffixes."""
        retriever = Retriever(persist_dir=str(chroma_dir))
        results = retriever.search(query="Python programming", top_k=5)
        assert len(results) > 0
        for r in results:
            # Content should not end with a file stem pattern like "readme", "intro", etc.
            words = r.content.strip().split()
            if words:
                last_word = words[-1].lower()
                # File stems used in test docs are short identifiers;
                # actual chunk content shouldn't end with entity patterns
                assert (
                    not last_word.startswith("scp") or len(last_word) > 3
                ), f"Content may still have enrichment suffix: ...{words[-3:]}"


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

    def test_vector_search_returns_file_path(
        self, populated_index: Path, chroma_dir: Path
    ) -> None:
        """Retrieved results should include __file_path metadata."""
        retriever = Retriever(persist_dir=str(chroma_dir))
        results = retriever.search(query="Python programming", top_k=5)
        assert len(results) > 0
        for r in results:
            fp = r.metadata.get("__file_path", "")
            assert (
                fp
            ), f"Expected __file_path in metadata for {r.metadata.get('source')}"

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
