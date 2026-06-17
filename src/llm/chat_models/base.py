"""Abstract interface for chat completion models."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel


class ChatModel(ABC):
    """Abstract interface for chat completion models.

    Concrete implementations wrap an underlying LangChain ``BaseChatModel``
    so they are fully chain-compatible (i.e. work with ``prompt | llm``).
    """

    @abstractmethod
    def invoke(self, prompt: Any) -> Any:
        """Invoke the model with a prompt / message sequence.

        Delegates to the underlying LangChain provider's ``invoke`` method.

        Parameters
        ----------
        prompt : Any
            A LangChain ``BasePromptTemplate``, list of messages, or any
            object accepted by the underlying provider's ``invoke`` method.

        Returns
        -------
        Any
            A response object (typically a ``AIMessage`` or similar) from
            the underlying provider.
        """

    @abstractmethod
    def get_underlying(self) -> "BaseChatModel":
        """Return the underlying LangChain-compatible model instance."""
