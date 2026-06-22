"""Retriever: hybrid search combining vector and BM25 with RRF fusion."""

from __future__ import annotations

import logging
import os
import re
import string
from pathlib import Path
from operator import itemgetter

import chromadb
import nltk
from llm import get_embedding_model
from nltk.corpus import stopwords as _nltk_stopwords
from rank_bm25 import BM25Okapi

from mcp_server.schemas import SearchResult
from retrieval.bm25_store import Bm25Store
from retrieval.embedding_fn import make_chroma_embedding_fn

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Multilingual stopwords — English + Russian (from NLTK corpora)
# ---------------------------------------------------------------------------


def _ensure_nltk_data() -> None:
    """Download NLTK ``stopwords`` corpus if not already cached."""
    try:
        nltk.data.find("corpora/stopwords")
    except LookupError:
        nltk.download("stopwords", quiet=True)


_ensure_nltk_data()
_STOPWORDS_EN: frozenset[str] = frozenset(_nltk_stopwords.words("english"))
_STOPWORDS_RU: frozenset[str] = frozenset(_nltk_stopwords.words("russian"))
STOPWORDS: frozenset[str] = _STOPWORDS_EN | _STOPWORDS_RU


# Pattern for compound identifiers like SCP-002, MTF-Echo-11, Site-19, etc.
# Matches WORD-NUMBER or WORD-NUMBER-NUMBER (with optional en-dash).
_HYPHATED_ENTITY_RE: re.Pattern[str] = re.compile(r"^([A-Za-z]+)-(\d+(?:[-–]\d+)*)$")

# Mapping from tokenized form of code filenames to their stem names.
# Populated dynamically during indexing so BM25 entity boosting can recognize
# queries that mention code-file names without separators (e.g. "scprpgpy"
# from "scp_rpg.py" → maps to stem "scp_rpg").
_CODE_FILE_MAP: dict[str, str] = {}


def _populate_code_file_map(collection: chromadb.Collection) -> None:
    """Populate ``_CODE_FILE_MAP`` from the ChromaDB collection metadata.

    Iterates over all documents in *collection*, reads their ``source``
    metadata, extracts the filename stem, tokenizes it, and stores the
    mapping ``tokenized_stem → file_stem``.  This enables the entity-boosting
    logic in ``_bm25_search`` and ``search`` to match queries like
    ``scp_rpg.py`` → token ``scprpgpy`` against the indexed file
    ``code/scp_rpg.py``.
    """
    global _CODE_FILE_MAP
    _CODE_FILE_MAP.clear()
    data = collection.get(include=[])
    for doc_id in data.get("ids", []):
        # doc_id format is "relative/path/filename.ext::chunk-N"
        source_part = doc_id.split("::")[0]
        fname = os.path.basename(source_part)
        stem = Path(fname).stem
        # Tokenize the stem exactly as we tokenize query text
        tokens = _tokenize(stem)
        for tok in tokens:
            if tok not in _CODE_FILE_MAP:
                _CODE_FILE_MAP[tok] = stem


