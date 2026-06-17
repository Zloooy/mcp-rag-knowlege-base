"""Abstract interface for embedding generation models."""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingModel(ABC):
    """Abstract interface for embedding generation.

    Concrete implementations wrap specific providers (ChromaDB defaults,
    OpenAI-compatible APIs) behind a uniform API so that downstream code —
    the indexer, retriever, etc. — never needs to know which provider is in use.
    """

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of documents.

        Parameters
        ----------
        texts : list[str]
            A list of document strings to embed.

        Returns
        -------
        list[list[float]]
            A list of embedding vectors, one per input text.
        """

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Generate an embedding vector for a single query string.

        Parameters
        ----------
        text : str
            The query text to embed.

        Returns
        -------
        list[float]
            A single embedding vector.
        """
