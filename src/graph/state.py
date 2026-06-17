"""State schema for the Corrective RAG LangGraph pipeline."""

from __future__ import annotations

from typing import TypedDict


class RAGState(TypedDict, total=False):
    """State carried through the Corrective RAG graph.

    Fields and their reduction semantics::

        query            – original user question (overwrite)
        rewritten_query  – LLM-improved query for retrieval (overwrite)
        broadened_query  – broadened query used after retry loops (overwrite)
        retrieved_chunks – chunks returned by each retrieve pass (overwrite)
        relevant_chunks  – chunks that passed relevance grading (overwrite)
        answer           – final generated answer (overwrite)
        broaden_count    – how many broaden-and-retry loops executed (overwrite)
    """

    query: str
    rewritten_query: str
    broadened_query: str
    retrieved_chunks: list[dict]
    relevant_chunks: list[dict]
    answer: str
    broaden_count: int
