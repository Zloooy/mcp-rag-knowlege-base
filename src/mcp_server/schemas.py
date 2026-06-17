"""Pydantic output schemas for MCP tools."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SourceDocument(BaseModel):
    """A single document or chunk returned as a source in a RAG answer."""

    content: str = Field(description="The document or chunk text content")
    metadata: dict[str, Any] = Field(
        description="Metadata from the source (e.g. source file path, page number)"
    )


class SearchResult(BaseModel):
    """A single search result from hybrid retrieval."""

    content: str = Field(description="The matched chunk text content")
    metadata: dict[str, Any] = Field(description="Metadata from the retrieved document")
    score: float = Field(description="Relevance score from hybrid retrieval (RRF)")


class IndexFolderOutput(BaseModel):
    """Structured output of the index_folder tool."""

    indexed_count: int = Field(description="Number of files indexed")
    total_chunks: int = Field(description="Total number of chunks created")
    message: str = Field(description="Human-readable summary message")


class AskQuestionOutput(BaseModel):
    """Structured output of the ask_question tool."""

    answer: str = Field(description="The generated answer text")
    sources: list[SourceDocument] = Field(
        description="List of source documents used to generate the answer"
    )


class FindRelevantDocsOutput(BaseModel):
    """Structured output of the find_relevant_docs tool."""

    results: list[SearchResult] = Field(
        description="List of relevant document chunks ranked by relevance"
    )


class IndexStatusOutput(BaseModel):
    """Structured output of the index_status tool."""

    is_indexed: bool = Field(description="Whether folder is indexed")
    indexed_count: int = Field(description="Number of files in index")
    total_chunks: int = Field(description="Total chunks in index")
    persist_dir: str = Field(description="Path to ChromaDB persist directory")


__all__: list[str] = [
    "AskQuestionOutput",
    "FindRelevantDocsOutput",
    "IndexFolderOutput",
    "IndexStatusOutput",
    "SearchResult",
    "SourceDocument",
]
