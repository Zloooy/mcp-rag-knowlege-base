"""Ollama chat model implementation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from langchain_core.messages import AIMessage
from langchain_ollama import ChatOllama

from llm.chat_models.base import ChatModel

logger = logging.getLogger(__name__)


def _extract_response_text(result: Any) -> str:
    """Extract the text content from an LLM invoke result."""
    if isinstance(result, AIMessage):
        raw = result.content or ""
        if isinstance(raw, str):
            return raw.strip()
        parts: list[str] = []
        for block in raw:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(str(block.get("text", "")))
        return " ".join(parts).strip()
    content = getattr(result, "content", None)
    if content is None:
        return ""
    if isinstance(content, str):
        return content.strip()
    if callable(content):
        return ""
    return str(content).strip()


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

    def __init__(
        self, model: str, temperature: float, base_url: str | None = None
    ) -> None:
        self._model = ChatOllama(
            model=model, temperature=temperature, base_url=base_url
        )

    # -- ChatModel protocol ---------------------------------------------------

    def invoke(self, prompt: Any) -> Any:
        logger.debug(
            "[LLM] OllamaChat(model=%s) invoking with prompt_type=%s",
            self._model.model,
            type(prompt).__name__,
        )
        result = self._model.invoke(prompt)
        try:
            preview = _extract_response_text(result)[:200]
            logger.debug("[LLM] OllamaChat response preview: %s", preview)
        except Exception:  # noqa: BLE001 -- logging should never crash
            pass
        return result

    def get_underlying(self) -> BaseChatModel:
        return self._model
