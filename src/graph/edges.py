"""Conditional edge logic for the Corrective RAG LangGraph pipeline."""

from __future__ import annotations

from typing import Literal

from graph.state import RAGState


def should_broaden(state: RAGState) -> Literal["broaden_and_retry", "generate_answer"]:
    """Decide whether to broaden the search or finish.

    Returns ``"broaden_and_retry"`` when we have fewer relevant chunks
    than the configured minimum *and* haven't exceeded the broadening
    budget; otherwise returns ``"generate_answer"`` so the pipeline can
    produce a final answer (even if empty).
    """
    from core.settings import settings

    relevant_chunks: list[dict] = state.get("relevant_chunks", [])
    current_count: int = state.get("broaden_count", 0)

    if (
        len(relevant_chunks) < settings.MIN_RELEVANT_CHUNKS
        and current_count < settings.MAX_BROADEN_LOOPS
    ):
        return "broaden_and_retry"
    return "generate_answer"
