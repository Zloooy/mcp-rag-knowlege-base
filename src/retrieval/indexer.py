"""File indexer: scans, chunks, and persists documents into ChromaDB."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import logging
from pathlib import Path

import chromadb

from core.settings import settings
from llm import get_embedding_model
from mcp_server.schemas import IndexFolderOutput
from retrieval.embedding_fn import make_chroma_embedding_fn

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# File-hash metadata collection management
# ---------------------------------------------------------------------------

_HASH_COLLECTION = "file_hashes"


def _hash_file(path: Path) -> str:
    """Return SHA-256 hex digest of *path* file contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Indexer
# ---------------------------------------------------------------------------


class Indexer:
    """Scan a directory, chunk files, and store embeddings in ChromaDB."""

    def __init__(self, persist_dir: str | None = None) -> None:
        self._persist_dir = persist_dir or settings.CHROMA_PERSIST_DIR
        self._client = chromadb.PersistentClient(path=self._persist_dir)

        from typing import Any

        embed_model = get_embedding_model()
        embed_kwargs: dict[str, Any] = {}
        if embed_model is not None:
            chroma_ef = getattr(embed_model, "_embeddings", None)
            if chroma_ef is not None:
                embed_kwargs["embedding_function"] = make_chroma_embedding_fn(
                    chroma_ef, name="langchain_openai_embeddings"
                )

        self._collection = self._client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine"},
            **embed_kwargs,
        )
        # Dedicated small collection tracking {filepath → {hash, chunk_ids}}
        self._hash_collection = self._client.get_or_create_collection(
            name=_HASH_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

    # -- public API -----------------------------------------------------------

    def index_folder(
        self, folder_path: str, glob_pattern: str = "*"
    ) -> IndexFolderOutput:
        """Index every supported file under *folder_path*.

        On re-index: unchanged files are skipped; removed files are cleaned up.

        Parameters
        ----------
        folder_path:
            Absolute or relative path to the directory to scan.
        glob_pattern:
            Unix shell-style glob used to filter file names (default ``"*"``).

        Returns
        -------
        IndexFolderOutput with current state counts.
        """
        base = Path(folder_path).resolve()
        if not base.is_dir():
            raise FileNotFoundError(f"Folder not found: {folder_path}")

        files = sorted(
            tuple(
                filter(
                    lambda f: f.is_file()
                    and f.suffix.lower() in settings.SUPPORTED_EXTENSIONS
                    and fnmatch.fnmatch(f.name, glob_pattern),
                    base.rglob("*"),
                )
            )
        )

        if not files:
            logger.warning("No matching files in %s", folder_path)
            return IndexFolderOutput(
                indexed_count=0,
                total_chunks=0,
                message="No matching files found",
            )

        # --- Load previously tracked hashes -----------------------------------
        prev_hashed = self._load_prev_hashes()

        # --- Compute new hashes & classify -----------------------------------
        new_hashes: dict[str, str] = {}  # rel_path → hash
        changed_files: list[tuple[Path, str]] = []  # (file_path, hash)
        unchanged_files: list[tuple[str, str]] = []  # (rel_path, hash)

        for file_path in files:
            rel = str(file_path.relative_to(base))
            h = _hash_file(file_path)
            new_hashes[rel] = h

            prev_entry = prev_hashed.get(rel)
            if prev_entry and prev_entry.get("file_hash") == h:
                unchanged_files.append((rel, h))
            else:
                changed_files.append((file_path, h))

        # --- Delete chunks for removed files ----------------------------------
        removed_paths = set(prev_hashed.keys()) - set(new_hashes.keys())
        for rel in removed_paths:
            entry = prev_hashed[rel]
            chunk_ids = entry.get("chunk_ids", [])
            if chunk_ids:
                self._collection.delete(ids=chunk_ids)
                logger.info(
                    "Removed %d chunks for deleted file: %s", len(chunk_ids), rel
                )

        # --- Re-chunk changed / new files ------------------------------------
        all_ids: list[str] = []
        all_documents: list[str] = []
        all_metadatas: list[dict] = []

        for file_path, file_hash in changed_files:
            try:
                text = file_path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                logger.error("Cannot read %s: %s", file_path, exc)
                continue

            rel = str(file_path.relative_to(base))
            ext = file_path.suffix

            from document_processing import get_splitter

            splitter = get_splitter(ext)
            split_result = splitter.split(text, rel, ext)

            new_chunk_ids: list[str] = []
            for idx, chunk in enumerate(split_result.chunks):
                chunk_id_val = f"{rel}::chunk-{idx}"
                new_chunk_ids.append(chunk_id_val)
                all_ids.append(chunk_id_val)
                all_documents.append(chunk.content)
                all_metadatas.append(
                    {
                        "source": rel,
                        "chunk_index": idx,
                        "file_extension": ext,
                        "file_hash": file_hash,
                        **chunk.metadata,
                    }
                )

            # Persist hash entry for this file
            self._upsert_hash_entry(rel, file_hash, new_chunk_ids)

        # --- Upsert all new/changed data in ChromaDB --------------------------
        if all_ids:
            self._collection.upsert(
                ids=all_ids,
                documents=all_documents,
                metadatas=all_metadatas,
            )

        refreshed_count = self._collection.count()

        return IndexFolderOutput(
            indexed_count=len(new_hashes),
            total_chunks=refreshed_count,
            message=f"Indexed {len(new_hashes)} files ({refreshed_count} chunks)",
        )

    # -- internal helpers -----------------------------------------------------

    @staticmethod
    def _get_setting(name: str):
        """Lazy-access settings."""
        from core.settings import settings

        return getattr(settings, name)

    def _hash_entry_id(self, rel_path: str) -> str:
        """ChromaDB ID for a file-hash metadata entry."""
        safe = rel_path.replace("/", "__").replace("\\", "__")
        return f"_meta:{safe}"

    def _upsert_hash_entry(
        self, rel_path: str, file_hash: str, chunk_ids: list[str]
    ) -> None:
        """Store or update a single file-hash metadata entry."""
        eid = self._hash_entry_id(rel_path)
        meta: dict = {
            "file_hash": file_hash,
            "chunk_ids": json.dumps(chunk_ids),
            "source": rel_path,
        }
        doc_str = json.dumps(meta)
        self._hash_collection.upsert(ids=[eid], documents=[doc_str], metadatas=[meta])

    def _load_prev_hashes(self) -> dict[str, dict]:
        """Load all previously tracked file-hash entries.

        Returns a dict mapping *rel_path* → {file_hash, chunk_ids}.
        """
        result: dict[str, dict] = {}
        try:
            data = self._hash_collection.get(include=["metadatas"])
            if data and data["ids"]:
                for _eid, meta_dict in zip(data["ids"], data["metadatas"]):
                    source = meta_dict.get("source", "")
                    if not source:
                        continue
                    try:
                        chunk_ids_raw = meta_dict.get("chunk_ids", "[]")
                        if isinstance(chunk_ids_raw, str):
                            chunk_ids: list[str] = json.loads(chunk_ids_raw)
                        else:
                            chunk_ids = chunk_ids_raw
                    except json.JSONDecodeError, TypeError:
                        chunk_ids = []

                    result[source] = {
                        "file_hash": meta_dict.get("file_hash", ""),
                        "chunk_ids": chunk_ids,
                    }
        except Exception:  # noqa: BLE001
            logger.debug("No previous hash metadata found — full re-index assumed")
        return result