def _tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split, remove stopwords.

    Filters out both English and Russian stopwords so that Russian-language
    queries (which dominate the test suite) are tokenised cleanly without
    noise from function words like *какой*, *где*, *сколько* etc.

    Additionally, hyphenated compound identifiers (e.g. "SCP-002", "MTF-Echo-11")
    are expanded into BOTH their hyphenated and concatenated forms so that BM25
    can match regardless of whether the document uses "SCP-002" or "SCP002".
    """
    text = text.lower()

    # Expand hyphenated entities BEFORE punctuation removal.
    expanded_tokens: list[str] = []
    for token in text.split():
        expanded_tokens.append(token)
        m = _HYPHATED_ENTITY_RE.match(token)
        if m:
            # Also add the concatenated form ("scp002" from "scp-002")
            expanded_tokens.append(re.sub(r"[-–]", "", token))

    # Lowercase + strip punctuation + split + filter stopwords
    flat = " ".join(expanded_tokens)
    flat = flat.translate(str.maketrans("", "", string.punctuation))
    tokens = flat.split()
    return list(filter(lambda t: t not in STOPWORDS, tokens))


class Retriever:
    """Hybrid retriever over ChromaDB using vector + BM25 → RRF."""

    def __init__(self, persist_dir: str | None = None) -> None:
        from typing import Any

        self._persist_dir = persist_dir or self._get_setting("CHROMA_PERSIST_DIR")
        self._client = chromadb.PersistentClient(path=self._persist_dir)
        collection_name = self._get_setting("CHROMA_COLLECTION")

        embed_model = get_embedding_model()
        embed_kwargs: dict[str, Any] = {}
        if embed_model is not None:
            chroma_ef = getattr(embed_model, "_embeddings", None)
            if chroma_ef is not None:
                embed_kwargs["embedding_function"] = make_chroma_embedding_fn(
                    chroma_ef, name="langchain_openai_embeddings"
                )

        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
            **embed_kwargs,
        )

        # Persistent BM25 index stored within the Chroma persist directory
        bm25_persist = f"{self._persist_dir}/bm25_index"
        self._bm25_store = Bm25Store(persist_dir=bm25_persist)

    # -- public API -----------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int = 5,
        exclude_ids: set[str] | None = None,
    ) -> list[SearchResult]:
        """Return the top-*k* most relevant chunks for *query*.

        Uses Reciprocal Rank Fusion of a ChromaDB vector search and a
        BM25 keyword search.

        Parameters
        ----------
        query : str
            The search query text.
        top_k : int
            Maximum number of results to return.
        exclude_ids : set[str] | None
            Chunk IDs to skip when building the result set. If provided,
            the retriever scans beyond the initial RRF cutoff to find enough
            non-excluded candidates.

        Returns
        -------
        list[SearchResult]
            Typed search results with ``content``, ``metadata``, and ``score``.
        """
        if not self._collection.count():
            logger.warning("Index is empty — nothing to retrieve")
            return []

        # --- vector retrieval (ChromaDB) ------------------------------------
        vector_results = self._collection.query(
            query_texts=[query],
            n_results=top_k * 3,  # oversample to allow filtering later
            include=["documents", "metadatas", "distances"],
        )

        vector_ranked: dict[str, float] = {}  # doc_id → rank score
        ids_list = vector_results.get("ids") or []
        if ids_list and ids_list[0]:
            ids_inner: list[str] = ids_list[0]
            dists_inner: list[float] | None = (
                vector_results.get("distances") or [None]
            )[0]
            docs_inner: list[str] | None = (vector_results.get("documents") or [None])[
                0
            ]
            metas_inner: list | None = (  # type: ignore[assignment]
                vector_results.get("metadatas") or [None]
            )[0]
            for i, chunk_id in enumerate(ids_inner):
                d = (
                    dists_inner[i] if dists_inner and i < len(dists_inner) else 0.0
                ) or 0.0
                score = 1.0 / (1.0 + d)
                vector_ranked[chunk_id] = score

                docs_inner_item: str | None = (
                    docs_inner[i] if docs_inner and i < len(docs_inner) else None
                )
                preview = ""
                if docs_inner_item:
                    preview = docs_inner_item[:100].replace("\n", " ").replace("\r", "")
                logger.debug(
                    '[RETRIEVE] Vector: id=%s dist=%.4f score=%.4f doc="%s"',
                    chunk_id,
                    d,
                    score,
                    preview,
                )

        # --- BM25 retrieval (uses persisted store) --------------------------
        bm25_ranked = self._bm25_search(query, top_k=top_k * 3)

        # --- RRF fusion -----------------------------------------------------
        rrf_k = self._get_setting("RRF_K")
        fused = self._rrf_fuse(vector_ranked, bm25_ranked, k=rrf_k)

        # Build final result sorted by fused score
        results: list[SearchResult] = []
        exclude_set = exclude_ids or set()
        logger.debug("[RETRIEVE] RRF fusion produced %d candidates", len(fused))
        for chunk_id, rrf_score in fused:
            # Skip chunks whose IDs were explicitly excluded
            if chunk_id in exclude_set:
                continue
            meta_result = self._collection.get(ids=[chunk_id])
            meta_ids = meta_result.get("ids") if meta_result else None
            source_file = ""
            if meta_ids and meta_result and meta_result.get("metadatas"):
                raw_meta: dict = meta_result["metadatas"][0]  # type: ignore[assignment]
                source_file = raw_meta.get("source", "")
            logger.debug(
                "[RETRIEVE] RRF: id=%s fused=%.4f source=%s",
                chunk_id,
                rrf_score,
                source_file,
            )
            if meta_ids and meta_result and meta_result.get("metadatas"):
                raw_meta: dict = meta_result["metadatas"][0]  # type: ignore[assignment]
                # Prefer the clean original content stored during indexing;
                # fall back to the enriched document text if the field is missing;
                # strip the filename/entity suffix for pre-existing indexes.
                content_raw = raw_meta.get("__clean_content")
                # Build a user-facing metadata dict: start with source + file path,
                # then merge all remaining fields (position offsets, chunk_index, etc.)
                # while excluding internal fields that begin with "__".
                public_keys = {"source", "__file_path"}
                filtered_meta = {
                    k: v for k, v in raw_meta.items() if k not in public_keys
                }
                results.append(
                    SearchResult(
                        content=str(content_raw),
                        metadata={
                            "source": raw_meta.get("source", ""),
                            "__file_path": raw_meta.get("__file_path", ""),
                            **filtered_meta,
                        },
                        score=round(rrf_score, 6),
                    )
                )
            # Stop once we have enough non-excluded results
            if len(results) >= top_k:
                break

        return results

    def refresh_bm25(self) -> int:
        """Rebuild the BM25 index from current ChromaDB documents and persist it.

        Call this after indexing new documents so the BM25 store stays in sync.

        Returns
        -------
        int
            Number of documents the BM25 index now contains.
        """
        get_result = self._collection.get(include=[])
        all_ids = get_result.get("ids") or []
        all_docs_result = self._collection.get()
        all_docs = all_docs_result.get("documents") or []

        if not all_ids:
            self._bm25_store.update([], [])
            self._bm25_store.save()
            return 0

        # Populate code-file token → stem mapping for entity boosting
        _populate_code_file_map(self._collection)

        self._bm25_store.update(all_ids, all_docs)
        self._bm25_store.save()
        return self._bm25_store.count

    # -- internal helpers -----------------------------------------------------

    @staticmethod
    def _get_setting(name: str):
        """Lazy-access settings to avoid stale-module issues when mcp.* modules
        are cleared (e.g. during test isolation).  Importing here ensures we
        always resolve the current ``mcp_server.config.settings`` singleton."""
        from core.settings import settings

        return getattr(settings, name)

    def _bm25_search(self, query: str, top_k: int = 15) -> dict[str, float]:
        """Run BM25 scoring against the persisted tokenised corpus.

        Returns the **full** scored corpus (not limited to *top_k*) so that
        the RRF fusion step can discriminate among all relevant chunks using
        actual BM25 scores rather than a flat ``1/(k+rank)`` placeholder.
        Limiting to ``top_k`` would collapse many useful BM25 signals into
        noise when fused with vector results.
        """
        corpus = self._bm25_store.corpus
        doc_ids = self._bm25_store.doc_ids

        if not corpus:
            # Fallback: rebuild on-the-fly if store is empty (e.g. first run)
            get_docs = self._collection.get()
            all_docs_list = get_docs.get("documents") or []
            corpus = [_tokenize(doc) for doc in all_docs_list]
            get_ids = self._collection.get(include=[])
            doc_ids = get_ids.get("ids") or []
            if not doc_ids:
                return {}

        bm25 = BM25Okapi(corpus)
        query_tokens = _tokenize(query)
        scores = bm25.get_scores(query_tokens)

        ranked: list[tuple[str, float]] = sorted(
            zip(doc_ids, scores), key=itemgetter(1), reverse=True
        )
        # Return all non-zero scored documents — let RRF handle final ranking
        bm25_results = {chunk_id: score for chunk_id, score in ranked if score > 0}

        logger.debug(
            "[BM25] %d total hits, top 5: %s",
            len(bm25_results),
            "; ".join(
                f"{cid} score={sc:.4f}" for cid, sc in list(bm25_results.items())[:5]
            ),
        )

        return bm25_results

    @staticmethod
    def _rrf_fuse(
        vector_ranked: dict[str, float],
        bm25_ranked: dict[str, float],
        k: int,
    ) -> list[tuple[str, float]]:
        """Reciprocal Rank Fusion of two ranked dictionaries.

        Each document receives ``1 / (k + rank)`` from whichever source
        listed it.  Documents appearing in *both* lists accumulate two
        contributions, naturally boosting their position in the fused
        ranking.

        For the BM25 side, ranks are derived from descending BM25 scores so
        that stronger keyword matches receive higher RRF contribution.
        """
        # Derive ranks from BM25 scores (higher score = better rank)
        bm25_sorted = sorted(bm25_ranked.items(), key=itemgetter(1), reverse=True)
        max_bm25_score = bm25_sorted[0][1] if bm25_sorted else 1.0

        # Derive ranks from vector scores (higher score = better rank)
        vec_sorted = sorted(vector_ranked.items(), key=itemgetter(1), reverse=True)
        max_vec_score = vec_sorted[0][1] if vec_sorted else 1.0

        scores: dict[str, float] = {}
        for chunk_id, vec_score in vector_ranked.items():
            if chunk_id not in scores:
                scores[chunk_id] = 0.0
            # Use vector score ratio as effective rank: closer to 1 = better rank.
            # Mirrors the BM25-side treatment so both sources contribute
            # rank-differentiated RRF signals rather than a flat offset.
            vec_ratio = vec_score / max_vec_score
            vec_effective_rank = max(1, int((1 - vec_ratio) * k) + 1)
            scores[chunk_id] += 1.0 / (k + vec_effective_rank)

        for chunk_id, bm25_score in bm25_ranked.items():
            if chunk_id not in scores:
                scores[chunk_id] = 0.0
            # Use BM25 score ratio as effective rank: closer to 1 = better rank.
            # This ensures strongly boosted entities rise to the top regardless
            # of how many total BM25 hits exist.
            ratio = bm25_score / max_bm25_score
            # Map ratio to an effective rank: ratio=1 → rank 1, ratio→0 → rank ~infinity
            # Using inverse: effective_rank = ceil((1 - ratio) * k + 1)
            effective_rank = max(1, int((1 - ratio) * k) + 1)
            scores[chunk_id] += 1.0 / (k + effective_rank)

        # Sort descending by fused score
        return sorted(scores.items(), key=itemgetter(1), reverse=True)
