"""File indexer: scans, chunks, and persists documents into ChromaDB."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import logging
import re
from pathlib import Path

import chromadb

from core.settings import settings
from llm import get_embedding_model
from mcp_server.schemas import IndexFolderOutput
from retrieval.bm25_store import Bm25Store
from retrieval.embedding_fn import make_chroma_embedding_fn

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Entity-ID extraction from filenames
# ---------------------------------------------------------------------------

# Matches filenames like "scp_SCP-002.md" or "scp_EX-Special.md" → group(1) = entity ID.
# Handles patterns: scp_ENTITY.ext, mtf_ENTITY.ext, site_ENTITY.ext (separator can be
# underscore, hyphen, or dot).  Entity itself may contain hyphens and digits.
_ENTITY_RE: re.Pattern[str] = re.compile(
    r"^(?:scp|mtf|site)[-_.]?(.+?)\.(?:md|txt|py|js|ts|json|yaml|yml)$",
    re.IGNORECASE,
)


def _extract_entity_id(filename: str) -> str | None:
    """Extract the entity identifier from a source filename.

    Parameters
    ----------
    filename : str
        The relative file path (e.g. ``"scp/scp_SCP-002.md"``).

    Returns
    -------
    str | None
        The extracted entity ID (e.g. ``"SCP-002"``) or ``None`` if no pattern
        matches.
    """
    base = Path(filename).stem  # removes extension
    m = _ENTITY_RE.match(base)
    if m:
        return m.group(1)
    # Fallback: try matching just the basename without directory prefix
    basename = Path(filename).name
    m = _ENTITY_RE.match(basename)
    if m:
        return m.group(1)
    return None


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

    _SOURCE_FOLDER_KEY = "_meta:__source_folder__"

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
        self._embed_kwargs = embed_kwargs  # Save for recreation

        self._collection = self._client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine"},
            **embed_kwargs,
        )
        # Dedicated small collection tracking {filepath -> {hash, chunk_ids}}
        self._hash_collection = self._client.get_or_create_collection(
            name=_HASH_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

        # Load the previously indexed source folder path (persists across
        # Indexer instantiations so incremental sync can detect folder switches).
        self._source_folder = self._load_source_folder()

    def _clear_all_collections(self) -> None:
        """Delete and recreate both ChromaDB collections from scratch.

        Also resets the BM25 on-disk index and in-memory state so that a new
        folder path does not inherit stale tokens or file-hash entries from the
        previous indexing session.
        """
        logger.info("Clearing all indexed data (new folder path detected)")
        try:
            self._client.delete_collection(name=settings.CHROMA_COLLECTION)
        except Exception:  # noqa: BLE001
            pass
        try:
            self._client.delete_collection(name=_HASH_COLLECTION)
        except Exception:  # noqa: BLE001
            pass
        # Recreate the main collection with embedding function
        self._collection = self._client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine"},
            **self._embed_kwargs,
        )
        # Recreate the hash collection without embeddings
        self._hash_collection = self._client.get_or_create_collection(
            name=_HASH_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        # Clear the shared BM25 persisted index — it lives outside ChromaDB but
        # must stay in sync with the vector store.
        bm25_persist = f"{self._persist_dir}/bm25_index"
        bm25_store = Bm25Store(persist_dir=bm25_persist)
        bm25_store.clear()
        del bm25_store  # no lingering reference

        # Also clear the global code-file token map used by BM25 entity boosting;
        # stale mappings from the old index would corrupt future searches.
        try:
            from retrieval.retriever import _CODE_FILE_MAP  # noqa: F401

            _CODE_FILE_MAP.clear()
        except ImportError:  # pragma: no cover — retriever may not be installed
            pass

    def _load_source_folder(self) -> str | None:
        """Load the previously indexed source folder path, if any."""
        try:
            data = self._hash_collection.get(
                ids=[self._SOURCE_FOLDER_KEY], include=["documents"]
            )
            if data and data["documents"] and data["documents"][0]:
                return data["documents"][0]
        except Exception:  # noqa: BLE001
            pass
        return None

    def _save_source_folder(self, folder_path: str) -> None:
        """Persist the current source folder path."""
        self._hash_collection.upsert(
            ids=[self._SOURCE_FOLDER_KEY],
            documents=[folder_path],
            metadatas=[{"source": "__source_folder__"}],
        )

    # -- public API -----------------------------------------------------------

    def index_folder(
        self, folder_path: str, glob_pattern: str = "*"
    ) -> IndexFolderOutput:
        """Index every supported file under *folder_path*.

        Each call clears any previously indexed data and indexes the requested
        folder from scratch.  This ensures that switching to a different source
        folder always yields a clean, consistent index — no stale chunks or
        mismatched hash entries survive across calls.

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
        current_folder = str(base)

        # Detect whether we switched to a different folder by reading the
        # persisted source-folder sentinel stored in ChromaDB.  This works
        # even when a fresh Indexer() is instantiated per MCP request because
        # the path survives on-disk across process boundaries.
        if self._source_folder and self._source_folder != current_folder:
            logger.info(
                "Switching from folder '%s' to '%s' — clearing all data",
                self._source_folder,
                current_folder,
            )
            self._clear_all_collections()
            # _clear_all_collections already re-creates both collections
            # internally, but reload the persisted path since it was wiped.
            self._source_folder = None
        # else: first-ever index or same folder → proceed (incremental sync)

        # Always update the persisted folder path after any successful index.

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
        new_hashes: dict[str, str] = {}  # rel_path -> hash
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
        if removed_paths:
            logger.debug("Deleting chunks for %d removed files", len(removed_paths))
        for rel in removed_paths:
            entry = prev_hashed[rel]
            chunk_ids = entry.get("chunk_ids", [])
            if chunk_ids:
                self._collection.delete(ids=chunk_ids)
                logger.info(
                    "Removed %d chunks for deleted file: %s", len(chunk_ids), rel
                )

        logger.debug(
            "Will re-index %d files, skip %d unchanged",
            len(changed_files),
            len(unchanged_files),
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

            # Extract entity ID from filename and append as a lightweight suffix
            # to every chunk of markdown/text files so that BM25 can match queries
            # mentioning that entity even when a specific content chunk doesn't
            # mention it directly (cross-language retrieval).  A minimal suffix
            # avoids shifting primary-content BM25 scores significantly.
            entity_id = (
                _extract_entity_id(rel) if ext.lower() in {".md", ".txt"} else None
            )

            # Also append filename stem (without extension) as a BM25 keyword
            # so code-file queries can match on the source filename itself.
            # E.g. "scp_rpg" from "code/scp_rpg.py", "scp-slots" from
            # "code/scp-slots.ts".
            file_stem = Path(rel).stem

            new_chunk_ids: list[str] = []
            for idx, chunk in enumerate(split_result.chunks):
                chunk_id_val = f"{rel}::chunk-{idx}"
                new_chunk_ids.append(chunk_id_val)
                all_ids.append(chunk_id_val)
                # Build BM25 document text: original content + optional entity ID
                # + filename stem for cross-file keyword matching.
                parts = [chunk.content]
                if entity_id:
                    parts.append(entity_id)
                parts.append(file_stem)
                doc_content = " ".join(parts)
                all_documents.append(doc_content)
                all_metadatas.append(
                    {
                        "source": rel,
                        "chunk_index": idx,
                        "file_extension": ext,
                        "file_hash": file_hash,
                        "__file_path": str(file_path),
                        "__clean_content": chunk.content,  # original text without enrichment
                        "position_start": chunk.position_start,
                        "position_end": chunk.position_end,
                        **chunk.metadata,
                    }
                )

            # Persist hash entry for this file
            self._upsert_hash_entry(rel, file_hash, new_chunk_ids)

        # --- Upsert all new/changed data in ChromaDB --------------------------
        if all_ids:
            logger.debug(
                "Upserting %d chunks into ChromaDB collection '%s'",
                len(all_ids),
                settings.CHROMA_COLLECTION,
            )
            self._collection.upsert(
                ids=all_ids,
                documents=all_documents,
                metadatas=all_metadatas,  # type: ignore[arg-type]
            )

        refreshed_count = self._collection.count()

        # Persist the source folder path so future Indexer instances can
        # detect folder switches even across process boundaries.
        self._save_source_folder(current_folder)

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
        logger.debug(
            "Hash entry updated: source=%s chunks=%d", rel_path, len(chunk_ids)
        )

    def _load_prev_hashes(self) -> dict[str, dict]:
        """Load all previously tracked file-hash entries.

        Returns a dict mapping *rel_path* -> {file_hash, chunk_ids}.
        """
        result: dict[str, dict] = {}
        try:
            data = self._hash_collection.get(include=["metadatas"])
            if data and data["ids"]:
                metadatas = data["metadatas"] or []
                for _eid, meta_dict in zip(data["ids"], metadatas):
                    source = meta_dict.get("source", "")
                    if not source:
                        continue
                    try:
                        chunk_ids_raw = meta_dict.get("chunk_ids", "[]")
                        if isinstance(chunk_ids_raw, str):
                            parsed: list[str] = json.loads(chunk_ids_raw)
                            chunk_ids = parsed if isinstance(parsed, list) else []
                        elif isinstance(chunk_ids_raw, list):
                            chunk_ids = [str(c) for c in chunk_ids_raw]
                        else:
                            chunk_ids = []
                    except json.JSONDecodeError, TypeError:
                        chunk_ids = []

                    result[source] = {  # type: ignore[typeddict-item]
                        "file_hash": str(meta_dict.get("file_hash", "")),
                        "chunk_ids": chunk_ids,
                    }
            logger.debug("Loaded %d previous hash entries", len(result))
        except Exception:  # noqa: BLE001
            logger.debug("No previous hash metadata found — full re-index assumed")
        return result
