"""Central project settings via Pydantic BaseSettings.

All environment variables, constants, and tuning parameters live here so
that other modules never hardcode values or reach for ``os.environ`` directly.

Test override patterns::

    # Pattern 1 — context manager (recommended)
    from core.settings import Settings

    with Settings.override(CHROMA_PERSIST_DIR="/tmp/chroma_test"):
        …  # code that needs a different persist dir

    # Pattern 2 — reassign the singleton (for tests that previously did
    # ``settings.CHROMA_PERSIST_DIR = "/tmp"`` on the old mutable class)
    from core.settings import get_chunk_params, settings

    settings.model_rebuild()  # optional: ensure fresh state
    global _settings
    _settings = Settings(CHROMA_PERSIST_DIR="/tmp/chroma_test")
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, ClassVar, Literal

from pydantic import ConfigDict, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration for the RAG knowledge-base MCP server."""

    model_config = ConfigDict(env_prefix="RAG_", env_file=".env", extra="ignore")

    # ------------------------------------------------------------------
    # General
    # ------------------------------------------------------------------

    LOG_LEVEL: str = "INFO"

    # ------------------------------------------------------------------
    # LLM -- Completions (text generation)
    # ------------------------------------------------------------------

    # Ollama (legacy / local fallback). Kept for backward compatibility.
    OLLAMA_MODEL: str = "qwen2.5:3b"
    OLLAMA_TEMPERATURE: float = 0.0

    # OpenAI-compatible API for completions. When any of these three are set,
    # the server uses them *instead* of Ollama for answer generation.
    OPENAI_COMPLETIONS_BASE_URL: str = ""
    # Base URL for the OpenAI-compatible completions API
    # (e.g. ``http://localhost:11434/v1``).

    OPENAI_COMPLETIONS_MODEL: str = ""
    # Model name to use for completions (e.g. ``gpt-4o``, ``llama-3``).

    OPENAI_COMPLETIONS_API_KEY: str = ""
    # API key for authenticating with the completions provider.

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------

    # OpenAI-compatible API for text embeddings. When any of these three are
    # set the indexer and retriever use them instead of ChromaDB's default
    # embeddings. If left blank the project falls back to ChromaDB defaults.
    OPENAI_EMBEDDINGS_BASE_URL: str = ""
    # Base URL for the OpenAI-compatible embeddings API.

    OPENAI_EMBEDDINGS_MODEL: str = ""
    # Embedding model name (e.g. ``text-embedding-3-small``, ``nomic-embed``).

    OPENAI_EMBEDDINGS_API_KEY: str = ""
    # API key for authenticating with the embeddings provider.

    # ------------------------------------------------------------------
    # ChromaDB
    # ------------------------------------------------------------------

    CHROMA_PERSIST_DIR: str = "./chroma_db"
    CHROMA_COLLECTION: str = "rag_knowledge_base"
    CHROMA_HNSW_SPACE: Literal["cosine", "l2", "ip"] = "cosine"

    # ------------------------------------------------------------------
    # Document processing / chunking
    # ------------------------------------------------------------------

    SUPPORTED_EXTENSIONS: list[str] = [
        ".md",
        ".txt",
        ".py",
        ".js",
        ".ts",
        ".json",
        ".yaml",
    ]

    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50

    # Per-extension overrides; each entry can specify *chunk_size* and
    # *chunk_overlap* to fine-tune splitting for a given format.
    CHUNK_CONFIGS: dict[str, dict[str, int]] = {}

    # ------------------------------------------------------------------
    # Retrieval & ranking
    # ------------------------------------------------------------------

    RRF_K: int = 60
    RETRIEVE_TOP_K: int = 10
    FIND_RELEVANT_DOCS_DEFAULT_TOP_K: int = 5
    VECTOR_OVERSAMPLE_FACTOR: int = 3  # n_results = top_k * oversample

    # ------------------------------------------------------------------
    # Corrective RAG / LangGraph
    # ------------------------------------------------------------------

    MIN_RELEVANT_CHUNKS: int = 3
    MAX_BROADEN_LOOPS: int = 2

    @field_validator("SUPPORTED_EXTENSIONS")
    @classmethod
    def _sort_extensions(cls, v: list[str]) -> list[str]:
        return sorted(v)

    # -- test-friendly instance override --------------------------------------

    @classmethod
    @contextmanager
    def override(cls, /, **kwargs: Any) -> Any:
        """Temporarily override one or more settings fields.

        Creates a fresh Settings instance with the overridden values for
        the duration of the context block.  All references to the module-level
        ``settings`` singleton are swapped out atomically.

        Usage::

            with Settings.override(CHROMA_PERSIST_DIR="/tmp/test"):
                assert settings.CHROMA_PERSIST_DIR == "/tmp/test"
            # After exit, settings is restored to the original.
        """
        from core import settings as _mod

        original = _mod.settings
        _mod.settings = cls(**kwargs)  # type: ignore[arg-type]
        try:
            yield
        finally:
            _mod.settings = original


# Module-level singleton so downstream code does not need to pass it around.
def _make_settings() -> Settings:
    return Settings()


_settings: Settings = _make_settings()


def get_chunk_params(extension: str) -> tuple[int, int]:
    """Return ``(chunk_size, chunk_overlap)`` for *extension*.

    Falls back to global defaults when no override is configured.
    """
    ext = extension.lstrip(".") if extension.startswith(".") else f".{extension}"
    overrides = _settings.CHUNK_CONFIGS.get(ext, {})
    size = overrides.get("chunk_size", _settings.CHUNK_SIZE)
    overlap = overrides.get("chunk_overlap", _settings.CHUNK_OVERLAP)
    return size, overlap


# Export under the name ``settings`` so existing imports work unchanged.
settings: Settings = _settings
