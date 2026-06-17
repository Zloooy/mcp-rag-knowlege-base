"""OpenAI-compatible chat model sub-package."""

from llm.chat_models.base import ChatModel
from llm.chat_models.ollama import OllamaChat
from llm.chat_models.openai_compat import OpenAICompatChat

__all__ = ["ChatModel", "OllamaChat", "OpenAICompatChat"]
