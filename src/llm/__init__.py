"""LLM provider abstraction layer.

Public API — import from this package:

    from llm import ChatModel, EmbeddingModel, get_chat_model, get_embedding_model

Provider-specific classes live in sub-packages:

    from llm.chat_models import OllamaChat, OpenAICompatChat
    from llm.embed_models import OpenAICompatEmbeddings
"""

from llm.chat_models.base import ChatModel
from llm.embed_models.base import EmbeddingModel
from llm.factory import get_chat_model, get_embedding_model

__all__ = [
    "ChatModel",
    "EmbeddingModel",
    "get_chat_model",
    "get_embedding_model",
]
