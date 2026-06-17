"""Factory that selects the right document splitter by file extension."""

from __future__ import annotations

from .base import DocumentSplitter
from .code_splitter import CodeSplitter
from .json_splitter import JSONSplitter
from .markdown_splitter import MarkdownSplitter
from .text_splitter import TextSplitter
from .yaml_splitter import YAMLSplitter

# Registry of all known splitters — populated once at import time.
_REGISTRY: list[type[DocumentSplitter]] = [
    MarkdownSplitter,
    CodeSplitter,
    JSONSplitter,
    YAMLSplitter,
    TextSplitter,  # fallback last
]


def get_splitter(extension: str) -> DocumentSplitter:
    """Return a splitter instance that can handle *extension*.

    The first registered splitter whose ``can_handle`` returns ``True``
    is returned.  If no specific splitter matches, the ``TextSplitter``
    (fallback) is used.

    Parameters
    ----------
    extension : str
        File extension including the dot (e.g. ``".md"``).

    Returns
    -------
    DocumentSplitter
        An instantiated splitter ready for use.
    """
    for cls in _REGISTRY:
        if cls.can_handle(extension):
            return cls()
    # Ultimate fallback: any unknown extension gets text splitting
    return TextSplitter()
