"""Code splitter using tree-sitter AST for Python, JavaScript and TypeScript."""

from __future__ import annotations

import warnings
from typing import ClassVar

import tree_sitter as ts

from core.settings import get_chunk_params, settings

from .base import DocumentSplitter
from .models import Chunk, SplitResult


def _make_parser(language_module: object, lang_fn: str) -> ts.Parser | None:
    """Create a tree-sitter parser or return ``None`` on failure."""
    try:
        fn = getattr(language_module, lang_fn)
        lang = ts.Language(fn())
        return ts.Parser(lang)
    except Exception as exc:  # pragma: no cover — grammar not installed
        warnings.warn(f"Could not create parser: {exc}", stacklevel=2)
        return None


# Cached parsers per language to avoid re-creation.
_parsers: dict[str, ts.Parser | None] = {}


def _get_parser(key: str, module: object, lang_fn: str) -> ts.Parser | None:
    if key not in _parsers:
        _parsers[key] = _make_parser(module, lang_fn)
    return _parsers[key]


class CodeSplitter(DocumentSplitter):
    """Tree-sitter-aware code splitter for ``.py``, ``.js``, and ``.ts`` files.

    Extracts top-level functions and classes as logical units, then
    applies character-level chunking within each unit when it exceeds
    CHUNK_SIZE. Falls back to plain splitting when parsing fails.
    """

    supported_extensions: ClassVar[set[str]] = {".py", ".js", ".ts"}

    def split(self, content: str, source: str, extension: str) -> SplitResult:
        ext = extension.lstrip(".")

        if ext == "py":
            import tree_sitter_python as tspython

            parser = _get_parser("py", tspython, "language")
        elif ext == "js":
            import tree_sitter_javascript as tsjs

            parser = _get_parser("js", tsjs, "language")
        else:  # ts
            import tree_sitter_typescript as tsts

            parser = _get_parser("ts", tsts, "language_typescript")

        if parser is None:
            # Fallback: treat as plain text
            from .text_splitter import TextSplitter

            return TextSplitter().split(content, source, extension)

        raw = content.encode("utf-8")
        tree = parser.parse(raw)

        units = self._extract_units(tree.root_node, ext)

        if not units:
            # No parseable structure — fall back to plain splitting
            from .text_splitter import TextSplitter

            return TextSplitter().split(content, source, extension)

        chunks: list[Chunk] = []
        global_idx = 0

        for unit_text, metadata in units:
            sub_chunks = self._chunk_unit(unit_text, metadata, global_idx, extension)
            chunks.extend(sub_chunks)
            global_idx += len(sub_chunks)

        return SplitResult(chunks=chunks, source_file=source, file_extension=extension)

    # -- internal helpers -----------------------------------------------------

    @staticmethod
    def _extract_units(node: ts.Node, ext: str) -> list[tuple[str, dict[str, str]]]:
        """Extract top-level function/class definitions as (text, metadata) pairs."""
        results: list[tuple[str, dict[str, str]]] = []

        if ext == "py":
            _PythonExtractor.extract(node, results)
        elif ext == "js":
            _JSExtractor.extract(node, results)
        else:
            _TSExtractor.extract(node, results)

        return results

    @staticmethod
    def _chunk_unit(
        text: str, metadata: dict[str, str], start_index: int, extension: str = ""
    ) -> list[Chunk]:
        size, overlap = get_chunk_params(extension)

        if len(text) <= size:
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


# ── Language-specific extractors ────────────────────────────────────────────


class _PythonExtractor:
    """Extract top-level FunctionDef and ClassDef nodes from a Python AST."""

    @staticmethod
    def extract(node: ts.Node, results: list[tuple[str, dict[str, str]]]) -> None:
        for child in node.children:
            if child.type in ("function_definition", "class_definition"):
                name = ""
                for c in child.children:
                    if c.type == "identifier":
                        name = c.text.decode("utf-8", errors="replace")
                        break

                # Determine whether this is a class or function unit
                if child.type == "class_definition":
                    func_name = ""
                    cls_name = name
                else:
                    func_name = name
                    cls_name = ""

                # Look for enclosing class via parent chain (for methods inside classes)
                parent = child.parent
                while parent:
                    if parent.type == "class_definition":
                        for gc in parent.children:
                            if gc.type == "identifier":
                                cls_name = gc.text.decode("utf-8", errors="replace")
                                break
                        break
                    parent = parent.parent

                meta: dict[str, str] = {
                    "function_name": func_name,
                    "class_name": cls_name,
                    "line_start": str(child.start_point[0] + 1),
                    "line_end": str(child.end_point[0] + 1),
                }
                results.append((child.text.decode("utf-8", errors="replace"), meta))
            else:
                _PythonExtractor.extract(child, results)


