"""Ollama chat model implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_ollama import ChatOllama

from llm.chat_models.base import ChatModel

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel


class OllamaChat(ChatModel):
    """Wrapper around ``langchain_ollama.ChatOllama``.

    Reads model name from ``settings.OLLAMA_MODEL`` and temperature from
    ``settings.OLLAMA_TEMPERATURE`` at construction time.

    Because it holds a ``ChatOllama`` instance internally, the wrapper is
    fully compatible with LangChain's ``BaseChatModel`` protocol and can be
    used in chains like ``prompt | llm`` (via ``get_underlying()``).
    """

    _model: ChatOllama

    def __init__(self, model: str, temperature: float) -> None:
        self._model = ChatOllama(model=model, temperature=temperature)

    # -- ChatModel protocol ---------------------------------------------------

    def invoke(self, prompt: Any) -> Any:
        return self._model.invoke(prompt)

    def get_underlying(self) -> BaseChatModel:
        return self._model
