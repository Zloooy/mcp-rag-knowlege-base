"""OpenAI-compatible API embedding model implementation."""

from __future__ import annotations

from langchain_openai import OpenAIEmbeddings

from llm.embed_models.base import EmbeddingModel


class OpenAICompatEmbeddings(EmbeddingModel):
    """Wrapper around ``langchain_openai.OpenAIEmbeddings``.

    Supports any OpenAI-compatible embedding endpoint (not just OpenAI itself)
    by accepting a custom base URL, model name, and API key.

    Parameters
    ----------
    base_url : str
        The API base URL (e.g. ``http://localhost:11434/v1``).
    model : str
        Embedding model name (e.g. ``text-embedding-3-small``, ``nomic-embed``).
    api_key : str
        API key for authenticating with the provider.
    """

    _embeddings: OpenAIEmbeddings

    def __init__(self, base_url: str, model: str, api_key: str) -> None:
        self._embeddings = OpenAIEmbeddings(
            model=model,
            base_url=base_url,
            api_key=api_key,  # type: ignore[arg-type]
            timeout=60,
            max_retries=2,
        )

    # -- EmbeddingModel protocol ----------------------------------------------

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embeddings.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embeddings.embed_query(text)
