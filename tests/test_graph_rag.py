"""Tests for the LangGraph Corrective RAG pipeline in ``src/graph/``."""

from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import MagicMock, patch

import pytest

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

# ===========================================================================
# Helpers – create a mock chain whose invoke returns objects with .content
# ===========================================================================


def _make_mock_chain(response_text: str) -> MagicMock:
    """Return a mock chain whose ``invoke(dict)`` yields an object with .content."""
    mock_response = MagicMock()
    mock_response.content = response_text
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = mock_response
    return mock_chain


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture()
def sample_retrieved_chunks() -> list[dict]:
    """Return a small set of mock retrieved chunks."""
    return [
        {
            "id": "c1",
            "content": "Python is a versatile programming language used in web development.",
            "metadata": {"source": "python_intro.md"},
            "score": 0.95,
        },
        {
            "id": "c2",
            "content": "Django is a high-level Python web framework that encourages rapid development.",
            "metadata": {"source": "django_guide.md"},
            "score": 0.87,
        },
        {
            "id": "c3",
            "content": "Random unrelated text about quantum physics and black holes.",
            "metadata": {"source": "physics.txt"},
            "score": 0.12,
        },
    ]


@pytest.fixture()
def sample_state(sample_retrieved_chunks: list[dict]) -> RAGState:
    """Return a minimal RAGState with query and retrieved chunks."""
    return {
        "query": "What is Python?",
        "rewritten_query": "What is Python programming language?",
        "retrieved_chunks": sample_retrieved_chunks,
        "relevant_chunks": [],
        "answer": "",
        "broaden_count": 0,
    }


# ===========================================================================
# Node tests — rewrite_query
# ===========================================================================


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


# ===========================================================================
# Node tests — retrieve
# ===========================================================================


class TestRetrieve:
    """Test the retrieve node."""

    def test_uses_rewritten_query_when_available(self, populated_index) -> None:
        state: RAGState = {
            "query": "original",
            "rewritten_query": "rewritten query",
            "retrieved_chunks": [],
        }
        result = retrieve(state)
        assert isinstance(result["retrieved_chunks"], list)

    def test_falls_back_to_original_query_when_rewritten_empty(
        self, populated_index
    ) -> None:
        state: RAGState = {
            "query": "What is Python?",
            "rewritten_query": "",
            "retrieved_chunks": [],
        }
        result = retrieve(state)
        assert isinstance(result["retrieved_chunks"], list)

    def test_returns_chunk_dicts_with_expected_keys(self, populated_index) -> None:
        state: RAGState = {
            "query": "test",
            "rewritten_query": "test",
            "retrieved_chunks": [],
        }
        result = retrieve(state)
        chunks = result["retrieved_chunks"]
        if chunks:
            chunk = chunks[0]
            # SearchResult has no 'id' field — only content, metadata, score
            assert "content" in chunk
            assert "metadata" in chunk
            assert "score" in chunk


# ===========================================================================
# Node tests — grade_chunks
# ===========================================================================


class TestGradeChunks:
    """Test the grade_chunks node."""

    def test_marks_chunks_as_relevant_or_not(self) -> None:
        chunks = [
            {"content": "Python is great", "metadata": {"source": "a.md"}},
            {"content": "irrelevant noise", "metadata": {"source": "b.md"}},
        ]
        # Each non-empty chunk creates its own chain; side_effect gives different responses.
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
        assert result["relevant_chunks"][0]["metadata"]["source"] == "a.md"
        assert result["relevant_chunks"][0]["relevance_score"] == 0.9
        assert result["relevant_chunks"][0]["relevant"] is True

        # Non-relevant chunk also gets annotated
        irrelevant = [
            c
            for c in result["retrieved_chunks"]
            if c.get("metadata", {}).get("source") == "b.md"
        ][0]
        assert irrelevant["relevant"] is False
        assert irrelevant["relevance_score"] == 0.0

    def test_handles_empty_content(self) -> None:
        chunks = [{"content": "", "metadata": {"source": "empty.md"}}]

        state: RAGState = {
            "query": "test",
            "rewritten_query": "test",
            "retrieved_chunks": chunks,
        }

        with patch("graph.nodes._make_grade_chain"):
            result = grade_chunks(state)

        # Empty content → not relevant, chain factory not called
        assert len(result["relevant_chunks"]) == 0
        assert chunks[0]["relevant"] is False
        assert chunks[0]["relevance_score"] == 0.0

    def test_handles_chain_error_gracefully(self) -> None:
        chunks = [{"content": "some text", "metadata": {"source": "a.md"}}]
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


