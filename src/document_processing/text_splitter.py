"""Plain-text / fallback splitter with paragraph-aware splitting."""

from __future__ import annotations

from typing import ClassVar

from core.settings import get_chunk_params, settings

from .base import DocumentSplitter
from .models import Chunk, SplitResult


class TextSplitter(DocumentSplitter):
    """Character-level splitter for plain text (``.txt`` and unsupported formats).

    Splits on word boundaries when possible and respects paragraph
    boundaries (double newlines) as preferred split points near the
    chunk size limit.
    """

    supported_extensions: ClassVar[set[str]] = {".txt"}

    def split(self, content: str, source: str, extension: str) -> SplitResult:
        if not content:
            return SplitResult(chunks=[], source_file=source, file_extension=extension)

        size, overlap = get_chunk_params(extension)
        chunks: list[Chunk] = []
        start = 0

        while start < len(content):
            end = start + size

            # Try to find a word boundary first
            if end < len(content):
                split_at = content.rfind(" ", start, end)
                if split_at > start:
                    end = split_at

            # Prefer paragraph breaks when we are close to the boundary
            remaining = content[start:end]
            para_break = remaining.rfind("\n\n")
            if para_break > 0 and para_break < len(remaining) - 20:
                end = start + para_break + 2

            text = content[start:end]
            chunks.append(
                Chunk(
                    content=text,
                    chunk_index=len(chunks),
                    source=source,
                )
            )

            advance = size - overlap
            if advance <= 0:
                advance = 1
            start = end if end >= len(content) else start + advance

        return SplitResult(chunks=chunks, source_file=source, file_extension=extension)
