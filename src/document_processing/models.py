"""Models for document processing and chunking."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Chunk:
    """A single chunk of text extracted from a source document.

    Attributes
    ----------
    content : str
        The textual content of the chunk.
    chunk_index : int
        Sequential index of this chunk within its source file.
    source : str
        Relative path or identifier of the source file.
    metadata : dict[str, Any]
        Extra context (e.g., section heading, function name, YAML key path).
    position_start : int
        Zero-based character offset of the first character of this chunk
        in the original source document.
    position_end : int
        Zero-based character offset *after* the last character of this chunk
        in the original source document (exclusive, like Python slice notation).
    """

    content: str
    chunk_index: int
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)
    position_start: int = 0
    position_end: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Return a flat dict suitable for ChromaDB upsert."""
        return {
            "content": self.content,
            "chunk_index": self.chunk_index,
            "source": self.source,
            "position_start": self.position_start,
            "position_end": self.position_end,
            **self.metadata,
        }


@dataclass
class SplitResult:
    """The result of splitting a document into chunks.

    Attributes
    ----------
    chunks : list[Chunk]
        The produced chunks.
    source_file : str
        Relative path or identifier of the source file.
    file_extension : str
        The file extension including the dot (e.g. ``".md"``).
    """

    chunks: list[Chunk]
    source_file: str
    file_extension: str
