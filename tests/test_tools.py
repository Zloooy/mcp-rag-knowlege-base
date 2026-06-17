"""Tests for MCP tool registration and basic invocation."""

from __future__ import annotations

import sys
from pathlib import Path

from pydantic import BaseModel


class TestToolRegistration:
    """Verify all 4 tools are registered on the FastMCP server."""

    def test_all_tools_registered(self) -> None:
        """Check that the server module defines all four tools."""
        src = (
            Path(__file__).resolve().parent.parent / "src" / "mcp_server" / "server.py"
        )
        code = src.read_text()

        # Verify each tool function is wrapped with @mcp.tool(
        lines = code.splitlines()
        tool_decorators = [i for i, l in enumerate(lines) if "@mcp.tool(" in l]
        assert (
            len(tool_decorators) == 4
        ), f"Expected 4 @mcp.tool() decorators, found {len(tool_decorators)}"

        # Verify the decorated functions match expected names
        tool_names_found = []
        for idx in tool_decorators:
            next_line = lines[idx + 1].strip() if idx + 1 < len(lines) else ""
            if "def rag_index_folder" in next_line:
                tool_names_found.append("rag_index_folder")
            elif "def rag_ask_question" in next_line:
                tool_names_found.append("rag_ask_question")
            elif "def rag_find_relevant_docs" in next_line:
                tool_names_found.append("rag_find_relevant_docs")
            elif "def rag_index_status" in next_line:
                tool_names_found.append("rag_index_status")

        expected = {
            "rag_index_folder",
            "rag_ask_question",
            "rag_find_relevant_docs",
            "rag_index_status",
        }
        assert (
            set(tool_names_found) == expected
        ), f"Missing tools: {expected - set(tool_names_found)}"

    def test_tool_has_description(self) -> None:
        """Every registered tool should have a meaningful docstring (becomes description)."""
        from mcp_server.tools.index_folder import index_folder
        from mcp_server.tools.ask_question import ask_question
        from mcp_server.tools.find_relevant_docs import find_relevant_docs
        from mcp_server.tools.index_status import index_status

        tools = [
            ("rag_index_folder", index_folder),
            ("rag_ask_question", ask_question),
            ("rag_find_relevant_docs", find_relevant_docs),
            ("rag_index_status", index_status),
        ]
        for name, fn in tools:
            desc = getattr(fn, "__doc__", "") or ""
            assert desc, f"Tool '{name}' has no docstring"
            assert (
                len(desc) > 20
            ), f"Tool '{name}' docstring too short ({len(desc)} chars)"


class TestToolInvocation:
    """Call each tool directly and verify structured responses."""

    def _as_dict(self, result: BaseModel) -> dict:
        """Helper: convert a Pydantic model result to a plain dict."""
        return result.model_dump()

    def test_index_folder_tool(self, sample_docs) -> None:
        from mcp_server.tools.index_folder import index_folder

        result = index_folder(str(sample_docs))
        assert isinstance(result, BaseModel)
        d = self._as_dict(result)
        assert d["indexed_count"] > 0
        assert d["total_chunks"] > 0

    def test_index_folder_tool_missing_path(self) -> None:
        from mcp_server.tools.index_folder import index_folder

        result = index_folder("/no/such/path")
        assert isinstance(result, BaseModel)
        d = self._as_dict(result)
        assert "message" in d

    def test_find_relevant_docs_tool_empty(self, empty_index) -> None:
        """Search an empty index should return zero results."""
        from core.settings import Settings, get_chunk_params, settings
        from mcp_server.tools.find_relevant_docs import find_relevant_docs

        # Override persist dir so this test uses its own empty ChromaDB
        with Settings.override(CHROMA_PERSIST_DIR=str(empty_index)):
            result = find_relevant_docs("test query")
            assert isinstance(result, BaseModel)
            assert result.results == []

    def test_index_status_tool(self, chroma_dir) -> None:
        from core.settings import Settings
        from mcp_server.tools.index_status import index_status

        with Settings.override(CHROMA_PERSIST_DIR=str(chroma_dir)):
            result = index_status()
            assert isinstance(result, BaseModel)
            d = self._as_dict(result)
            assert "is_indexed" in d
            assert "total_chunks" in d
            assert "persist_dir" in d
            assert "indexed_count" in d
