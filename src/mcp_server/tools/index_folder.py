"""MCP tool: index_folder."""

from __future__ import annotations

import logging

from mcp_server.schemas import IndexFolderOutput
from retrieval import Indexer

logger = logging.getLogger(__name__)


def index_folder(path: str, glob_pattern: str = "*") -> IndexFolderOutput:
    """Scan a folder for document files (.md, .txt, .py, .js, .ts, .json, .yaml),
    split them into chunks, generate embeddings, and store them in the knowledge base
    vector database. Use this to add new documents to the searchable knowledge base.
    """
    try:
        indexer = Indexer()
        result: IndexFolderOutput = indexer.index_folder(
            folder_path=path, glob_pattern=glob_pattern
        )
        return result
    except Exception as exc:  # noqa: BLE001
        logger.exception("index_folder failed")
        return IndexFolderOutput(
            indexed_count=0, total_chunks=0, message=f"Error: {exc}"
        )
