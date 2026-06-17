"""MCP tool: find_relevant_docs."""

from __future__ import annotations

import logging

from mcp_server.schemas import FindRelevantDocsOutput
from retrieval import Retriever

logger = logging.getLogger(__name__)


def find_relevant_docs(query: str, top_k: int = 5) -> FindRelevantDocsOutput:
    """Search the knowledge base for relevant document chunks without generating an answer.
    Returns ranked chunks sorted by hybrid search relevance (combining semantic similarity
    and keyword matching). Use this to browse or inspect which documents match a query,
    before deciding whether to ask for a full answer.
    """
    try:
        retriever = Retriever()
        results = retriever.search(query=query, top_k=top_k)
        return FindRelevantDocsOutput(results=results)
    except Exception as exc:  # noqa: BLE001
        logger.exception("find_relevant_docs failed")
        return FindRelevantDocsOutput(results=[])
