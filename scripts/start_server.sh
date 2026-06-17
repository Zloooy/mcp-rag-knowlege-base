#!/bin/bash
# Start the RAG knowledge base MCP server.
# Usage: uv run bash scripts/start_server.sh
set -e
cd "$(dirname "$0")/.."
exec uv run --with "mcp[server]" PYTHONPATH="$PWD/src" python3 src/main.py
