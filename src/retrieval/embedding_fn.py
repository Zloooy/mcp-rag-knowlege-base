"""ChromaDB embedding function wrappers that bridge LangChain embeddings."""

from __future__ import annotations

import logging
from typing import Any, Protocol

import chromadb
from chromadb.api.types import Embeddings, Documents

logger = logging.getLogger(__name__)


class _LangChainEmbeddingProtocol(Protocol):
    """Duck-typing interface for LangChain embedding objects."""

    def embed_documents(self, documents: list[str]) -> list[list[float]]: ...
    def embed_query(self, document: str) -> list[float]: ...


def make_chroma_embedding_fn(
    langchain_embeddings: _LangChainEmbeddingProtocol,
    name: str = "langchain_embeddings",
) -> chromadb.EmbeddingFunction[Documents]:
    """Wrap a LangChain-compatible embedding object as a ChromaDB ``EmbeddingFunction``.

    This bridge implements the ChromaDB 1.x embedding function protocol
    (``__call__``, ``name``, ``get_config``, ``build_from_config``) so that
    LangChain embedding providers can be used with ChromaDB collections.

    Parameters
    ----------
    langchain_embeddings : _LangChainEmbeddingProtocol
        An object with ``embed_documents(texts)`` and ``embed_query(text)``
        methods (e.g. ``langchain_openai.OpenAIEmbeddings``).
    name : str
        A human-readable name for this embedding function.

    Returns
    -------
    chromadb.EmbeddingFunction[Documents]
        A callable that ChromaDB can use for vector storage and retrieval.
    """

    class _Wrapper(chromadb.EmbeddingFunction[Documents]):
        def __call__(self, input: Documents) -> Embeddings:
            # Detect whether we have a single query or multiple documents.
            if isinstance(input, str):
                return [langchain_embeddings.embed_query(input)]
            return langchain_embeddings.embed_documents(list(input))

        @staticmethod
        def name() -> str:
            return name

        def get_config(self) -> dict[str, Any]:
            return {"type": "langchain_wrapper", "name": name}

        @staticmethod
        def build_from_config(config: dict[str, Any]) -> "_Wrapper":
            return _Wrapper()

    return _Wrapper()
