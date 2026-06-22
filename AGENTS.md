# AGENTS.md — MCP RAG Knowledge Base

## Quick start
- **Dependency manager:** `uv` (lockfile at `uv.lock`). Never use `pip install`.
- **Python version:** 3.14 (see `.python-version`)
- **Run tests:** `uv run pytest tests/ -v`
- **Single test:** `uv run pytest tests/test_file.py::test_name -v`
- **Start the server:** `uv run .` (runs `__main__.py`; no need for `PYTHONPATH=src` — it self-injects)
- **HTTP transport:** `uv run . --transport streamable-http --port 8000`

## Architecture
MCP server that turns local documents into a searchable RAG knowledge base. Uses LangGraph Corrective RAG pipeline with hybrid retrieval (BM25 + vector → RRF).

```
src/
├── core/settings.py        # Pydantic BaseSettings — all env vars, constants, tuning params
├── core/logging.py         # Logging setup called by __main__.py
├── mcp_server/             # MCP tool definitions & registration
│   ├── server.py           # FastMCP server — 4 tools registered here
│   ├── schemas.py          # Output Pydantic models per tool
│   ├── tool_descriptions.py # Tool descriptions for LLM agent prompts
│   └── tools/              # Individual tool implementations
├── graph/                  # LangGraph Corrective RAG pipeline
│   ├── builder.py          # StateGraph construction
│   ├── nodes.py            # Node functions + _load_prompt() for prompts/*.md
│   ├── edges.py            # Conditional routing (should_broaden)
│   └── state.py            # RAGState TypedDict schema
├── document_processing/    # Document parsing & chunking
│   ├── factory.py          # Splitter factory (dispatches by extension)
│   ├── base.py             # Base splitter interface
│   ├── text_splitter.py    # .txt splitter
│   ├── code_splitter.py    # .py/.js/.ts (tree-sitter based)
│   ├── markdown_splitter.py
│   └── yaml_splitter.py    # .yaml/.yml
├── retrieval/              # Search & indexing layer
│   ├── indexer.py          # ChromaDB indexing pipeline
│   ├── retriever.py        # Hybrid retriever (BM25 + vector → RRF)
│   └── bm25_store.py       # BM25 inverted index
prompts/                    # LLM prompt templates (*.md)
rag_dataset/demo_documents/ # Sample documents for testing
chroma_db/                  # Persisted ChromaDB store (gitignored)
```

### LangGraph flow (Corrective RAG)
```
query → rewrite_query → retrieve (hybrid BM25+vector→RRF) → grade_chunks
                                                    │
                                    enough relevant? ├─yes→ generate_answer → END
                                    no + budget left└─no→ broaden_and_retry → (loop back to retrieve)
```

### Key defaults in `src/core/settings.py`
- `CHUNK_SIZE=500`, `CHUNK_OVERLAP=50`
- `MIN_RELEVANT_CHUNKS=3`, `MAX_BROADEN_LOOPS=2`
- ChromaDB persist dir: `RAG_CHROMA_PERSIST_DIR` (default `./chroma_db`)
- LLM model: `RAG_OLLAMA_MODEL` (default `"qwen2.5:3b"`)
- Retrieval: `RETRIEVE_TOP_K=10`, `VECTOR_OVERSAMPLE_FACTOR=3`
- Supported extensions: `.md`, `.txt`, `.py`, `.js`, `.ts`, `.json`, `.yaml`

### Test settings override
Use `Settings.override()` context manager in `tests/conftest.py` fixtures and tests:

```python
from core.settings import Settings

with Settings.override(CHROMA_PERSIST_DIR="/tmp/chroma_test"):
    # code that needs a different persist dir
```

## Gotchas
- **Server entry point:** Run via `uv run .` (runs `__main__.py`). Do not try `python -m mcp.server` — that module does not exist. `__main__.py` self-injects `src/` on `sys.path`.
- **Prompts are files, not inline strings.** All LLM prompts live in `prompts/*.md` and are loaded at runtime via `_load_prompt()` in `src/graph/nodes.py`. Paths resolved relative to project root.
- **Tool registration is centralized.** All four MCP tools are in `src/mcp_server/server.py`. Entry points import from it — never duplicate.
- **Settings imports.** Use `from core.settings import settings` or `Settings`. Never import from `mcp_server.config` — removed.
- **ChromaDB collection name:** `rag_knowledge_base` (env: `RAG_CHROMA_COLLECTION`). Tests use `chroma_dir` fixture; populate with `populated_index` fixture.
- **Formatter:** `black` configured in `.opencode/opencode.jsonc`. Run `black <file>` or format on save.
- **.env prefix:** All env vars use `RAG_` prefix (e.g. `RAG_CHUNK_SIZE`, `RAG_OLLAMA_MODEL`). See `.env.example`.

## CI
GitHub Actions workflows in `.github/workflows/`:
- **lint.yml** — `black --check .` + `pyright src/`
- **test.yml** — `uv run pytest tests/ -v` (Python 3.14)

## Docker
Build and run with `docker-compose up`. Mount documents via `DOCUMENTS_PATH` env var. Default transport is `streamable-http` on port 8000. Requires gcc/g++ for tree-sitter native extensions (handled in Dockerfile).
