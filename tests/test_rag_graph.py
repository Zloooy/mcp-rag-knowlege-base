"""Tests for the LangGraph RAG graph (backward-compat shim layer).

This file tests the old ``mcp.engine.rag_graph`` module, which now re-exports
from the new ``graph`` package.  Import statements are updated to use the new
module path so that this test suite validates the deprecation redirect works.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from graph import (
    RAGState,
    build_graph,
    broaden,
    generate_answer,
    grade_chunks,
    retrieve,
    rewrite_query,
)
from graph.edges import should_broaden

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_chain(response_text: str) -> MagicMock:
    """Return a mock chain whose ``invoke(dict)`` yields an object with .content."""
    mock_response = MagicMock()
    mock_response.content = response_text
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = mock_response
    return mock_chain


# ---------------------------------------------------------------------------
# Node tests — rewrite_query
# ---------------------------------------------------------------------------


class TestRewriteQuery:
    """Test the rewrite_query node."""

    def test_calls_llm_with_original_query(self) -> None:
        chain = _make_mock_chain("Refactored query about Python")
        with patch("graph.nodes._make_rewrite_chain", return_value=chain):
            result = rewrite_query({"query": "What is Python?"})

        chain.invoke.assert_called_once_with({"query": "What is Python?"})
        assert result["rewritten_query"] == "Refactored query about Python"

    def test_strips_whitespace(self) -> None:
        chain = _make_mock_chain("   cleaned query   \n")
        with patch("graph.nodes._make_rewrite_chain", return_value=chain):
            result = rewrite_query({"query": "noisy input"})

        assert result["rewritten_query"] == "cleaned query"


# ---------------------------------------------------------------------------
# Node tests — grade_chunks
# ---------------------------------------------------------------------------


class TestGradeChunks:
    """Test the grade_chunks node."""

    def test_marks_chunks_as_relevant_or_not(self) -> None:
        chunks = [
            {"content": "Python is great", "source": "a.md"},
            {"content": "irrelevant noise", "source": "b.md"},
        ]
        chains = [
            _make_mock_chain("relevant: yes\nscore: 0.9"),
            _make_mock_chain("relevant: no\nscore: 0.0"),
        ]

        state: RAGState = {
            "query": "What is Python?",
            "rewritten_query": "What is Python?",
            "retrieved_chunks": chunks,
        }

        with patch("graph.nodes._make_grade_chain", side_effect=chains):
            result = grade_chunks(state)

        assert len(result["relevant_chunks"]) == 1
        assert result["relevant_chunks"][0]["source"] == "a.md"
        assert result["relevant_chunks"][0]["relevance_score"] == 0.9
        assert result["relevant_chunks"][0]["relevant"] is True

        # Non-relevant chunk also gets annotated
        irrelevant = [c for c in result["retrieved_chunks"] if c["source"] == "b.md"][0]
        assert irrelevant["relevant"] is False
        assert irrelevant["relevance_score"] == 0.0

    def test_handles_empty_content(self) -> None:
        chunks = [{"content": "", "source": "empty.md"}]

        state: RAGState = {
            "query": "test",
            "rewritten_query": "test",
            "retrieved_chunks": chunks,
        }

        with patch("graph.nodes._make_grade_chain"):
            result = grade_chunks(state)

        assert len(result["relevant_chunks"]) == 0
        assert chunks[0]["relevant"] is False
        assert chunks[0]["relevance_score"] == 0.0

    def test_handles_chain_error_gracefully(self) -> None:
        chunks = [{"content": "some text", "source": "a.md"}]
        error_chain = MagicMock()
        error_chain.invoke.side_effect = Exception("LLM down")

        state: RAGState = {
            "query": "test",
            "rewritten_query": "test",
            "retrieved_chunks": chunks,
        }

        with patch("graph.nodes._make_grade_chain", return_value=error_chain):
            result = grade_chunks(state)

        assert len(result["relevant_chunks"]) == 0
        assert chunks[0]["relevant"] is False

    def test_no_chunks_produces_empty_result(self) -> None:
        state: RAGState = {
            "query": "test",
            "rewritten_query": "test",
            "retrieved_chunks": [],
        }

        with patch("graph.nodes._make_grade_chain"):
            result = grade_chunks(state)

        assert result["relevant_chunks"] == []
        assert result["retrieved_chunks"] == []


# ---------------------------------------------------------------------------
# Node tests — generate_answer
# ---------------------------------------------------------------------------


class TestGenerateAnswer:
    """Test the generate_answer node."""

    def test_generates_from_relevant_chunks(self) -> None:
        chain = _make_mock_chain("Python is a popular programming language.")

        relevant = [
            {"content": "Python is popular.", "source": "a.md"},
            {"content": "It supports many paradigms.", "source": "b.md"},
        ]
        state: RAGState = {
            "query": "What is Python?",
            "relevant_chunks": relevant,
        }

        with patch("graph.nodes._make_generate_chain", return_value=chain):
            result = generate_answer(state)

        assert result["answer"] == "Python is a popular programming language."
        call_arg = chain.invoke.call_args.args[0]
        assert "Source 1: a.md" in call_arg["context"]
        assert "Source 2: b.md" in call_arg["context"]

    def test_returns_fallback_when_no_relevant_chunks(self) -> None:
        state: RAGState = {
            "query": "test",
            "relevant_chunks": [],
        }

        with patch("graph.nodes._make_generate_chain"):
            result = generate_answer(state)

        assert "could not find any relevant documents" in result["answer"].lower()

    def test_passes_question_and_context_to_llm(self) -> None:
        chain = _make_mock_chain("Answer")

        relevant = [{"content": "X", "source": "f.md"}]
        state: RAGState = {
            "query": "My question?",
            "relevant_chunks": relevant,
        }

        with patch("graph.nodes._make_generate_chain", return_value=chain):
            generate_answer(state)

        call_arg = chain.invoke.call_args.args[0]
        assert call_arg["question"] == "My question?"
        assert "[Source 1: f.md]" in call_arg["context"]


# ---------------------------------------------------------------------------
# Node tests — broaden
# ---------------------------------------------------------------------------


class TestBroaden:
    """Test the broaden node."""

    def test_increments_counter(self) -> None:
        chain = _make_mock_chain("broadened query")

        state: RAGState = {"query": "test", "broaden_count": 0}

        with patch("graph.nodes._make_broaden_chain", return_value=chain):
            result = broaden(state)

        assert result["broaden_count"] == 1
        assert result["broadened_query"] == "broadened query"

    def test_accumulates_across_calls(self) -> None:
        chain = _make_mock_chain("broadened again")

        with patch("graph.nodes._make_broaden_chain", return_value=chain):
            r1 = broaden({"query": "test", "broaden_count": 0})
            r2 = broaden({"query": "test", "broaden_count": r1["broaden_count"]})

        assert r1["broaden_count"] == 1
        assert r2["broaden_count"] == 2

    def test_hits_max_loops_limit(self) -> None:
        from core.settings import settings as s

        max_loops = s.MAX_BROADEN_LOOPS
        chain = _make_mock_chain("broadened")

        state: RAGState = {"query": "test", "broaden_count": max_loops - 1}

        with patch("graph.nodes._make_broaden_chain", return_value=chain):
            result = broaden(state)

        assert result["broaden_count"] == max_loops
        chain.invoke.assert_not_called()

    def test_uses_rewritten_query_for_broadening(self) -> None:
        chain = _make_mock_chain("broadened")

        state: RAGState = {
            "query": "original",
            "rewritten_query": "already rewritten",
            "broaden_count": 0,
        }

        with patch("graph.nodes._make_broaden_chain", return_value=chain):
            broaden(state)

        call_arg = chain.invoke.call_args.args[0]
        assert call_arg["query"] == "already rewritten"


# ---------------------------------------------------------------------------
# Conditional edge tests
# ---------------------------------------------------------------------------


class TestShouldBroaden:
    """Test the should_broaden conditional edge logic."""

    def test_enough_relevant_finishes(self) -> None:
        chunks = [
            {"content": "a", "relevance_score": 1.0, "relevant": True},
            {"content": "b", "relevance_score": 1.0, "relevant": True},
            {"content": "c", "relevance_score": 1.0, "relevant": True},
        ]
        state: RAGState = {"relevant_chunks": chunks, "broaden_count": 0}
        assert should_broaden(state) == "generate_answer"

    def test_few_relevant_broadens(self) -> None:
        state: RAGState = {
            "relevant_chunks": [{"id": "bad", "relevant": False}],
            "broaden_count": 0,
        }
        assert should_broaden(state) == "broaden_and_retry"

    def test_max_loops_exceeded_finishes(self) -> None:
        from core.settings import settings as s

        state: RAGState = {
            "relevant_chunks": [],
            "broaden_count": s.MAX_BROADEN_LOOPS,
        }
        assert should_broaden(state) == "generate_answer"

    def test_empty_chunks_treats_as_insufficient(self) -> None:
        state: RAGState = {
            "relevant_chunks": [],
            "broaden_count": 0,
        }
        assert should_broaden(state) == "broaden_and_retry"


# ---------------------------------------------------------------------------
# Graph compilation tests
# ---------------------------------------------------------------------------


class TestGraphConstruction:
    """Test that the graph builds and compiles correctly."""

    def test_build_graph_returns_compiled_graph(self) -> None:
        g = build_graph()
        app = g.compile()
        assert app is not None

    def test_graph_has_all_nodes(self) -> None:
        g = build_graph()
        compiled = g.compile()
        nodes = list(compiled.builder.nodes.keys())
        expected = {
            "rewrite_query",
            "retrieve",
            "grade_chunks",
            "generate_answer",
            "broaden_and_retry",
        }
        assert set(nodes) == expected


# ---------------------------------------------------------------------------
# Integration tests (require ChromaDB index + mocked LLM chains & Retriever)
# ---------------------------------------------------------------------------


class TestGraphExecution:
    """Integration tests that run the full compiled graph (mock LLM & Retriever)."""

    def test_full_pipeline_with_mocks(self, populated_index) -> None:
        """Run the entire RAG pipeline end-to-end with all external deps mocked."""
        rewrite_chain = _make_mock_chain("What is Python programming?")
        grade_chains = [
            _make_mock_chain("relevant: yes\nscore: 0.9"),
            _make_mock_chain("relevant: yes\nscore: 0.8"),
            _make_mock_chain("relevant: yes\nscore: 0.7"),
        ]
        gen_chain = _make_mock_chain("Python is a versatile programming language.")

        with (
            patch("graph.nodes._make_rewrite_chain", return_value=rewrite_chain),
            patch("graph.nodes._make_grade_chain", side_effect=grade_chains),
            patch("graph.nodes._make_generate_chain", return_value=gen_chain),
        ):
            g = build_graph()
            app = g.compile()
            initial_state: RAGState = {
                "query": "What is Python?",
                "rewritten_query": "",
                "broadened_query": "",
                "retrieved_chunks": [],
                "relevant_chunks": [],
                "answer": "",
                "broaden_count": 0,
            }
            result = app.invoke(initial_state)

        assert "answer" in result
        assert len(result["answer"]) > 0
        assert "retrieved_chunks" in result
        assert len(result["retrieved_chunks"]) > 0
        assert "relevant_chunks" in result

    def test_graph_handles_empty_index(self) -> None:
        """Graph should produce an answer even when index is empty."""
        rewrite_chain = _make_mock_chain("unknown topic xyz")
        gen_chain = _make_mock_chain("I couldn't find any info.")

        with (
            patch("graph.nodes._make_rewrite_chain", return_value=rewrite_chain),
            patch("graph.nodes._make_generate_chain", return_value=gen_chain),
        ):
            g = build_graph()
            app = g.compile()
            initial_state: RAGState = {
                "query": "unknown topic xyz",
                "rewritten_query": "",
                "broadened_query": "",
                "retrieved_chunks": [],
                "relevant_chunks": [],
                "answer": "",
                "broaden_count": 0,
            }
            result = app.invoke(initial_state)

        assert "answer" in result
        assert len(result["answer"]) > 0
