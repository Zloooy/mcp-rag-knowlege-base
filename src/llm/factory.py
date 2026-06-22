"""Factory functions for LLM chat and embedding models.

Providers are selected at call time by inspecting the current ``settings``
singleton — this means ``Settings.override()`` works naturally in tests
without any cache invalidation gymnastics.

A provider is considered "configured" when **all three** of its variables
(BASE_URL, MODEL, API_KEY) are present and non-empty.  This avoids partial-
config surprises (e.g. a base URL set but no model name).
"""

from __future__ import annotations

from typing import Any

from llm.chat_models.base import ChatModel
from llm.chat_models.ollama import OllamaChat
from llm.chat_models.openai_compat import OpenAICompatChat
from llm.embed_models.base import EmbeddingModel
from llm.embed_models.openai_compat import OpenAICompatEmbeddings


def get_chat_model() -> ChatModel:
    """Return the appropriate chat model based on current settings.

    If **all** of ``OPENAI_COMPLETIONS_BASE_URL``,
    ``OPENAI_COMPLETIONS_MODEL``, and ``OPENAI_COMPLETIONS_API_KEY`` are
    set to non-empty strings, returns an ``OpenAICompatChat`` instance.

    Otherwise falls back to ``OllamaChat`` using ``OLLAMA_MODEL`` and
    ``OLLAMA_TEMPERATURE`` from settings.

    Returns
    -------
    ChatModel
        An object wrapping either ``ChatOllama`` or ``ChatOpenAI``.
        Compatible with LangChain chains via ``get_underlying()``.
    """
    # Lazy import so Settings.override() swap is always respected.
    from core.settings import settings

    openai_base = settings.OPENAI_COMPLETIONS_BASE_URL.strip()
    openai_model = settings.OPENAI_COMPLETIONS_MODEL.strip()
    openai_key = settings.OPENAI_COMPLETIONS_API_KEY.strip()

    if openai_base and openai_model and openai_key:
        print("Creating OpeiAI chat")
        return OpenAICompatChat(
            base_url=openai_base,
            model=openai_model,
            api_key=openai_key,
        )

    print("Creating Ollama chat")
    return OllamaChat(
        base_url=settings.OLLAMA_BASE_URL or None,
        model=settings.OLLAMA_MODEL,
        temperature=settings.OLLAMA_TEMPERATURE,
    )


def get_embedding_model() -> EmbeddingModel | None:
    """Return the appropriate embedding model based on current settings.

    If **all** of ``OPENAI_EMBEDDINGS_BASE_URL``,
    ``OPENAI_EMBEDDINGS_MODEL``, and ``OPENAI_EMBEDDINGS_API_KEY`` are
    set to non-empty strings, returns an ``OpenAICompatEmbeddings`` instance.

    Otherwise returns ``None`` so that callers can fall back to ChromaDB's
    built-in default embeddings.

    Returns
    -------
    EmbeddingModel | None
        An ``OpenAICompatEmbeddings`` wrapper or ``None``.
    """
    # Lazy import so Settings.override() swap is always respected.
    from core.settings import settings

    openai_base = settings.OPENAI_EMBEDDINGS_BASE_URL.strip()
    openai_model = settings.OPENAI_EMBEDDINGS_MODEL.strip()
    openai_key = settings.OPENAI_EMBEDDINGS_API_KEY.strip()

    if openai_base and openai_model and openai_key:
        return OpenAICompatEmbeddings(
            base_url=openai_base,
            model=openai_model,
            api_key=openai_key,
        )

    return None
