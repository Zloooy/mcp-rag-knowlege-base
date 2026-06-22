"""FastMCP server for the RAG knowledge base."""

from __future__ import annotations

import json
import logging
from typing import Any, Literal

from fastmcp import FastMCP

logger = logging.getLogger("mcp_server")

from .schemas import (
    AskQuestionOutput,
    FindRelevantDocsOutput,
    IndexFolderOutput,
    IndexStatusOutput,
)
from .tool_descriptions import (
    RAG_ASK_QUESTION_DESCRIPTION,
    RAG_FIND_RELEVANT_DOCS_DESCRIPTION,
    RAG_INDEX_FOLDER_DESCRIPTION,
    RAG_INDEX_STATUS_DESCRIPTION,
)
from mcp_server.tools.ask_question import ask_question
from mcp_server.tools.find_relevant_docs import find_relevant_docs
from mcp_server.tools.index_folder import index_folder
from mcp_server.tools.index_status import index_status

mcp = FastMCP("rag-knowledge-base")


def _model_to_dict(model: Any) -> dict[str, Any]:
    """Convert a Pydantic model or dict to a plain dict."""
    if hasattr(model, "model_dump"):
        return model.model_dump()
    if isinstance(model, dict):
        return model
    return json.loads(json.dumps(model, default=str))


@mcp.tool(output_schema=IndexFolderOutput.model_json_schema())
def rag_index_folder(path: str, glob_pattern: str = "*") -> dict[str, Any]:
    """Index documents from a local folder into the knowledge base. Scans for files with extensions .md, .txt, .py, .js, .ts, .json, .yaml, splits them into chunks, generates embeddings, and stores them for search. Call this FIRST before asking any questions if you need the agent to know about new documents.

    Parameters:
      - path (required): Absolute or relative path to the folder to scan. Example: "./docs"
      - glob_pattern (optional): File pattern filter. Default "*" matches all supported types. Example: "*.md" for markdown only.

    Call when: A user provides new documents, asks for information not yet answered, or says "index this folder".
    Do NOT call when: The user already asked a question and wants an immediate answer (use rag_ask_question instead).
    """
    logger.debug(
        "request: [MCP] rag_index_folder(path=%r, glob=%r)", path, glob_pattern
    )
    result = _model_to_dict(index_folder(path, glob_pattern))
    logger.debug(
        "response: [MCP] rag_index_folder → indexed_count=%s, total_chunks=%s",
        result.get("indexed_count"),
        result.get("total_chunks"),
    )
    return result


@mcp.tool(output_schema=AskQuestionOutput.model_json_schema())
def rag_ask_question(query: str) -> dict[str, Any]:
    """Ask a question against the indexed knowledge base. This runs the full RAG pipeline: it rewrites the query for better search, finds relevant document chunks using hybrid (semantic + keyword) search, grades each chunk's relevance, and generates a final answer with source citations.

    Parameters:
      - query (required): The natural-language question to answer. Be specific but concise. Example: "How is authentication configured?"

    Call when: The user wants a direct answer to a question. This is the primary Q&A tool.
    Do NOT call when: You need to inspect raw matching documents without an answer (use rag_find_relevant_docs) or the knowledge base has not been indexed yet (use rag_index_folder first).
    """
    logger.debug("request: [MCP] rag_ask_question(query=%r)", query)
    result = _model_to_dict(ask_question(query))
    answer_text = str(result.get("answer", ""))[:200]
    sources_count = len(result.get("sources", []))
    logger.debug(
        "response: [MCP] rag_ask_question → answer=%r, sources=%s",
        answer_text,
        sources_count,
    )
    return result


@mcp.tool(output_schema=FindRelevantDocsOutput.model_json_schema())
def rag_find_relevant_docs(query: str, top_k: int = 5) -> dict[str, Any]:
    """Search the knowledge base for relevant document chunks without generating a final answer. Returns ranked results sorted by hybrid search relevance (combining semantic vector similarity and BM25 keyword matching). Use this to browse, inspect, or verify which documents match a query.

    Parameters:
      - query (required): The search query string. Example: "token expiration configuration"
      - top_k (optional): Number of results to return. Default 5, range 1-20. Example: 10

    Call when: The user wants to see which documents match a query, compare sources, or verify retrieval quality before getting an answer.
    Do NOT call when: The user wants a synthesized answer (use rag_ask_question) or needs to add new documents (use rag_index_folder).
    """
    logger.debug(
        "request: [MCP] rag_find_relevant_docs(query=%r, top_k=%s)", query, top_k
    )
    result = _model_to_dict(find_relevant_docs(query, top_k))
    logger.debug(
        "response: [MCP] rag_find_relevant_docs → result_count=%s",
        len(result.get("results", [])),
    )
    return result


@mcp.tool(output_schema=IndexStatusOutput.model_json_schema())
def rag_index_status() -> dict[str, Any]:
    """Check the current state of the knowledge base index. Returns metadata including the number of files indexed, total chunks, collection name, and the timestamp of the last indexing operation. Use this to verify whether the knowledge base has content before searching.

    Parameters: none

    Call when: Before starting a search session to confirm the knowledge base is populated. After indexing to verify success. When the user asks "what's in the knowledge base" or "how many documents are indexed".
    Do NOT call when: The user is actively asking a question or browsing results (use rag_ask_question or rag_find_relevant_docs instead).
    """
    logger.debug("request: [MCP] rag_index_status(no params)")
    result = _model_to_dict(index_status())
    logger.debug(
        "response: [MCP] rag_index_status → is_indexed=%s, total_chunks=%s, indexed_count=%s",
        result.get("is_indexed"),
        result.get("total_chunks"),
        result.get("indexed_count"),
    )
    return result


def run_server(
    transport: Literal["stdio", "http", "sse", "streamable-http"] = "stdio",
    host: str = "0.0.0.0",
    port: int = 8000,
    **kwargs: Any,
) -> None:
    """Entry point for running the MCP server."""
    mcp.run(transport=transport, host=host, port=port, **kwargs)


if __name__ == "__main__":
    run_server()
