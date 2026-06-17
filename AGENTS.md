# AGENTS.md — MCP RAG Knowledge Base

## Quick start
- **Dependency manager:** `uv` (lockfile at `uv.lock`). Never use `pip install` in this project.
- **Python version:** 3.14 (see `.python-version`)
- **Run tests:** `uv run pytest tests/ -v`
- **Run a single test:** `uv run pytest tests/test_file.py::test_name -v`
- **Start the server:** `uv run .` or `PYTHONPATH=src uv run python -m mcp.server`

## Architecture overview
This is an MCP (Model Context Protocol) server that turns a local folder of documents into a searchable RAG knowledge base.

```
src/
├── core/               # Shared domain layer
│   └── settings.py     # Pydantic BaseSettings — all env vars, constants, tuning params
├── mcp_server/         # MCP tool definitions & registration
│   ├── tools/          # 4 tools: index_folder, ask_question, find_relevant_docs, index_status
│   └── server.py       # FastMCP server definition
├── graph/              # LangGraph Corrective RAG pipeline
│   ├── builder.py      # StateGraph construction (START → rewrite → retrieve → grade → generate/broaden → END)
│   ├── nodes.py        # Node functions: rewrite_query, retrieve, grade_chunks, generate_answer, broaden
│   ├── edges.py        # Conditional routing logic (should_broaden)
│   └── state.py        # RAGState TypedDict schema
├── document_processing/  # Document parsing \& chunking
│   ├── factory.py      # Splitter factory (dispatches by file extension)
│   ├── base.py         # Base splitter interface
│   ├── text_splitter.py   # .md / .txt splitter
│   ├── code_splitter.py   # .py / .js / .ts splitter (tree-sitter based)
│   ├── markdown_splitter.py
│   └── yaml_splitter.py   # .yaml/.yml splitter
├── retrieval/          # Search \& indexing layer
│   ├── indexer.py      # ChromaDB indexing pipeline
│   ├── retriever.py    # Hybrid retriever (BM25 + vector → RRF)
│   └── bm25_store.py   # BM25 inverted index
prompts/                # LLM prompt templates (loaded at runtime by nodes.py)
chroma_db/              # Persisted ChromaDB store (gitignored)
rag_dataset/demo_documents/  # Sample documents for testing
```

### LangGraph flow (Corrective RAG)
```
query → rewrite_query → retrieve (hybrid BM25+vector→RRF) → grade_chunks
                                                    │
                                    enough relevant? ├─yes→ generate_answer → END
                                    no + budget left└─no→ broaden_and_retry → (loop back to retrieve)
```

Key config defaults in `src/core/settings.py` (Pydantic `BaseSettings`):
- `CHUNK_SIZE=500`, `CHUNK_OVERLAP=50`
- `MIN_RELEVANT_CHUNKS=3`, `MAX_BROADEN_LOOPS=2`
- ChromaDB persist dir: env var `RAG_CHROMA_PERSIST_DIR` (default `./chroma_db`)
- LLM model: env var `RAG_OLLAMA_MODEL` (default `"qwen2.5:3b"`)
- Retrieval top_k: `RETRIEVE_TOP_K=10`, `FIND_RELEVANT_DOCS_DEFAULT_TOP_K=5`
- Vector oversample factor: `VECTOR_OVERSAMPLE_FACTOR=3`

### Test settings override
Use `Settings.override()` context manager to temporarily change fields in tests:

```python
from core.settings import Settings

with Settings.override(CHROMA_PERSIST_DIR="/tmp/chroma_test"):
    # code that needs a different persist dir
```

## Gotchas & non-obvious details

### Tool registration is centralized
All four MCP tools are registered in `src/mcp_server/server.py`. Entry points (`__main__.py`) import from it — never duplicate tool definitions.

### Prompts are files, not inline strings
All LLM prompts live in `prompts/*.md` and are loaded at runtime via `_load_prompt()` in `src/graph/nodes.py`. The file paths are resolved relative to the project root, so prompts work regardless of CWD.

### Supported file types for indexing
Only these extensions are indexed: `.md`, `.txt`, `.py`, `.js`, `.ts`, `.json`, `.yaml`. Controlled by `Settings.SUPPORTED_EXTENSIONS` in `src/core/settings.py`.

### Settings imports
All settings live in `src/core/settings.py`. Import via `from core.settings import settings` or `from core.settings import Settings, get_chunk_params`. Never import from `mcp_server.config` — that module was removed.

### Test fixtures
`tests/conftest.py` sets up `sys.path` so local packages can be imported when running tests without PYTHONPATH. Fixtures include:
- `chroma_dir` — temp directory for isolated ChromaDB per test
- `sample_docs` — creates 4 small test files (`.md`, `.txt`, `.yaml`, `.py`)

### Formatting
OpenCode config (`opencode.jsonc`) uses `black` for Python formatting. Run `black <file>` or let OpenCode format on save.

### No CI yet
There is no `.github/workflows/` directory. Tests are run locally only.

## What NOT to do
- Don't add dependencies with `pip` — use `uv add <pkg>` instead
- Don't modify `chroma_db/` manually — it's managed by the indexer
- Don't put LLM prompt text inline in Python — always use `prompts/*.md`
