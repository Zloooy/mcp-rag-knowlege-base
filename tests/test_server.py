"""Tests for the MCP server setup."""

from __future__ import annotations

import inspect
from pathlib import Path


class TestServerSetup:
    """Verify the FastMCP server initializes correctly."""

    def test_server_creation(self) -> None:
        """Verify the server module defines a FastMCP instance and tool functions.

        We avoid importing ``from mcp_server.server`` directly because doing so
        would trigger ``mcp.run()`` (which blocks). Instead we inspect the
        source file as a text blob.
        """
        src = (
            Path(__file__).resolve().parent.parent / "src" / "mcp_server" / "server.py"
        )
        code = src.read_text()

        # Check that FastMCP is imported from fastmcp
        assert "from fastmcp import FastMCP" in code

        # Check that mcp instance is created
        assert 'FastMCP("rag-knowledge-base")' in code

        # Check all four tools are registered with @mcp.tool(output_schema=...)
        assert "@mcp.tool(" in code
        assert "rag_index_folder" in code
        assert "rag_ask_question" in code
        assert "rag_find_relevant_docs" in code
        assert "rag_index_status" in code

    def test_tool_parameters(self) -> None:
        """Verify each tool function signature matches expectations."""
        from mcp_server.tools.index_folder import index_folder
        from mcp_server.tools.ask_question import ask_question
        from mcp_server.tools.find_relevant_docs import find_relevant_docs
        from mcp_server.tools.index_status import index_status

        # index_folder(path, glob_pattern="*")
        sig = inspect.signature(index_folder)
        params = list(sig.parameters.keys())
        assert "path" in params
        assert "glob_pattern" in params

        # ask_question(query)
        sig = inspect.signature(ask_question)
        params = list(sig.parameters.keys())
        assert "query" in params

        # find_relevant_docs(query, top_k=5)
        sig = inspect.signature(find_relevant_docs)
        params = list(sig.parameters.keys())
        assert "query" in params
        assert "top_k" in params

        # index_status() — no parameters
        sig = inspect.signature(index_status)
        assert len(sig.parameters) == 0
