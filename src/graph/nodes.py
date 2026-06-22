"""Node implementations for the Corrective RAG LangGraph pipeline.

Each node is a pure function that receives ``RAGState`` and returns a
partial state dict containing only the fields it updates.  This keeps
nodes composable and easy to test in isolation.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from inscriptis import get_text

from core.settings import settings
from graph.state import RAGState
from llm.chat_models.base import ChatModel
from llm import get_chat_model
from retrieval import Retriever

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_PROMPTS_DIR = _PROJECT_ROOT / "prompts"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _chunk_key(chunk: dict) -> str:
    """Create a dedup key for a chunk based on source and content."""
    source = chunk.get("metadata", {}).get("source", "unknown")
    return f"{source}::{chunk.get('content', '')[:200]}"


def _chunk_position_hint(chunk: dict) -> str:
    """Extract a human-readable position hint from a chunk's metadata.

    Returns an empty string when position offsets are unavailable.
    """
    meta: dict = chunk.get("metadata", {})
    pos_start = meta.get("position_start")
    pos_end = meta.get("position_end")
    if pos_start is not None and pos_end is not None:
        return f"[chars {pos_start}-{pos_end}]"
    return ""


def _load_prompt(filename: str) -> str:
    """Load a prompt template from the project *prompts/* directory.

    The path is resolved relative to this module's location so that it
    works regardless of the current working directory when the script is
    invoked.
    """
    prompt_path = _PROMPTS_DIR / filename
    return prompt_path.read_text(encoding="utf-8").strip()


# ---------------------------------------------------------------------------
# Chunk joining / merging
# ---------------------------------------------------------------------------


def _join_intersecting_chunks(chunks: list[dict], query: str = "") -> list[dict]:
    """Group chunks by source file and merge overlapping / adjacent ranges.

    Chunks sharing the same ``metadata.source`` are grouped together. Within
    each group, chunks whose ``position_start`` / ``position_end`` intervals
    overlap or touch (i.e. one ends exactly where another begins) are merged
    into a single chunk spanning the minimal start to maximal end of the
    connected interval.

    Content of merged chunks is assembled by walking the sorted positions and
    concatenating only the non-overlapping portions — overlapping text is
    written once.

    Parameters
    ----------
    chunks :
        Raw retrieved chunks (each with ``content`` and ``metadata``).
    query :
        Unused placeholder kept for API compatibility. When broadening is
        active, previously-seen chunks are already excluded upstream; this
        parameter exists only so callers can pass the query verbatim without
        needing conditional logic.

    Returns
    -------
    list[dict]
        Deduplicated joined chunks preserving the expected downstream shape
        (``content``, ``metadata`` with ``source``, ``position_start``,
        ``position_end``, etc.).
    """
    # --- 1. Group chunks by source file -----------------------------------
    groups: dict[str, list[dict]] = defaultdict(list)
    no_position: list[dict] = []

    for chunk in chunks:
        source = chunk.get("metadata", {}).get("source")
        pos_start = chunk.get("metadata", {}).get("position_start")
        pos_end = chunk.get("metadata", {}).get("position_end")

        if source is None or pos_start is None or pos_end is None:
            # No position info → emit as-is (cannot merge safely).
            no_position.append(chunk)
            continue

        groups[source].append(chunk)

    # --- 2. Merge each group -----------------------------------------------
    merged: list[dict] = list(no_position)

    for source, group_chunks in groups.items():
        # Sort by position_start ascending
        group_chunks.sort(key=lambda c: c["metadata"]["position_start"])

        # Build interval tree: collect (start, end, content) triples
        intervals: list[tuple[int, int, str]] = [
            (
                c["metadata"]["position_start"],
                c["metadata"]["position_end"],
                c.get("content", ""),
            )
            for c in group_chunks
        ]

        # Sweep and merge overlapping/adjacent intervals
        merged_intervals: list[tuple[int, int, list[str]]] = []
        cur_start: int = intervals[0][0]
        cur_end: int = intervals[0][1]
        cur_contents: list[str] = [intervals[0][2]]

        for idx in range(1, len(intervals)):
            start, end, content = intervals[idx]
            if start <= cur_end + 1:
                # Overlapping or adjacent — extend current interval
                cur_end = max(cur_end, end)
                cur_contents.append(content)
            else:
                merged_intervals.append((cur_start, cur_end, cur_contents))
                cur_start = start
                cur_end = end
                cur_contents = [content]

        # Flush last interval
        merged_intervals.append((cur_start, cur_end, cur_contents))

        # Build joined chunk(s)
        for m_start, m_end, contents in merged_intervals:
            joined_content = _deduplicate_combine(contents)
            metadata = dict(group_chunks[0]["metadata"])
            metadata["position_start"] = m_start
            metadata["position_end"] = m_end
            metadata["joined_from"] = len(contents)

            merged.append(
                {
                    "content": joined_content,
                    "metadata": metadata,
                }
            )

    return merged


def _deduplicate_combine(contents: list[str]) -> str:
    """Combine multiple chunk contents, removing duplicated overlap.

    Assumes all contents share the same underlying document text and that
    they were extracted from contiguous or overlapping character ranges.
    The simplest correct strategy is to concatenate everything; the LLM
    will handle minor redundancy.  For large overlaps we still want to
    avoid sending megabytes of repeated text, so we keep only unique
    characters seen so far up to a generous cap.
    """
    if len(contents) == 1:
        return contents[0]

    # Fast path: if there are many small pieces, just join them.
    # The grading nodes use `inscriptis.get_text` which already strips
    # HTML tags, so duplication is usually limited to ~CHUNK_OVERLAP chars.
    seen: set[str] = set()
    result_parts: list[str] = []
    total = 0
    # Use a generous per-chunk dedup budget; the caller caps total later.
    BUDGET = 500_000

    for piece in contents:
        for ch in piece:
            if total >= BUDGET:
                break
            if ch not in seen:
                seen.add(ch)
                result_parts.append(ch)
                total += 1
        if total >= BUDGET:
            break

    joined = "".join(result_parts)
    return joined


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
            ("user", ""),
        ]
    )
    return prompt | llm.get_underlying()


def _make_grade_chain(llm: ChatModel):
    """Build the relevance-grading chain."""
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _GRADE_SYSTEM),
            ("user", ""),
        ]
    )
    return prompt | llm.get_underlying()


def _make_broaden_chain(llm: ChatModel):
    """Build the query-broadening chain."""
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _BROADEN_SYSTEM),
            ("user", ""),
        ]
    )
    return prompt | llm.get_underlying()


def _make_generate_chain(llm: ChatModel):
    """Build the answer-generation chain."""
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _GENERATE_SYSTEM),
            ("user", ""),
        ]
    )
    return prompt | llm.get_underlying()


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------


def _extract_response_text(result: Any) -> str:
    """Extract the text content from an LLM invoke result."""
    if isinstance(result, AIMessage):
        raw = result.content or ""
        if isinstance(raw, str):
            return raw.strip()
        # Some models return list of content blocks; join them
        parts: list[str] = []
        for block in raw:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(str(block.get("text", "")))
        return " ".join(parts).strip()
    # Fallback: try .content attribute, then str()
    content = getattr(result, "content", None)
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    # Handle mock objects / other duck-typed responses where .content might
    # be callable (e.g. MagicMock().content returns a new MagicMock).
    if callable(content):
        return ""
    return str(content).strip()


def rewrite_query(state: RAGState) -> RAGState:
    """Rewrite the user query for improved retrieval quality.

    Calls the LLM to produce a reformulated version of the original
    ``query`` that should yield better results from both vector and
    keyword (BM25) search systems.

    Returns ``{"rewritten_query": ...}`` with the LLM-produced string.
    """
    llm = _get_llm()
    chain = _make_rewrite_chain(llm)
    query = state.get("query") or ""
    logger.debug("[GRAPH.rewrite_query] Calling LLM to rewrite user query")
    result = chain.invoke({"query": query})
    rewritten = _extract_response_text(result)
    logger.info("Query rewritten: %s -> %s", query, rewritten)
    return {"rewritten_query": rewritten}


def retrieve(state: RAGState) -> RAGState:
    """Run hybrid search (BM25 + vector -> RRF) against the index.

    Uses the ``broadened_query`` if present (broaden-and-retry loop),
    otherwise falls back to ``rewritten_query``, then to original ``query``.

    On broadened passes, oversamples retrieval to account for previously-seen
    chunks and excludes them so we always get fresh results.

    Returns ``{"retrieved_chunks": [...], "seen_chunk_ids": {...}}``.
    """
    # Determine which query to use
    broadened: str | None = state.get("broadened_query")
    rewritten: str | None = state.get("rewritten_query")

    if broadened and broadened.strip():
        query = broadened.strip()
        is_broaden_pass = True
    elif rewritten and rewritten.strip():
        query = rewritten.strip()
        is_broaden_pass = False
    else:
        query = (state.get("query") or "").strip()
        is_broaden_pass = False

    top_k = settings.RETRIEVE_TOP_K
    retriever = Retriever()

    # Build exclude set from previously seen chunks (by chunk key)
    prev_seen: set[str] = state.get("seen_chunk_ids", set())

    # Calculate how many candidates to fetch. On broaden passes, we need
    # to oversample to compensate for excluded previously-seen chunks.
    # Formula: prev_seen_count + top_k ensures we have enough candidates
    # that after excluding all seen chunks, we still get at least top_k fresh ones.
    if is_broaden_pass and prev_seen:
        # Fetch prev_seen_count + top_k candidates; after dedup we'll have >= top_k
        search_n = len(prev_seen) + top_k
    else:
        search_n = top_k

    # Note: we DON'T pass exclude_ids to the retriever because our chunk keys
    # (_chunk_key) don't match ChromaDB document IDs. Instead, we retrieve
    # more candidates and filter at the node level.
    results = retriever.search(query=query, top_k=search_n, exclude_ids=None)

    # Convert SearchResult objects to plain dicts; metadata stays nested.
    chunks = [r.model_dump() for r in results]

    # Post-filter: remove chunks whose keys were already seen
    if prev_seen:
        chunks = [c for c in chunks if _chunk_key(c) not in prev_seen]

    # Compute and accumulate seen_chunk_ids
    all_seen = set(prev_seen)
    for chunk in chunks:
        all_seen.add(_chunk_key(chunk))

    # Log position metadata presence for observability
    with_pos = sum(
        1 for c in chunks if c.get("metadata", {}).get("position_start") is not None
    )
    logger.info(
        "Retrieve returned %d chunks (%d with position offsets) for query: %s",
        len(chunks),
        with_pos,
        query[:80],
    )
    return {"retrieved_chunks": chunks, "seen_chunk_ids": all_seen}


def grade_chunks(state: RAGState) -> RAGState:
    """Grade each retrieved chunk for relevance using the LLM.

    Before grading, overlapping and adjacent chunks from the same source
    file are joined into larger logical units via ``_join_intersecting_chunks``
    so the LLM grader sees fewer, less redundant inputs.

    For every joined chunk in ``retrieved_chunks``, the LLM evaluates whether
    it helps answer the question.  Each chunk is annotated with
    ``"relevance_score"`` (float 0-1) and ``"relevant"`` (bool).

    Chunks marked ``relevant=True`` (score > 0) are collected into
    ``relevant_chunks``.

    Returns both ``{"relevant_chunks": ..., "retrieved_chunks": ...}``.
    """
    llm = _get_llm()
    chunks: list[dict] = state.get("retrieved_chunks", [])
    query = state.get("query") or ""

    # Join overlapping / adjacent chunks before grading.
    joined_chunks = _join_intersecting_chunks(chunks, query=query)

    relevant: list[dict] = []

    logger.debug(
        "[GRAPH.grade_chunks] Calling LLM to grade relevance for %d chunks "
        "(%d after joining)",
        len(chunks),
        len(joined_chunks),
    )

    for chunk in joined_chunks:
        content: str = get_text(chunk.get("content", ""))
        source: str = chunk.get("metadata", {}).get("source", "unknown")

        if not content:
            chunk["relevance_score"] = 0.0
            chunk["relevant"] = False
            continue

        # Prepend source filename so the LLM grader knows where the chunk is from
        labeled_content = f"[Source: {source}]\n{content}"

        try:
            chain = _make_grade_chain(llm)
            response = chain.invoke(
                {
                    "question": query,
                    "document": labeled_content,
                }
            )
            text = _extract_response_text(response)

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

    # Merge with any relevant chunks already accumulated from prior broaden passes
    existing_relevant: list[dict] = state.get("relevant_chunks", [])
    existing_keys = {_chunk_key(c) for c in existing_relevant}
    merged: list[dict] = list(existing_relevant)
    for chunk in relevant:
        key = _chunk_key(chunk)
        if key not in existing_keys:
            merged.append(chunk)
            existing_keys.add(key)

    # Log how many relevant chunks carry position metadata
    with_pos = sum(
        1 for c in merged if c.get("metadata", {}).get("position_start") is not None
    )
    logger.info(
        "Graded %d chunks -> %d relevant (%d with history; %d with position offsets)",
        len(chunks),
        len(relevant),
        len(merged),
        with_pos,
    )
    return {"relevant_chunks": merged, "retrieved_chunks": chunks}


def generate_answer(state: RAGState) -> RAGState:
    """Generate a final answer from relevant chunks, citing sources.

    Assembles the contents of ``relevant_chunks`` into a context block
    and asks the LLM to produce a concise answer grounded in that
    context.

    For each relevant chunk, if its joined content exceeds
    ``settings.RAG_ANSWER_CHUNK_SIZE`` (default 20 000 chars), the
    joined chunk content is used directly instead of reading the full file
    from disk — this avoids sending megabytes of unrelated document text
    to the LLM.

    If there are no relevant chunks at all, returns a polite fallback
    message.

    Returns ``{"answer": ...}``.
    """
    llm = _get_llm()
    relevant: list[dict] = state.get("relevant_chunks", [])
    query = state.get("query") or ""

    if not relevant:
        fallback = _load_prompt("fallback_message.md")
        return {"answer": fallback}

    context_parts: list[str] = []
    for i, chunk in enumerate(relevant, start=1):
        source: str = chunk.get("metadata", {}).get("source", "unknown")
        file_path: str = chunk.get("metadata", {}).get("__file_path", "")
        pos_start: int | None = chunk.get("metadata", {}).get("position_start")
        pos_end: int | None = chunk.get("metadata", {}).get("position_end")

        # Build a human-readable reference tag with position info when available.
        # This lets the LLM cite precise locations in its answer.
        if pos_start is not None and pos_end is not None:
            ref_tag = f" [chars {pos_start}-{pos_end}]"
        else:
            ref_tag = ""

        # Decide which content to use:
        #   - If the joined chunk content exceeds the configured threshold,
        #     use the joined content directly (avoids reading the entire file).
        #   - Otherwise read the full file from disk as before.
        joined_content = chunk.get("content", "")
        joined_len = len(joined_content)
        limit = settings.RAG_ANSWER_CHUNK_SIZE

        if joined_len <= limit and file_path and Path(file_path).is_file():
            try:
                content = Path(file_path).read_text(encoding="utf-8")
            except OSError:
                content = joined_content
        else:
            # Joined chunk exceeds the configured threshold — use it directly
            # to avoid sending megabytes of unrelated document text to the LLM.
            content = joined_content

        context_parts.append(f"[Source {i}: {source}{ref_tag}]\n{content}")

    context = "\n\n---\n\n".join(context_parts)
    logger.debug(
        "[GRAPH.generate_answer] Calling LLM to generate answer from %d sources",
        len(relevant),
    )
    chain = _make_generate_chain(llm)
    result = chain.invoke(
        {
            "question": query,
            "context": context,
        }
    )

    answer = _extract_response_text(result)
    sources = list({c.get("metadata", {}).get("source", "unknown") for c in relevant})
    source_positions = {
        f"{c.get('metadata', {}).get('source', 'unknown')}:{_chunk_position_hint(c)}"
        for c in relevant
    }
    logger.info(
        "Generated answer from %d sources: %s",
        len(sources),
        sorted(source_positions),
    )

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
        logger.debug(
            "[GRAPH.broaden] Calling LLM to broaden query (loop %d)", new_count
        )
        chain = _make_broaden_chain(llm)
        rewritten: str | None = state.get("rewritten_query")
        query = (rewritten or state.get("query") or "").strip()
        response = chain.invoke({"query": query})
        broadened = _extract_response_text(response)
        logger.info("Broadened query: %s -> %s", rewritten, broadened)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to broaden query, falling back: %s", exc)
        # Fall back to original - still increments the counter.
        rewritten = state.get("rewritten_query")
        broadened = rewritten or state.get("query") or ""

    return {
        "broadened_query": broadened,
        "broaden_count": new_count,
    }
