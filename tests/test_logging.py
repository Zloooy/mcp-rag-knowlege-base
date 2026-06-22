"""Comprehensive tests for the centralized logging system.

Tests cover ``setup_logging()``, ``is_debug_enabled()``, debug-level logger
propagation for project sub-loggers, and LLM/MCP tool debug logging with
``caplog`` fixtures.
"""

from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure src/ is on the path (conftest does this too but be explicit).
_project_root = Path(__file__).resolve().parent.parent
_src_dir = str(_project_root / "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)


def _reload_settings_module(monkeypatch: pytest.MonkeyPatch, log_level: str) -> None:
    """Set the RAG_LOG_LEVEL env var and reload the settings module so it picks up the new value."""
    monkeypatch.setenv("RAG_LOG_LEVEL", log_level)
    # Reload core.settings to pick up the new env var on the next access.
    # Also need to reload core.logging which imports from settings.
    from core import logging as _logging_mod
    from core import settings as _settings_mod

    importlib.reload(_settings_mod)
    importlib.reload(_logging_mod)


def _reset_logging() -> None:
    """Fully reset stdlib logging to a clean slate between tests."""
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.NOTSET)
    from core.logging import _DEBUG_LOGGERS

    for name in _DEBUG_LOGGERS:
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.setLevel(logging.NOTSET)
        # Also reset any child loggers recursively
        for child_name in list(logging.Logger.manager.loggerDict.keys()):
            if child_name.startswith(name + "."):
                child = logging.getLogger(child_name)
                child.handlers.clear()
                child.setLevel(logging.NOTSET)


