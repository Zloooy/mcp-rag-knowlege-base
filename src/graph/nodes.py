"""Node implementations for the Corrective RAG LangGraph pipeline.

Each node is a pure function that receives ``RAGState`` and returns a
partial state dict containing only the fields it updates.  This keeps
nodes composable and easy to test in isolation.
"""

from __future__ import annotations

import logging
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from html_text import extract_text

from core.settings import settings
from graph.state import RAGState
from llm.chat_models.base import ChatModel
from llm import get_chat_model
from retrieval import Retriever

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_PROMPTS_DIR = _PROJECT_ROOT / "prompts"


def _load_prompt(filename: str) -> str:
    """Load a prompt template from the project *prompts/* directory.

    The path is resolved relative to this module's location so that it
    works regardless of the current working directory when the script is
    invoked.
    """
    prompt_path = _PROMPTS_DIR / filename
    return prompt_path.read_text(encoding="utf-8").strip()


# ---------------------------------------------------------------------------
# LLM factory (singleton with lazy init; reset on Settings.override)
# ---------------------------------------------------------------------------

_llm_instance: ChatModel | None = None


def _get_llm() -> ChatModel:
    """Return a cached chat model instance via the new LLM abstraction layer.

    The model provider is selected at call time by inspecting the current
    ``settings`` singleton — this means ``Settings.override()`` works
    naturally in tests without any cache invalidation gymnastics.

    Returns
    -------
    ChatModel
        An object wrapping either ``ChatOllama`` or ``ChatOpenAI``,
        fully chain-compatible via ``prompt | llm``.
    """
    global _llm_instance

    # Invalidate cache when underlying provider changes (via Settings.override).
    if _llm_instance is not None:
        old_type = type(_llm_instance).__name__
        new_instance = get_chat_model()
        new_type = type(new_instance).__name__
        if old_type != new_type:
            _llm_instance = None
        else:
            return _llm_instance

    if _llm_instance is None:
        _llm_instance = get_chat_model()

    return _llm_instance


# ---------------------------------------------------------------------------
# Prompts (loaded from files – single source of truth for prompt content)
# ---------------------------------------------------------------------------

_REWRITE_SYSTEM = _load_prompt("query_rewrite.md")
_GRADE_SYSTEM = _load_prompt("relevance_grade.md")
_BROADEN_SYSTEM = _load_prompt("query_broaden.md")
_GENERATE_SYSTEM = _load_prompt("answer_generation.md")


def _make_rewrite_chain(llm: ChatModel):
    """Build the query-rewriting chain."""
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _REWRITE_SYSTEM),
            ("user", "Original query: {query}\nRewritten query:"),
        ]
    )
    return prompt | llm.get_underlying()


def _make_grade_chain(llm: ChatModel):
    """Build the relevance-grading chain."""
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _GRADE_SYSTEM),
            ("user", "Question: {question}\n\nDocument:\n{document}\n\nRelevant:"),
        ]
    )
    return prompt | llm.get_underlying()

def _make_broaden_chain(llm: ChatModel):
    """Build the query-broadening chain."""
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _BROADEN_SYSTEM),
            ("user", "Original query: {query}\nBroadened query:"),
        ]
    )
    return prompt | llm.get_underlying()


def _make_generate_chain(llm: ChatModel):
    """Build the answer-generation chain."""
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _GENERATE_SYSTEM),
            (
                "user",
                "Question: {question}\n\n" "Relevant chunks:\n{context}\n\n" "Answer:",
            ),
        ]
    )
    return prompt | llm.get_underlying()


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------


def rewrite_query(state: RAGState) -> RAGState:
    """Rewrite the user query for improved retrieval quality.

    Calls the LLM to produce a reformulated version of the original
    ``query`` that should yield better results from both vector and
    keyword (BM25) search systems.

    Returns ``{"rewritten_query": ...}`` with the LLM-produced string.
    """
    llm = _get_llm()
    chain = _make_rewrite_chain(llm)
    query: str = state["query"]
    result = chain.invoke({"query": query})
    rewritten = result.content.strip()
    logger.info("Query rewritten: %s -> %s", query, rewritten)
    return {"rewritten_query": rewritten}


def retrieve(state: RAGState) -> RAGState:
    """Run hybrid search (BM25 + vector -> RRF) against the index.

    Uses the ``rewritten_query`` first; if that is empty, falls back
    to the original ``query``.  Results overwrite previous retrievals
    so only the latest search pass is visible at the end.

    Returns ``{"retrieved_chunks": [...]}``.
    """
    rewritten: str | None = state.get("rewritten_query")
    query: str = rewritten or state["query"]
    top_k = 10
    retriever = Retriever()
    results = retriever.search(query=query, top_k=top_k)
    # Convert SearchResult objects to plain dicts — LangGraph state and
    # downstream nodes mutate the chunk dicts in-place (adding relevance_score,
    # relevant keys), which is not possible on Pydantic models.
    chunks = [r.model_dump() for r in results]
    logger.info("Retrieve returned %d chunks for query: %s", len(chunks), query[:80])
    return {"retrieved_chunks": chunks}


