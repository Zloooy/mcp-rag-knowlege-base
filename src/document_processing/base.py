"""Abstract base class for document splitters."""

from __future__ import annotations

import abc
from typing import ClassVar

from .models import SplitResult


class DocumentSplitter(abc.ABC):
    """Base class for all document splitters.

    A splitter knows which file extensions it can handle and is
    responsible for producing semantic ``Chunk`` objects from raw text.
    """

    #: Extensions this splitter supports (without leading dot).
    supported_extensions: ClassVar[set[str]] = set()

    @classmethod
    def can_handle(cls, extension: str) -> bool:
        """Return ``True`` if *extension* (with or without leading dot) is supported."""
        ext = extension
        if ext.startswith("."):
            ext = ext[1:]
        # Also check with the dot for backwards compatibility
        return ext in cls.supported_extensions or f".{ext}" in cls.supported_extensions

    @abc.abstractmethod
    def split(self, content: str, source: str, extension: str) -> SplitResult:
        """Split *content* into chunks appropriate for the given *extension*.

        Parameters
        ----------
        content : str
            Raw file contents as a UTF-8 string.
        source : str
            Relative path or identifier used in chunk metadata.
        extension : str
            File extension including the dot (e.g. ``".md"``).

        Returns
        -------
        SplitResult
            Contains the list of ``Chunk`` objects plus source metadata.
        """
