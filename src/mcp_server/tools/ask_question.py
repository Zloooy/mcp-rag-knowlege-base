"""MCP tool: ask_question."""

from __future__ import annotations

import logging

from mcp_server.schemas import AskQuestionOutput, SourceDocument
from graph import build_graph

logger = logging.getLogger(__name__)


def ask_question(query: str) -> AskQuestionOutput:
    """Ask a question against the indexed knowledge base. Runs a RAG (Retrieval-Augmented
    Generation) pipeline: rewrites the query for better retrieval, searches for relevant
    document chunks using hybrid search (semantic + keyword), grades relevance, and generates
    an answer citing sources. Use this to get answers based on the stored documents.
    """
    try:
        graph = build_graph()
        app = graph.compile()

        initial_state = {
            "query": query,
            "rewritten_query": "",
            "broadened_query": "",
            "retrieved_chunks": [],
            "relevant_chunks": [],
            "answer": "",
            "broaden_count": 0,
        }
        result = app.invoke(initial_state)

        raw_sources = result.get("relevant_chunks", [])
        sources = [
            SourceDocument(
                content=s.get("content", "") if isinstance(s, dict) else str(s),
                metadata=s.get("metadata", {}) if isinstance(s, dict) else {},
            )
            for s in raw_sources
        ]
        return AskQuestionOutput(
            answer=result.get("answer", ""),
            sources=sources,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("ask_question failed")
        return AskQuestionOutput(answer="", sources=[])
