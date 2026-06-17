"""JSON splitter using tree-sitter AST.

Extracts top-level keys as logical units and preserves the full key path
in metadata.  Values exceeding ``CHUNK_SIZE`` are further character-chunked.

For nested objects, child key paths are emitted with a dotted prefix so that
a chunk for ``data.user.name`` carries the context of its parent hierarchy.

Examples
--------
>>> from document_processing.json_splitter import JSONSplitter
>>> splitter = JSONSplitter()
>>> result = splitter.split('{"name": "Alice", "age": 30}', "sample.json", ".json")
>>> len(result.chunks)
2
"""

from __future__ import annotations

from typing import ClassVar

import tree_sitter as ts
import tree_sitter_json as ts_json

from core.settings import get_chunk_params, settings

from .base import DocumentSplitter
from .models import Chunk, SplitResult


class JSONSplitter(DocumentSplitter):
    """Tree-sitter-aware JSON splitter.

    Parses a JSON document into an AST and walks it depth-first, emitting
    one chunk per leaf value (string, number, boolean, null).  The chunk
    content is a compact JSON representation of the key-path mapping, e.g.::

        {"data.user.name": "Alice"}

    Nested arrays and objects are recursed into; their children inherit the
    parent's key path as a dotted prefix.  Array elements use numeric indices
    in the path (e.g. ``"items.0.id"``).

    If a single leaf value exceeds ``CHUNK_SIZE``, it is further split on
    word boundaries to produce multiple chunks.
    """

    supported_extensions: ClassVar[set[str]] = {".json"}

    def split(self, content: str, source: str, extension: str) -> SplitResult:
        lang = ts.Language(ts_json.language())
        parser = ts.Parser(lang)

        raw = content.encode("utf-8")
        tree = parser.parse(raw)

        root = tree.root_node
        items: list[tuple[str, str, dict[str, str]]] = []

        # A parsed JSON value can be an object or array at the top level
        self._walk_value(root, "", items)

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
    def _is_leaf(t: str) -> bool:
        """Return True if *t* represents a scalar JSON value."""
        return t in ("string", "number", "true", "false", "null")

    @staticmethod
    def _scalar_text(node: ts.Node) -> str:
        """Return the decoded text of a scalar node."""
        return node.text.decode("utf-8", errors="replace").strip()

    @staticmethod
    def _key_name(node: ts.Node) -> str:
        """Extract the unquoted key string from a JSON ``string`` node.

        A tree-sitter-json ``string`` node for a key has structure::

            string
              " (opening quote)
              string_content (the actual key text)
              " (closing quote)

        We drill into ``string_content`` to get the clean key name.
        Falls back to the raw text if no ``string_content`` child is found.
        """
        for child in node.children:
            if child.type == "string_content":
                return child.text.decode("utf-8", errors="replace").strip()
        # Fallback: strip surrounding quotes from the raw text
        raw = node.text.decode("utf-8", errors="replace").strip()
        if len(raw) >= 2 and raw.startswith('"') and raw.endswith('"'):
            return raw[1:-1]
        return raw

    @staticmethod
    def _first_child_of(node: ts.Node, child_type: str) -> ts.Node | None:
        """Return the first child of *node* whose type matches *child_type*, or ``None``."""
        for child in node.children:
            if child.type == child_type:
                return child
        return None

    def _walk_value(
        self,
        node: ts.Node,
        prefix: str,
        results: list[tuple[str, str, dict[str, str]]],
    ) -> None:
        """Recursively walk the AST, collecting leaf values with key paths."""
        # tree-sitter-json wraps top-level values in a 'document' node;
        # unwrap it so we start from the actual JSON value.
        if node.type == "document":
            inner = (
                self._first_child_of(node, "value")
                or self._first_child_of(node, "object")
                or self._first_child_of(node, "array")
            )
            if inner is not None:
                self._walk_value(inner, prefix, results)
            return

        if self._is_leaf(node.type):
            key_path = prefix if prefix else "(root)"
            value = self._scalar_text(node)
            meta: dict[str, str] = {
                "key_path": key_path,
                "value_type": self._infer_json_type(node),
            }
            results.append((key_path, value, meta))
            return

        if node.type == "object":
            for child in node.children:
                if child.type != "pair":
                    continue
                # pair structure: [key(string), ":", value]
                children_list = [c for c in child.children if c.type not in (":",)]
                if len(children_list) < 2:
                    continue
                key_node = children_list[0]
                val_node = children_list[1]
                key_str = self._key_name(key_node)
                child_path = f"{prefix}.{key_str}" if prefix else key_str
                self._walk_value(val_node, child_path, results)

        elif node.type == "array":
            idx = 0
            for child in node.children:
                # Skip structural brackets and separators
                if child.type in (",", "[", "]"):
                    continue
                child_path = f"{prefix}.{idx}" if prefix else str(idx)
                self._walk_value(child, child_path, results)
                idx += 1

    @staticmethod
    def _infer_json_type(node: ts.Node) -> str:
        """Infer the semantic type of a leaf node."""
        t = node.type
        if t == "string":
            return "string"
        if t in ("true", "false"):
            return "boolean"
        if t == "null":
            return "null"
        if t == "number":
            text = node.text.decode("utf-8", errors="replace").strip()
            if "." in text or "e" in text.lower():
                return "float"
            try:
                int(text)
                return "integer"
            except ValueError:
                return "float"
        return "unknown"

    def _chunk_value(
        self,
        key_path: str,
        text: str,
        metadata: dict[str, str],
        start_index: int,
        extension: str = "",
    ) -> list[Chunk]:
        """Split a single leaf value into chunks respecting CHUNK_SIZE."""
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
