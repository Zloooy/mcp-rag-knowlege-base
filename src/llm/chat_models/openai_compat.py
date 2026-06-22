"""OpenAI-compatible API chat model implementation."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from llm.chat_models.base import ChatModel

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel


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
    _model_name: str
    _base_url: str

    def __init__(self, base_url: str, model: str, api_key: str) -> None:
        self._model_name = model
        self._base_url = base_url
        self._model = ChatOpenAI(
            model=model,
            base_url=base_url,
            api_key=api_key,  # type: ignore[arg-type]
            timeout=60,
            max_retries=2,
        )

    # -- ChatModel protocol ---------------------------------------------------

    def invoke(self, prompt: Any) -> Any:
        logger.debug(
            "[LLM] ChatOpenAI(model=%s, url=%s) invoking with prompt_type=%s",
            self._model_name,
            self._base_url.split("://")[0],  # redact scheme/path, keep protocol prefix
            type(prompt).__name__,
        )
        result = self._model.invoke(prompt)
        try:
            preview = _extract_response_text(result)[:200]
            logger.debug("[LLM] ChatOpenAI response preview: %s", preview)
        except Exception:  # noqa: BLE001 -- logging should never crash
            pass
        return result

    def get_underlying(self) -> BaseChatModel:
        return self._model
