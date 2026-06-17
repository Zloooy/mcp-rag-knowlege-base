"""Document processing module for RAG knowledge base.

This package provides AST-aware, format-specific document splitters
built on top of tree-sitter.  It also includes a plain-text fallback
for unsupported formats.

Public API
----------
- ``DocumentSplitter`` — abstract base class
- ``Chunk``, ``SplitResult`` — data models
- ``get_splitter(extension)`` — factory function
- Individual splitter classes: ``MarkdownSplitter``, ``CodeSplitter``,
  ``JSONSplitter``, ``YAMLSplitter``, ``TextSplitter``
"""

from __future__ import annotations

from .base import DocumentSplitter
from .code_splitter import CodeSplitter
from .factory import get_splitter
from .json_splitter import JSONSplitter
from .markdown_splitter import MarkdownSplitter
from .models import Chunk, SplitResult
from .text_splitter import TextSplitter
from .yaml_splitter import YAMLSplitter

__all__ = [
    "Chunk",
    "CodeSplitter",
    "DocumentSplitter",
    "JSONSplitter",
    "MarkdownSplitter",
    "SplitResult",
    "TextSplitter",
    "YAMLSplitter",
    "get_splitter",
]
