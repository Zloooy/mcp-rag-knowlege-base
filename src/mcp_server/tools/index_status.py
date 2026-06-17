"""MCP tool: index_status."""

from __future__ import annotations

import logging

import chromadb

from core.settings import settings
from mcp_server.schemas import IndexStatusOutput

logger = logging.getLogger(__name__)


def index_status() -> IndexStatusOutput:
    """Get statistics about the current knowledge base index: number of files indexed,
    number of chunks, collection name, and last update time. Use this to check if the
    knowledge base has been populated and how much content is available.
    """
    try:
        client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        collection = client.get_or_create_collection(name=settings.CHROMA_COLLECTION)

        count = collection.count()
        return IndexStatusOutput(
            is_indexed=count > 0,
            indexed_count=count,
            total_chunks=count,
            persist_dir=settings.CHROMA_PERSIST_DIR,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("index_status failed")
        return IndexStatusOutput(
            is_indexed=False,
            indexed_count=0,
            total_chunks=0,
            persist_dir=settings.CHROMA_PERSIST_DIR,
        )
