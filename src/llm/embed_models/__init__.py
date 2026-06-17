"""OpenAI-compatible embedding model sub-package."""

from llm.embed_models.base import EmbeddingModel
from llm.embed_models.openai_compat import OpenAICompatEmbeddings

__all__ = ["EmbeddingModel", "OpenAICompatEmbeddings"]