def grade_chunks(state: RAGState) -> RAGState:
    """Grade each retrieved chunk for relevance using the LLM.

    For every chunk in ``retrieved_chunks``, the LLM evaluates whether
    it helps answer the question.  Each chunk is annotated with
    ``"relevance_score"`` (float 0-1) and ``"relevant"`` (bool).

    Chunks marked ``relevant=True`` (score > 0) are collected into
    ``relevant_chunks``.

    Returns both ``{"relevant_chunks": ..., "retrieved_chunks": ...}``.
    """
    llm = _get_llm()
    chunks: list[dict] = state.get("retrieved_chunks", [])
    query: str = state["query"]
    relevant: list[dict] = []

    for chunk in chunks:
        content: str = extract_text(chunk.get("content", ""))
        if not content:
            chunk["relevance_score"] = 0.0
            chunk["relevant"] = False
            continue

        try:
            chain = _make_grade_chain(llm)
            response = chain.invoke(
                {
                    "question": query,
                    "document": content,#[:1000],  # avoid context overflow
                }
            )
            text = response.content.strip().lower()

            # Parse LLM structured response
            lines = text.splitlines()
            relevant_flag = "yes"
            score = 0.0

            for line in lines:
                if line.startswith("relevant:"):
                    relevant_flag = line.split(":", 1)[1].strip()
                elif line.startswith("score:"):
                    try:
                        score = float(line.split(":", 1)[1].strip())
                    except ValueError:
                        score = 0.0

            is_relevant = relevant_flag == "yes" or score > 0
            chunk["relevance_score"] = round(score, 4)
            chunk["relevant"] = is_relevant

            if is_relevant:
                relevant.append(chunk)

        except Exception as exc:  # noqa: BLE001 -- don't crash on bad LLM response
            logger.warning("Failed to grade chunk: %s", exc)
            chunk["relevance_score"] = 0.0
            chunk["relevant"] = False

    logger.info(
        "Graded %d chunks -> %d relevant",
        len(chunks),
        len(relevant),
    )
    return {"relevant_chunks": relevant, "retrieved_chunks": chunks}


def generate_answer(state: RAGState) -> RAGState:
    """Generate a final answer from relevant chunks, citing sources.

    Assembles the contents of ``relevant_chunks`` into a context block
    and asks the LLM to produce a concise answer grounded in that
    context.

    If there are no relevant chunks at all, returns a polite fallback
    message.

    Returns ``{"answer": ...}``.
    """
    llm = _get_llm()
    relevant: list[dict] = state.get("relevant_chunks", [])
    query: str = state["query"]

    if not relevant:
        fallback = _load_prompt("fallback_message.md")
        return {"answer": fallback}

    context_parts: list[str] = []
    for i, chunk in enumerate(relevant, start=1):
        source: str = chunk.get("source", "unknown")
        content: str = chunk.get("content", "")
        context_parts.append(f"[Source {i}: {source}]\n{content}")

    context = "\n\n---\n\n".join(context_parts)
    chain = _make_generate_chain(llm)
    result = chain.invoke(
        {
            "question": query,
            "context": context,
        }
    )

    answer = result.content.strip()
    sources = list({c.get("source", "unknown") for c in relevant})
    logger.info("Generated answer from %d sources: %s", len(sources), sources)

    return {"answer": answer}


def broaden(state: RAGState) -> RAGState:
    """Broaden the query and increment the retry counter.

    Calls the LLM to produce a more general version of the query when
    previous searches returned too few relevant results.  The counter
    ``broaden_count`` is incremented so the graph can enforce the max
    loop limit.

    Returns ``{"broadened_query": ..., "broaden_count": ...}``.
    """
    llm = _get_llm()
    current_count: int = state.get("broaden_count", 0)
    new_count = current_count + 1

    if new_count >= settings.MAX_BROADEN_LOOPS:
        # We've hit the budget - no more broadening needed.
        # Just pass through the existing query unchanged.
        logger.info(
            "Max broaden loops (%d) reached; skipping broadening.",
            settings.MAX_BROADEN_LOOPS,
        )
        return {"broaden_count": new_count}

    try:
        chain = _make_broaden_chain(llm)
        rewritten: str | None = state.get("rewritten_query")
        query: str = rewritten or state["query"]
        response = chain.invoke({"query": query})
        broadened = response.content.strip()
        logger.info("Broadened query: %s -> %s", rewritten, broadened)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to broaden query, falling back: %s", exc)
        # Fall back to original - still increments the counter.
        rewritten = state.get("rewritten_query")
        broadened = rewritten or state["query"]

    return {
        "broadened_query": broadened,
        "broaden_count": new_count,
    }
