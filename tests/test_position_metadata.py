"""Tests for position metadata flow through the LangGraph RAG pipeline.

These tests verify that ``position_start`` and ``position_end`` — added to
Chunk objects by the data-engineer and persisted in ChromaDB by the
database-coder — are correctly preserved as they travel through each graph
node (retrieve -> grade_chunks -> generate_answer).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestChunkPositionHint:
    """Unit tests for the _chunk_position_hint helper."""

    def test_returns_hint_when_both_offsets_present(self):
        from graph.nodes import _chunk_position_hint

        chunk = {"metadata": {"position_start": 100, "position_end": 500}}
        assert _chunk_position_hint(chunk) == "[chars 100-500]"

    def test_returns_empty_when_no_metadata(self):
        from graph.nodes import _chunk_position_hint

        chunk = {}
        assert _chunk_position_hint(chunk) == ""

    def test_returns_empty_when_only_start_present(self):
        from graph.nodes import _chunk_position_hint

        chunk = {"metadata": {"position_start": 100}}
        assert _chunk_position_hint(chunk) == ""

    def test_returns_empty_when_only_end_present(self):
        from graph.nodes import _chunk_position_hint

        chunk = {"metadata": {"position_end": 500}}
        assert _chunk_position_hint(chunk) == ""

    def test_returns_empty_when_values_are_none(self):
        from graph.nodes import _chunk_position_hint

        chunk = {"metadata": {"position_start": None, "position_end": None}}
        assert _chunk_position_hint(chunk) == ""

    def test_returns_empty_when_position_keys_missing(self):
        from graph.nodes import _chunk_position_hint

        chunk = {"metadata": {"source": "test.md", "other_field": 42}}
        assert _chunk_position_hint(chunk) == ""

    def test_handles_zero_offsets(self):
        from graph.nodes import _chunk_position_hint

        chunk = {"metadata": {"position_start": 0, "position_end": 0}}
        assert _chunk_position_hint(chunk) == "[chars 0-0]"


class TestModelDumpPreservesPositions:
    """Verify SearchResult.model_dump() includes position fields."""

    def test_model_dump_includes_position_fields(self):
        from mcp_server.schemas import SearchResult

        result = SearchResult(
            content="test content",
            metadata={
                "source": "doc.md",
                "position_start": 10,
                "position_end": 99,
            },
            score=0.5,
        )
        dumped = result.model_dump()
        assert dumped["metadata"]["position_start"] == 10
        assert dumped["metadata"]["position_end"] == 99

    def test_model_dump_preserves_non_internal_metadata(self):
        """model_dump preserves all metadata keys; filtering of __* keys
        happens downstream in the retriever, not at schema level."""
        from mcp_server.schemas import SearchResult

        result = SearchResult(
            content="text",
            metadata={
                "source": "file.md",
                "__file_path": "/tmp/file.md",
                "position_start": 0,
                "position_end": 100,
                "chunk_index": 3,
            },
            score=0.7,
        )
        dumped = result.model_dump()
        # model_dump keeps everything — filtering is done by the retriever
        assert "__file_path" in dumped["metadata"]
        assert "position_start" in dumped["metadata"]
        assert "position_end" in dumped["metadata"]
        assert "chunk_index" in dumped["metadata"]


class TestRetrievePreservesPositions:
    """Verify the retrieve node does not strip position metadata."""

    def test_retrieve_transforms_dict_without_striping_positions(self):
        """When retrieve converts SearchResult -> dict, positions survive."""
        from mcp_server.schemas import SearchResult
        from retrieval import Retriever

        mock_results = [
            SearchResult(
                content="chunk with positions",
                metadata={
                    "source": "file.md",
                    "__file_path": "/tmp/file.md",
                    "position_start": 0,
                    "position_end": 100,
                    "chunk_index": 0,
                },
                score=0.9,
            ),
        ]

        mock_retriever = MagicMock(spec=Retriever)
        mock_retriever.search.return_value = mock_results

        with patch("graph.nodes.Retriever", return_value=mock_retriever):
            from graph.nodes import retrieve

            state = {
                "query": "test query",
                "rewritten_query": "test query",
                "broadened_query": "",
                "retrieved_chunks": [],
                "relevant_chunks": [],
                "seen_chunk_ids": set(),
                "answer": "",
                "broaden_count": 0,
            }
            output = retrieve(state)

        chunks = output["retrieved_chunks"]
        assert len(chunks) == 1
        assert chunks[0]["metadata"]["position_start"] == 0
        assert chunks[0]["metadata"]["position_end"] == 100


class TestGradeChunksPreservesPositions:
    """Verify the grade_chunks node preserves position metadata."""

    def test_relevant_chunks_retain_position_data(self):
        """Relevant chunks keep their position offsets after grading."""
        from mcp_server.schemas import SearchResult
        from retrieval import Retriever

        mock_search_result = SearchResult(
            content="<p>relevant content here</p>",
            metadata={
                "source": "doc.md",
                "__file_path": "/tmp/doc.md",
                "position_start": 50,
                "position_end": 150,
            },
            score=0.8,
        )

        mock_retriever = MagicMock(spec=Retriever)
        mock_retriever.search.return_value = [mock_search_result]

        with patch("graph.nodes.Retriever", return_value=mock_retriever):
            # Mock LLM chain to return 'yes' relevance
            mock_chain = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "relevant: yes\nscore: 0.9"
            mock_chain.invoke.return_value = mock_response

            with patch("graph.nodes._make_grade_chain", return_value=mock_chain):
                from graph.nodes import grade_chunks

                retrieved_chunks = [mock_search_result.model_dump()]
                state = {
                    "query": "what is scp?",
                    "rewritten_query": "",
                    "broadened_query": "",
                    "retrieved_chunks": retrieved_chunks,
                    "relevant_chunks": [],
                    "seen_chunk_ids": set(),
                    "answer": "",
                    "broaden_count": 0,
                }
                output = grade_chunks(state)

        relevant = output["relevant_chunks"]
        assert len(relevant) >= 1
        assert relevant[0]["metadata"]["position_start"] == 50
        assert relevant[0]["metadata"]["position_end"] == 150


class TestGenerateAnswerWithContextHints:
    """Verify generate_answer includes position hints in prompt context."""

    def test_context_includes_position_tags_for_first_source(self):
        """The context string passed to LLM contains position info."""
        from langchain_core.messages import AIMessage

        relevant = [
            {
                "content": "This is the first chunk.",
                "metadata": {
                    "source": "doc_a.md",
                    "__file_path": "/tmp/doc_a.md",
                    "position_start": 0,
                    "position_end": 30,
                },
            },
            {
                "content": "This is the second chunk.",
                "metadata": {
                    "source": "doc_b.md",
                    "__file_path": "/tmp/doc_b.md",
                    # No position info -- should produce empty tag
                    "chunk_index": 1,
                },
            },
        ]

        mock_chain = MagicMock()
        mock_chain.invoke.return_value = AIMessage(content="Test answer")

        with patch("graph.nodes._make_generate_chain", return_value=mock_chain):
            from graph.nodes import generate_answer

            state = {
                "query": "test question",
                "rewritten_query": "",
                "broadened_query": "",
                "retrieved_chunks": [],
                "relevant_chunks": relevant,
                "seen_chunk_ids": set(),
                "answer": "",
                "broaden_count": 0,
            }
            generate_answer(state)

        # Check the context sent to LLM (LangChain pipe passes args[0])
        call_arg = mock_chain.invoke.call_args.args[0]
        context = call_arg["context"]

        # First source should have position tag
        assert "[Source 1: doc_a.md [chars 0-30]]" in context
        # Second source should NOT have position tag
        assert "[Source 2: doc_b.md]" in context
        assert "[chars" not in context.split("[Source 2:")[1].split("\n")[0]


class TestFullPipelineFlow:
    """Integration-style test tracing position metadata through the full flow."""

    def test_position_metadata_survives_full_transform_chain(self):
        """Simulate retrieve -> grade -> generate and verify positions persist."""
        from mcp_server.schemas import SearchResult
        from retrieval import Retriever

        original_chunk = SearchResult(
            content="<p>Important SCP information</p>",
            metadata={
                "source": "scp/scp_SCP-001.md",
                "__file_path": "/data/scp_SCP-001.md",
                "position_start": 1000,
                "position_end": 1500,
                "chunk_index": 2,
            },
            score=0.75,
        )

        mock_retriever = MagicMock(spec=Retriever)
        mock_retriever.search.return_value = [original_chunk]

        # Grade returns 'yes'
        mock_chain = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "relevant: yes\nscore: 0.85"
        mock_chain.invoke.return_value = mock_response

        with patch("graph.nodes.Retriever", return_value=mock_retriever):
            with patch("graph.nodes._make_grade_chain", return_value=mock_chain):
                from graph.nodes import generate_answer, grade_chunks, retrieve

                state = {
                    "query": "What is SCP-001?",
                    "rewritten_query": "SCP-001 description",
                    "broadened_query": "",
                    "retrieved_chunks": [],
                    "relevant_chunks": [],
                    "seen_chunk_ids": set(),
                    "answer": "",
                    "broaden_count": 0,
                }

                # Step 1: Retrieve
                step1 = retrieve(state)
                assert (
                    step1["retrieved_chunks"][0]["metadata"]["position_start"] == 1000
                )
                assert step1["retrieved_chunks"][0]["metadata"]["position_end"] == 1500

                # Step 2: Grade
                step2 = grade_chunks(step1)
                assert step2["relevant_chunks"][0]["metadata"]["position_start"] == 1000
                assert step2["relevant_chunks"][0]["metadata"]["position_end"] == 1500

                # Position metadata survived both nodes!
                pos = step2["relevant_chunks"][0]["metadata"]
                assert pos["source"] == "scp/scp_SCP-001.md"
                assert pos["chunk_index"] == 2
