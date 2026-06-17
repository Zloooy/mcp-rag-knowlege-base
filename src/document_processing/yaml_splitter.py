"""YAML splitter using tree-sitter AST."""

from __future__ import annotations

from typing import ClassVar

import tree_sitter as ts
import tree_sitter_yaml as ts_yaml

from core.settings import get_chunk_params, settings

from .base import DocumentSplitter
from .models import Chunk, SplitResult


class YAMLSplitter(DocumentSplitter):
    """Tree-sitter-aware YAML splitter.

    Extracts top-level keys as logical units and preserves the full
    key path in metadata.  Values exceeding CHUNK_SIZE are further
    character-chunked.
    """

    supported_extensions: ClassVar[set[str]] = {".yaml", ".yml"}

    def split(self, content: str, source: str, extension: str) -> SplitResult:
        lang = ts.Language(ts_yaml.language())
        parser = ts.Parser(lang)

        raw = content.encode("utf-8")
        tree = parser.parse(raw)

        root = tree.root_node
        mapping_node = self._find_block_mapping(root)

        if mapping_node is None:
            return SplitResult(chunks=[], source_file=source, file_extension=extension)

        items: list[tuple[str, str, dict[str, str]]] = []
        self._walk_pairs(mapping_node, "", items)

        chunks: list[Chunk] = []
        global_idx = 0

        for key_path, value_text, meta in items:
            sub_chunks = self._chunk_value(
                key_path, value_text, meta, global_idx, extension
            )
            chunks.extend(sub_chunks)
            global_idx += len(sub_chunks)

        return SplitResult(chunks=chunks, source_file=source, file_extension=extension)

    # -- internal helpers -----------------------------------------------------

    @staticmethod
    def _find_block_mapping(node: ts.Node) -> ts.Node | None:
        if node.type == "block_mapping":
            return node
        for child in node.children:
            result = YAMLSplitter._find_block_mapping(child)
            if result is not None:
                return result
        return None

    @staticmethod
    def _unwrap_wrapper(node: ts.Node) -> ts.Node:
        """Unwrap flow_node / block_node wrappers to get the inner node."""
        while node.type in ("flow_node", "block_node"):
            if node.children:
                node = node.children[0]
            else:
                break
        return node

    @staticmethod
    def _is_scalar_type(t: str) -> bool:
        return t in (
            "plain_scalar",
            "string_scalar",
            "integer_scalar",
            "float_scalar",
            "null_scalar",
            "boolean_scalar",
        )

    @staticmethod
    def _scalar_name(node: ts.Node) -> str:
        """Recursively find the first scalar string under *node*."""
        if YAMLSplitter._is_scalar_type(node.type):
            return node.text.decode("utf-8", errors="replace").strip()
        for child in node.children:
            result = YAMLSplitter._scalar_name(child)
            if result:
                return result
        return ""

    @staticmethod
    def _infer_scalar_type(text: str) -> str:
        """Infer YAML scalar type from its textual representation."""
        t = text.strip()
        if t in ("null", "~", ""):
            return "null"
        if t in ("true", "false", "yes", "no", "on", "off"):
            return "boolean"
        try:
            int(t)
            return "integer"
        except ValueError:
            pass
        try:
            float(t)
            return "float"
        except ValueError:
            pass
        return "string"

    @staticmethod
    def _get_value_type(node: ts.Node) -> str:
        if YAMLSplitter._is_scalar_type(node.type):
            # tree-sitter-yaml reports all scalars as plain_scalar;
            # infer the actual type from text content
            return YAMLSplitter._infer_scalar_type(
                node.text.decode("utf-8", errors="replace").strip()
            )
        if node.type == "block_mapping":
            return "mapping"
        if node.type == "block_sequence":
            return "sequence"
        return "unknown"

    def _walk_pairs(
        self,
        node: ts.Node,
        prefix: str,
        results: list[tuple[str, str, dict[str, str]]],
    ) -> None:
        if node.type != "block_mapping":
            return

        for pair in node.children:
            if pair.type != "block_mapping_pair":
                continue

            # A pair has exactly 3 children: [key_node, ":", value_node]
            children_list = [c for c in pair.children if c.type != ":"]
            if len(children_list) < 2:
                continue

            key_raw = children_list[0]
            value_raw = children_list[1]

            # Extract key name from the raw key node
            key = self._scalar_name(key_raw)
            if not key:
                continue

            # Resolve the value node (unwrap wrappers)
            value_node = self._unwrap_wrapper(value_raw)
            value_type = self._get_value_type(value_node)
            val_text = value_node.text.decode("utf-8", errors="replace")

            key_path = f"{prefix}.{key}" if prefix else key
            meta: dict[str, str] = {"key_path": key_path, "value_type": value_type}
            results.append((key_path, val_text, meta))

            # Recurse into nested mappings to get leaf values with full paths
            if value_type == "mapping":
                self._walk_pairs(value_node, key_path, results)

    def _chunk_value(
        self,
        key_path: str,
        text: str,
        metadata: dict[str, str],
        start_index: int,
        extension: str = "",
    ) -> list[Chunk]:
        size, overlap = get_chunk_params(extension)

        if not text or len(text) <= size:
            return [
                Chunk(
                    content=text,
                    chunk_index=start_index,
                    source="",
                    metadata=metadata,
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
                )
            )
            advance = size - overlap
            if advance <= 0:
                advance = 1
            start = end if end >= len(text) else start + advance

        return chunks
