"""Markdown splitter using tree-sitter AST."""

from __future__ import annotations

from typing import ClassVar

from inscriptis import get_text
import tree_sitter as ts
import tree_sitter_markdown as ts_md
import tree_sitter_markdown_text as ts_md_text

from core.settings import get_chunk_params, settings

from .base import DocumentSplitter
from .models import Chunk, SplitResult

# Module-level cached language and parser (tree-sitter objects are cheap to share).
_LANG: ts.Language | None = None
_PARSER: ts.Parser | None = None


def _get_parser() -> ts.Parser:
    global _LANG, _PARSER
    if _LANG is None:
        _LANG = ts.Language(ts_md.language())
    if _PARSER is None:
        _PARSER = ts.Parser(_LANG)
    return _PARSER


def _decode_text(node_bytes: bytes | None) -> str:
    """Safely decode bytes from a tree-sitter node to string."""
    if node_bytes is None:
        return ""
    return node_bytes.decode("utf-8", errors="replace")


def _byte_to_char_offset(content: str, byte_offset: int) -> int:
    """Convert a UTF-8 byte offset to a character offset in *content*.

    Tree-sitter parses raw UTF-8 bytes and reports *start_byte* / *end_byte*.
    Because UTF-8 is variable-width, a byte offset does not always equal a
    character offset (e.g. emojis or non-ASCII characters).  This helper
    decodes progressively more of the string until the accumulated byte
    length reaches *byte_offset*, then returns the corresponding character
    index.
    """
    if byte_offset <= 0:
        return 0
    encoded = content.encode("utf-8")
    if byte_offset > len(encoded):
        byte_offset = len(encoded)
    return len(encoded[:byte_offset].decode("utf-8"))


class MarkdownSplitter(DocumentSplitter):
    """Tree-sitter-aware markdown splitter.

    Extracts sections delimited by ATX headings (``#``, ``##``, etc.),
    keeps fenced code blocks atomic, and applies character-level
    chunking within each section when it exceeds CHUNK_SIZE.
    """

    supported_extensions: ClassVar[set[str]] = {".md"}

    def split(self, content: str, source: str, extension: str) -> SplitResult:
        parser = _get_parser()
        raw = content.encode("utf-8")
        tree = parser.parse(raw)

        # Collect top-level children of the document node
        doc_node = tree.root_node
        sections = self._collect_sections(doc_node, raw)

        chunks: list[Chunk] = []
        global_idx = 0

        for heading_text, section_content, pos_start, pos_end in sections:
            meta: dict[str, str] = {}
            if heading_text:
                meta["section"] = heading_text

            # Fenced code blocks are kept as-is; other content is chunked
            sub_chunks = self._chunk_section(
                section_content, meta, pos_start, pos_end, global_idx, extension
            )
            chunks.extend(sub_chunks)
            global_idx += len(sub_chunks)

        return SplitResult(chunks=chunks, source_file=source, file_extension=extension)

    # -- internal helpers -----------------------------------------------------

    @staticmethod
    def _collect_sections(node: ts.Node, raw: bytes) -> list[tuple[str, str, int, int]]:
        """Return triples of ``(heading_text, body_text, position_start, position_end)``
        from a markdown AST.  Positions refer to the original UTF-8 decoded content."""
        results: list[tuple[str, str, int, int]] = []

        if node.type == "section":
            heading_text = ""
            body_parts: list[str] = []

            for child in node.children:
                if child.type == "atx_heading":
                    heading_text = _decode_text(child.text).strip()
                elif child.type == "fenced_code_block":
                    body_parts.append(_decode_text(child.text))
                else:
                    body_parts.append(_decode_text(child.text))

            body = get_text("\n".join(body_parts))
            pos_start = _byte_to_char_offset(
                raw.decode("utf-8", errors="replace"), node.start_byte
            )
            pos_end = _byte_to_char_offset(
                raw.decode("utf-8", errors="replace"), node.end_byte
            )
            results.append((heading_text, body, pos_start, pos_end))

            # Recurse into nested sections
            for child in node.children:
                if child.type == "section":
                    results.extend(MarkdownSplitter._collect_sections(child, raw))

        elif node.child_count > 0:
            for child in node.children:
                results.extend(MarkdownSplitter._collect_sections(child, raw))

        return results

    def _chunk_section(
        self,
        text: str,
        metadata: dict[str, str],
        section_position_start: int,
        section_position_end: int,
        start_index: int,
        extension: str = "",
    ) -> list[Chunk]:
        """Apply character-level chunking to *text* if it exceeds CHUNK_SIZE."""
        size, overlap = get_chunk_params(extension)

        if len(text) <= size:
            return [
                Chunk(
                    content=text,
                    chunk_index=start_index,
                    source="",
                    metadata=metadata,
                    position_start=section_position_start,
                    position_end=section_position_end,
                )
            ]

        chunks: list[Chunk] = []
        start = 0

        while start < len(text):
            end = start + size
            if end < len(text):
                split_at = text.rfind(" ", start, end)
                if split_at > start:
                    end = split_at

            chunk_text = text[start:end]
            chunks.append(
                Chunk(
                    content=chunk_text,
                    chunk_index=start_index + len(chunks),
                    source="",
                    metadata=dict(metadata),
                    position_start=section_position_start + start,
                    position_end=section_position_start + end,
                )
            )
            advance = size - overlap
            if advance <= 0:
                advance = 1
            start = end if end >= len(text) else start + advance

        return chunks