# ===========================================================================
# Node tests — generate_answer
# ===========================================================================


class TestGenerateAnswer:
    """Test the generate_answer node."""

    def test_generates_from_relevant_chunks(self) -> None:
        """Reads full file content via __file_path metadata when available."""
        chain = _make_mock_chain("Python is a popular programming language.")

        # Create real temporary files so Path(file_path).is_file() succeeds.
        with NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f1:
            f1.write(
                "Python is a versatile programming language.\n"
                "It is widely used in web development, data science,\n"
                "and automation."
            )
            path1 = f1.name

        with NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f2:
            f2.write(
                "Python supports multiple programming paradigms\n"
                "including procedural, object-oriented, and functional."
            )
            path2 = f2.name

        relevant = [
            {
                "content": "Python is popular.",  # deliberately small snippet
                "metadata": {"source": "a.md", "__file_path": path1},
            },
            {
                "content": "It supports many paradigms.",  # deliberately small
                "metadata": {"source": "b.md", "__file_path": path2},
            },
        ]
        state: RAGState = {
            "query": "What is Python?",
            "relevant_chunks": relevant,
        }

        try:
            with patch("graph.nodes._make_generate_chain", return_value=chain):
                result = generate_answer(state)

            assert result["answer"] == "Python is a popular programming language."
            call_arg = chain.invoke.call_args.args[0]
            context = call_arg["context"]

            # Source headers must be present
            assert "Source 1: a.md" in context
            assert "Source 2: b.md" in context
            # Full file content (NOT the small snippet) must appear
            assert "versatile programming language" in context
            assert "multiple programming paradigms" in context
            # The small individual snippets should NOT appear as standalone content
            assert "Python is popular." not in context
            assert "It supports many paradigms." not in context
        finally:
            Path(path1).unlink(missing_ok=True)
            Path(path2).unlink(missing_ok=True)

    def test_uses_full_file_content_from_disk(self) -> None:
        """When __file_path points to an existing file, full content is read."""
        chain = _make_mock_chain("Full answer from full content.")

        with NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write(
                "This is the complete file text.\n"
                "It contains detailed explanations, code examples, and\n"
                "in-depth analysis of the topic at hand."
            )
            path = f.name

        relevant = [
            {
                "content": "partial snippet",  # deliberately different from file
                "metadata": {"source": "big_file.md", "__file_path": path},
            },
        ]
        state: RAGState = {
            "query": "Tell me about big_file.md",
            "relevant_chunks": relevant,
        }

        try:
            with patch("graph.nodes._make_generate_chain", return_value=chain):
                generate_answer(state)

            call_arg = chain.invoke.call_args.args[0]
            context = call_arg["context"]

            # Full file content appears
            assert "complete file text" in context
            assert "code examples" in context
            assert "in-depth analysis" in context
            # Small snippet does NOT appear as content
            assert "partial snippet" not in context
            assert "[Source 1: big_file.md]" in context
        finally:
            Path(path).unlink(missing_ok=True)

    def test_falls_back_to_chunk_when_file_missing(self) -> None:
        """When __file_path points to a nonexistent file, falls back to chunk content."""
        chain = _make_mock_chain("Answer from fallback.")

        relevant = [
            {
                "content": "fallback chunk text",
                "metadata": {
                    "source": "ghost.md",
                    "__file_path": "/nonexistent/path/file.md",
                },
            },
        ]
        state: RAGState = {
            "query": "Ghost query?",
            "relevant_chunks": relevant,
        }

        with patch("graph.nodes._make_generate_chain", return_value=chain):
            result = generate_answer(state)

        assert result["answer"] == "Answer from fallback."
        call_arg = chain.invoke.call_args.args[0]
        context = call_arg["context"]
        assert "fallback chunk text" in context

    def test_falls_back_to_chunk_when_no_file_path(self) -> None:
        """When __file_path key is absent, falls back to chunk content."""
        chain = _make_mock_chain("Answer from no-path chunk.")

        relevant = [
            {"content": "no path chunk", "metadata": {"source": "no_path.md"}},
        ]
        state: RAGState = {
            "query": "No-path query?",
            "relevant_chunks": relevant,
        }

        with patch("graph.nodes._make_generate_chain", return_value=chain):
            result = generate_answer(state)

        assert result["answer"] == "Answer from no-path chunk."
        call_arg = chain.invoke.call_args.args[0]
        context = call_arg["context"]
        assert "no path chunk" in context

    def test_returns_fallback_when_no_relevant_chunks(self) -> None:
        state: RAGState = {
            "query": "test",
            "relevant_chunks": [],
        }

        with patch("graph.nodes._make_generate_chain"):
            result = generate_answer(state)

        assert "no relevant documents were found" in result["answer"].lower()

    def test_passes_question_and_context_to_llm(self) -> None:
        chain = _make_mock_chain("Answer")

        relevant = [{"content": "X", "metadata": {"source": "f.md"}}]
        state: RAGState = {
            "query": "My question?",
            "relevant_chunks": relevant,
        }

        with patch("graph.nodes._make_generate_chain", return_value=chain):
            generate_answer(state)

        call_arg = chain.invoke.call_args.args[0]
        assert call_arg["question"] == "My question?"
        assert "[Source 1: f.md]" in call_arg["context"]


