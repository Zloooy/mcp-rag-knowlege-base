"""OpenAI-compatible API chat model implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_openai import ChatOpenAI

from llm.chat_models.base import ChatModel

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel


class OpenAICompatChat(ChatModel):
    """Wrapper around ``langchain_openai.ChatOpenAI``.

    Supports any OpenAI-compatible API endpoint (not just OpenAI itself) by
    accepting a custom base URL, model name, and API key.

    Parameters
    ----------
    base_url : str
        The API base URL (e.g. ``http://localhost:11434/v1``).
    model : str
        Model name to use (e.g. ``gpt-4o``, ``llama-3``).
    api_key : str
        API key for authenticating with the provider.
    """

    _model: ChatOpenAI

    def __init__(self, base_url: str, model: str, api_key: str) -> None:
        self._model = ChatOpenAI(
            model=model,
            base_url=base_url,
            api_key=api_key,  # type: ignore[arg-type]
            timeout=60,
            max_retries=2,
        )

    # -- ChatModel protocol ---------------------------------------------------

    def invoke(self, prompt: Any) -> Any:
        return self._model.invoke(prompt)

    def get_underlying(self) -> BaseChatModel:
        return self._model
