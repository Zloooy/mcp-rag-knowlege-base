"""Allow running as ``uv run .``."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is on the path so local packages (mcp_server, graph, etc.)
# can be imported regardless of how this module was invoked.
_project_root = Path(__file__).resolve().parent
_src_dir = str(_project_root / "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from mcp_server.server import run_server

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run the MCP RAG server")
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "streamable-http"],
        help="Transport type (default: stdio)",
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to bind (default: 8000)"
    )
    args = parser.parse_args()

    run_server(transport=args.transport, host=args.host, port=args.port)