# ===========================================================================
# Node tests — broaden
# ===========================================================================


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

        # Counter will be at max_loops - 1; next call increments to max_loops
        # and skips broadening (budget exhausted).
        state: RAGState = {"query": "test", "broaden_count": max_loops - 1}

        with patch("graph.nodes._make_broaden_chain", return_value=chain):
            result = broaden(state)

        # Counter incremented but exceeded budget so no chain call
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

        # Chain should be called with the rewritten query
        call_arg = chain.invoke.call_args.args[0]
        assert call_arg["query"] == "already rewritten"


# ===========================================================================
# Conditional edge tests
# ===========================================================================


class TestShouldBroaden:
    """Test the should_broaden conditional edge logic."""

    def test_enough_relevant_finishes(
        self, sample_retrieved_chunks: list[dict]
    ) -> None:
        """When enough relevant chunks exist, route to generate_answer."""
        state: RAGState = {
            "query": "test",
            "relevant_chunks": sample_retrieved_chunks[:3],
            "broaden_count": 0,
        }
        assert should_broaden(state) == "generate_answer"

    def test_few_relevant_broadens(self) -> None:
        """When too few relevant chunks, route to broaden_and_retry."""
        from core.settings import settings as s

        with s.override(MIN_RELEVANT_CHUNKS=3):
            state: RAGState = {
                "query": "test",
                "relevant_chunks": [{"id": "bad", "metadata": {"source": "bad.md"}}],
                "broaden_count": 0,
            }
            assert should_broaden(state) == "broaden_and_retry"

    def test_max_loops_exceeded_finishes(self) -> None:
        from core.settings import settings as s

        state: RAGState = {
            "query": "test",
            "relevant_chunks": [],
            "broaden_count": s.MAX_BROADEN_LOOPS,
        }
        assert should_broaden(state) == "generate_answer"

    def test_empty_chunks_treats_as_insufficient(self) -> None:
        """No chunks at all triggers broadening (within budget)."""
        state: RAGState = {
            "query": "test",
            "relevant_chunks": [],
            "broaden_count": 0,
        }
        assert should_broaden(state) == "broaden_and_retry"


# ===========================================================================
# Graph compilation tests
# ===========================================================================


class TestGraphConstruction:
    """Test that the graph builds and compiles correctly."""

    def test_build_graph_returns_compiled_graph(self) -> None:
        g = build_graph()
        app = g.compile()
        assert app is not None

    def test_graph_has_all_nodes(self) -> None:
        g = build_graph()
        compiled = g.compile()
        # Compiled graphs expose internal structure via _builder
        nodes = list(compiled.builder.nodes.keys())
        expected = {
            "rewrite_query",
            "retrieve",
            "grade_chunks",
            "generate_answer",
            "broaden_and_retry",
        }
        assert set(nodes) == expected


# ===========================================================================
# Integration tests (require ChromaDB index + mocked LLM chains & Retriever)
# ===========================================================================


class TestGraphExecution:
    """Integration tests that run the full compiled graph (mock LLM & Retriever)."""

    def test_full_pipeline_with_mocks(self, populated_index) -> None:
        """Run the entire RAG pipeline end-to-end with all external deps mocked."""
        # Build mock chains for each invocation order:
        # 1. rewrite_query (1 chain)
        # 2-4. grade_chunks (1 chain per non-empty retrieved chunk)
        # 5. generate_answer (1 chain)
        rewrite_chain = _make_mock_chain("What is Python programming?")
        # We expect 3 retrieved chunks from the populated index, so 3 grade chains
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
                "retrieved_chunks": [],
                "relevant_chunks": [],
                "answer": "",
                "broaden_count": 0,
            }
            result = app.invoke(initial_state)

        assert "answer" in result
        assert len(result["answer"]) > 0