class _JSExtractor:
    """Extract top-level function declarations, arrow functions, and methods from JS AST."""

    @staticmethod
    def extract(node: ts.Node, results: list[tuple[str, dict[str, str]]]) -> None:
        for child in node.children:
            if child.type == "function_declaration":
                name = ""
                for c in child.children:
                    if c.type == "identifier":
                        name = c.text.decode("utf-8", errors="replace")
                        break
                meta: dict[str, str] = {
                    "function_name": name,
                    "class_name": "",
                    "line_start": str(child.start_point[0] + 1),
                    "line_end": str(child.end_point[0] + 1),
                }
                results.append((child.text.decode("utf-8", errors="replace"), meta))
            elif child.type == "lexical_declaration":
                # Check for arrow function assignment: const foo = (...) => ...
                for c in child.children:
                    if c.type == "variable_declarator":
                        for gc in c.children:
                            if gc.type == "arrow_function":
                                meta: dict[str, str] = {
                                    "function_name": "",
                                    "class_name": "",
                                    "line_start": str(c.start_point[0] + 1),
                                    "line_end": str(c.end_point[0] + 1),
                                }
                                results.append(
                                    (c.text.decode("utf-8", errors="replace"), meta)
                                )
                                break
            elif child.type == "method_definition":
                name = ""
                for c in child.children:
                    if c.type == "property_identifier":
                        name = c.text.decode("utf-8", errors="replace")
                        break
                meta: dict[str, str] = {
                    "function_name": name,
                    "class_name": "",
                    "line_start": str(child.start_point[0] + 1),
                    "line_end": str(child.end_point[0] + 1),
                }
                results.append((child.text.decode("utf-8", errors="replace"), meta))
            else:
                _JSExtractor.extract(child, results)


class _TSExtractor:
    """Extract top-level function declarations, class members, and arrow functions from TS AST."""

    @staticmethod
    def extract(node: ts.Node, results: list[tuple[str, dict[str, str]]]) -> None:
        for child in node.children:
            if child.type == "function_declaration":
                name = ""
                for c in child.children:
                    if c.type == "identifier":
                        name = c.text.decode("utf-8", errors="replace")
                        break
                meta: dict[str, str] = {
                    "function_name": name,
                    "class_name": "",
                    "line_start": str(child.start_point[0] + 1),
                    "line_end": str(child.end_point[0] + 1),
                }
                results.append((child.text.decode("utf-8", errors="replace"), meta))
            elif child.type == "class_declaration":
                cls_name = ""
                for c in child.children:
                    if c.type == "type_identifier":
                        cls_name = c.text.decode("utf-8", errors="replace")
                        break
                # Extract methods from class_body
                for c in child.children:
                    if c.type == "class_body":
                        for gc in c.children:
                            if gc.type == "method_definition":
                                name = ""
                                for gd in gc.children:
                                    if gd.type == "property_identifier":
                                        name = gd.text.decode("utf-8", errors="replace")
                                        break
                                meta: dict[str, str] = {
                                    "function_name": name,
                                    "class_name": cls_name,
                                    "line_start": str(gc.start_point[0] + 1),
                                    "line_end": str(gc.end_point[0] + 1),
                                }
                                results.append(
                                    (gc.text.decode("utf-8", errors="replace"), meta)
                                )
            elif child.type == "lexical_declaration":
                for c in child.children:
                    if c.type == "variable_declarator":
                        for gc in c.children:
                            if gc.type == "arrow_function":
                                meta: dict[str, str] = {
                                    "function_name": "",
                                    "class_name": "",
                                    "line_start": str(c.start_point[0] + 1),
                                    "line_end": str(c.end_point[0] + 1),
                                }
                                results.append(
                                    (c.text.decode("utf-8", errors="replace"), meta)
                                )
                                break
            else:
                _TSExtractor.extract(child, results)