class TestSetupLogging:
    """Test basic setup_logging behaviour and idempotency."""

    def teardown_method(self, method: object) -> None:
        """Reset logging handlers after each test so tests are independent."""
        _reset_logging()
        # Restore the default env var so subsequent tests start clean
        import os

        if "RAG_LOG_LEVEL" in os.environ:
            del os.environ["RAG_LOG_LEVEL"]
        # Reload settings/logging back to their defaults
        try:
            from core import logging as _logging_mod
            from core import settings as _settings_mod

            importlib.reload(_settings_mod)
            importlib.reload(_logging_mod)
        except Exception:
            pass

    def test_setup_logging_sets_correct_level(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """LOG_LEVEL=INFO -> root logger gets level 20, one handler."""
        _reload_settings_module(monkeypatch, "INFO")
        _reset_logging()
        from core.logging import setup_logging

        setup_logging()
        root = logging.getLogger()
        assert root.level == logging.INFO
        assert len(root.handlers) == 1

    def test_setup_logging_debug_level(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When LOG_LEVEL=DEBUG, root logger and all project
        sub-loggers get DEBUG."""
        _reload_settings_module(monkeypatch, "DEBUG")
        from core.logging import _DEBUG_LOGGERS, is_debug_enabled, setup_logging

        _reset_logging()
        setup_logging()
        root = logging.getLogger()
        assert root.level == logging.DEBUG

        for name in _DEBUG_LOGGERS:
            child = logging.getLogger(name)
            # effectiveLevel should be DEBUG because we explicitly set it
            assert child.level == logging.DEBUG

    def test_setup_logging_is_idempotent(self) -> None:
        """Calling setup_logging twice must not duplicate handlers."""
        _reset_logging()
        from core.logging import setup_logging

        setup_logging()
        first_count = len(logging.getLogger().handlers)

        setup_logging()
        second_count = len(logging.getLogger().handlers)

        assert first_count == second_count == 1

    def test_is_debug_enabled_returns_true_when_debug(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """is_debug_enabled should return True when LOG_LEVEL is DEBUG."""
        _reload_settings_module(monkeypatch, "DEBUG")
        from core.logging import is_debug_enabled, setup_logging

        setup_logging()
        assert is_debug_enabled() is True

    def test_is_debug_enabled_returns_false_when_info(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """is_debug_enabled should return False at INFO level."""
        _reload_settings_module(monkeypatch, "INFO")
        _reset_logging()
        from core.logging import is_debug_enabled, setup_logging

        setup_logging()
        assert is_debug_enabled() is False


class TestMCPLogging:
    """Test that MCP tools use the correct logger and emit messages."""

    def teardown_method(self, method: object) -> None:
        """Reset logging state after each test."""
        _reset_logging()
        import os

        if "RAG_LOG_LEVEL" in os.environ:
            del os.environ["RAG_LOG_LEVEL"]
        try:
            from core import logging as _logging_mod
            from core import settings as _settings_mod

            importlib.reload(_settings_mod)
            importlib.reload(_logging_mod)
        except Exception:
            pass

    def test_mcp_tool_logs_error_at_debug(self, tmp_path: Path) -> None:
        """index_status should emit a DEBUG log on failure via mcp_server logger.

        We force an error by pointing at a read-only location so ChromaDB cannot
        create its persistent store, triggering the ``logger.exception`` code path.
        """
        from core.settings import settings
        from mcp_server.tools.index_status import index_status

        persist_dir = str(tmp_path / "test_chroma_mcp")

        # Directly mutate the singleton so settings reads pick up the change
        settings.CHROMA_PERSIST_DIR = persist_dir

        _reset_logging()
        from core.logging import setup_logging

        setup_logging()

        # Add a dedicated handler to capture mcp_server debug messages
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(message)s"))
        mcp_logger = logging.getLogger("mcp_server")
        mcp_logger.addHandler(handler)
        mcp_logger.propagate = True

        # Force an error by making the persist dir unwritable
        import os

        readonly_dir = str(tmp_path / "readonly_chroma")
        os.makedirs(readonly_dir, exist_ok=True)
        os.chmod(readonly_dir, 0o000)
        settings.CHROMA_PERSIST_DIR = readonly_dir

        result = index_status()
        # Should return error response, not crash
        assert result.is_indexed is False

        # Restore permissions for cleanup
        os.chmod(readonly_dir, 0o755)

        # Read captured output from the handler's stream
        handler_stream = handler.stream
        handler_stream.seek(0)
        output = handler_stream.read()

        assert (
            "index_status" in output.lower()
        ), f"Expected 'index_status' in logs, got: {output!r}"

    def test_mcp_tool_no_debug_at_info_level(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """At INFO level, no DEBUG-level messages should appear for mcp_server."""
        from core.settings import Settings, settings
        from mcp_server.tools.index_status import index_status

        persist_dir = str(tmp_path / "test_chroma_mcp_no_debug")

        # Directly mutate the singleton
        original_persist = settings.CHROMA_PERSIST_DIR
        settings.CHROMA_PERSIST_DIR = persist_dir

        _reset_logging()
        from core.logging import setup_logging

        setup_logging()

        caplog.set_level(logging.DEBUG, logger="mcp_server")

        # Call tool -- nothing should be logged at DEBUG level since root is INFO
        result = index_status()
        assert result.is_indexed is False

        # Filter only DEBUG records from mcp_server
        debug_records = [
            r
            for r in caplog.records
            if r.levelno == logging.DEBUG and "mcp_server" in r.name
        ]
        assert (
            len(debug_records) == 0
        ), f"Unexpected DEBUG logs at INFO level: {debug_records}"


class TestLLMLogging:
    """Test that LLM chat models emit debug logs during invoke()."""

    def teardown_method(self, method: object) -> None:
        """Reset logging state after each test."""
        _reset_logging()
        import os

        if "RAG_LOG_LEVEL" in os.environ:
            del os.environ["RAG_LOG_LEVEL"]
        try:
            from core import logging as _logging_mod
            from core import settings as _settings_mod

            importlib.reload(_settings_mod)
            importlib.reload(_logging_mod)
        except Exception:
            pass

    def test_ollama_chat_logs_invoke(self, caplog: pytest.LogCaptureFixture) -> None:
        """OllamaChat.invoke should log model name, prompt type, and response preview."""
        from llm.chat_models.ollama import OllamaChat

        _reset_logging()
        from core.logging import setup_logging

        setup_logging()

        # Set the llm logger to DEBUG so messages are not filtered before
        # reaching the dedicated handler below.
        logger = logging.getLogger("llm")
        logger.setLevel(logging.DEBUG)

        # Use a dedicated handler since _reset_logging may have removed caplog's handler
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.propagate = True

        # Create a mock AIMessage and patch the underlying ChatOllama
        mock_result = MagicMock()
        mock_result.content = "This is a test response from the model."

        ollama = OllamaChat(model="qwen2.5:3b", temperature=0.0)
        # Patch at the class level because ChatOllama is a Pydantic model that
        # rejects arbitrary attribute assignments on instances.
        with patch.object(type(ollama._model), "invoke", return_value=mock_result):
            ollama.invoke("Hello!")

        # Read captured output from the handler's stream
        handler_stream = handler.stream
        handler_stream.seek(0)
        output = handler_stream.read()

        assert (
            "[LLM] OllamaChat" in output
        ), f"Missing '[LLM] OllamaChat' in logs: {output!r}"
        assert "invoking" in output.lower(), f"Missing 'invoking' in logs: {output!r}"
        assert (
            "response preview" in output.lower()
        ), f"Missing 'response preview' in logs: {output!r}"

    def test_openai_compat_chat_logs_invoke(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """OpenAICompatChat.invoke should log model name, url prefix, and response preview."""
        from llm.chat_models.openai_compat import OpenAICompatChat

        _reset_logging()
        from core.logging import setup_logging

        setup_logging()

        # Set the llm logger to DEBUG so messages are not filtered before
        # reaching the dedicated handler below.
        logger = logging.getLogger("llm")
        logger.setLevel(logging.DEBUG)

        # Use a dedicated handler since _reset_logging may have removed caplog's handler
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.propagate = True

        # Patch the underlying ChatOpenAI's invoke
        mock_result = MagicMock()
        mock_result.content = "OpenAI-compatible model response."

        llm = OpenAICompatChat(
            base_url="http://localhost:11434/v1",
            model="test-model",
            api_key="fake-key",
        )
        # Use patch.object to avoid Pydantic readonly-attribute errors
        with patch.object(type(llm._model), "invoke", return_value=mock_result):
            llm.invoke("Tell me about Python.")

        # Read captured output from the handler's stream
        handler_stream = handler.stream
        handler_stream.seek(0)
        output = handler_stream.read()

        assert (
            "[LLM] ChatOpenAI" in output
        ), f"Missing '[LLM] ChatOpenAI' in logs: {output!r}"
        assert "invoking" in output.lower(), f"Missing 'invoking' in logs: {output!r}"
        assert (
            "response preview" in output.lower()
        ), f"Missing 'response preview' in logs: {output!r}"
