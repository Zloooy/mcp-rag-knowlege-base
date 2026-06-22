# ARCHITECTURE.md — MCP RAG Knowledge Base

## High-level overview

This project is an **MCP (Model Context Protocol) server** that transforms a folder of local documents into a searchable, LLM-backed knowledge base using a **Corrective RAG** pipeline. It combines hybrid retrieval (BM25 + dense vectors → RRF fusion), chunk-level relevance grading, and query rewriting/broadening to produce accurate answers from retrieved context.

```
User / MCP Client
    │
    ▼
┌──────────────────────────┐
│  MCP Server (FastMCP)     │  ← 4 tools: index_folder, ask_question, find_relevant_docs, index_status
│  src/mcp_server/          │
└──────┬───────────────────┘
       │ tool calls
       ▼
┌──────────────────────────┐       ┌──────────────────────────┐
│  LangGraph Pipeline       │       │  Retrieval Layer          │
│  src/graph/              │       │  src/retrieval/           │
│  - builder.py            │       │  - indexer.py             │
│  - nodes.py              │       │  - retriever.py (RRF)     │
│  - edges.py              │       │  - bm25_store.py          │
│  - state.py              │       │  - embedding_fn.py        │
└──────┬───────────────────┘       └──────┬───────────────────┘
       │                                 │
       ▼                                 ▼
┌──────────────────────────┐       ┌──────────────────────────┐
│  LLM Abstraction          │       │  Document Processing      │
│  src/llm/                │       │  src/document_processing/ │
│  - chat_models/          │       │  - factory.py             │
│    - ollama.py           │       │  - base.py                │
│    - openai_compat.py    │       │  - text_splitter.py       │
│  - embed_models/         │       │  - code_splitter.py       │
│    - openai_compat.py    │       │  - markdown_splitter.py   │
└──────────────────────────┘       │  - yaml_splitter.py       │
                                   │  - json_splitter.py       │
                                   └──────────────────────────┘
```

---

## Directory structure

```
mcp-rag-knowlege-base/
├── src/                              # Application source code
│   ├── core/                         # Shared domain layer
│   │   ├── settings.py               # Pydantic BaseSettings — env vars, constants, tuning params
│   │   ├── logging.py                # Logging configuration
│   │   └── __init__.py
│   │
│   ├── mcp_server/                   # MCP protocol layer
│   │   ├── server.py                 # FastMCP server definition & tool registration
│   │   ├── schemas.py                # Request/response Pydantic models
│   │   ├── tool_descriptions.py      # Tool descriptions for MCP clients
│   │   └── tools/                    # Individual tool implementations
│   │       ├── ask_question.py       # Ask question tool — triggers full RAG pipeline
│   │       ├── find_relevant_docs.py # Find relevant docs tool — returns ranked chunks
│   │       ├── index_folder.py       # Index folder tool — parses & indexes documents
│   │       └── index_status.py       # Index status tool — reports indexing progress
│   │
│   ├── graph/                        # LangGraph Corrective RAG pipeline
│   │   ├── state.py                  # RAGState TypedDict — shared pipeline state
│   │   ├── builder.py                # StateGraph construction (START → END flow)
│   │   ├── nodes.py                  # Node functions: rewrite_query, retrieve, grade_chunks, generate_answer, broaden
│   │   └── edges.py                  # Conditional routing: should_broaden
│   │
│   ├── retrieval/                    # Search & indexing layer
│   │   ├── indexer.py                # ChromaDB indexing pipeline — parses, splits, upserts chunks
│   │   ├── retriever.py              # Hybrid retriever — BM25 + vector scores → Reciprocal Rank Fusion (RRF)
│   │   ├── bm25_store.py             # In-memory BM25 inverted index
│   │   ├── embedding_fn.py           # Embedding function wrapper (delegates to llm/embed_models)
│   │   └── __init__.py
│   │
│   ├── document_processing/          # Document parsing & chunking
│   │   ├── factory.py                # Splitter factory — dispatches by file extension (.md, .txt, .py, etc.)
│   │   ├── base.py                   # Abstract base splitter interface
│   │   ├── models.py                 # Chunk data model with position metadata
│   │   ├── text_splitter.py          # Generic text splitter for .md / .txt
│   │   ├── code_splitter.py          # Code-aware splitter for .py / .js / .ts (tree-sitter based)
│   │   ├── markdown_splitter.py      # Markdown-aware splitter preserving headers/headings
│   │   ├── yaml_splitter.py          # YAML file splitter
│   │   ├── json_splitter.py          # JSON file splitter
│   │   └── __init__.py
│   │
│   ├── llm/                          # LLM abstraction layer
│   │   ├── factory.py                # Creates chat or embedding model instances
│   │   ├── chat_models/              # Text generation backends
│   │   │   ├── base.py               # Abstract chat model interface
│   │   │   ├── ollama.py             # Ollama integration (local models)
│   │   │   └── openai_compat.py      # OpenAI-compatible API (any compatible provider)
│   │   └── embed_models/             # Embedding backends
│   │       ├── base.py               # Abstract embedding model interface
│   │       └── openai_compat.py      # OpenAI-compatible embedding API
│   │
│   └── __init__.py
│
├── prompts/                          # LLM prompt templates (loaded at runtime)
│   ├── answer_generation.md          # System prompt for generating final answer
│   ├── fallback_message.md           # Message when no relevant chunks are found
│   ├── mcp_tool_descriptions.md      # Descriptions for MCP client display
│   ├── query_broaden.md              # Prompt for broadening search scope
│   ├── query_rewrite.md              # Prompt for rewriting user queries
│   └── relevance_grade.md            # Prompt for grading chunk relevance
│
├── tests/                            # Test suite
│   ├── conftest.py                   # Pytest fixtures (chroma_dir, sample_docs, sys.path setup)
│   ├── test_graph_rag.py             # LangGraph pipeline integration tests
│   ├── test_indexer.py               # Indexing pipeline tests
│   ├── test_retrieval.py             # Core retrieval logic tests
│   ├── test_retriever.py             # Hybrid retriever (RRF) tests
│   ├── test_tools.py                 # MCP tool handler tests
│   ├── test_server.py                # MCP server layer tests
│   ├── test_markdown_splitter.py     # Markdown splitter tests
│   ├── test_position_metadata.py     # Chunk position metadata tests
│   ├── test_logging.py               # Logging configuration tests
│   ├── fix_nodes.py                  # Node-level debugging tests
│   └── __init__.py
│
├── rag_dataset/                      # Sample datasets for development/testing
│   ├── demo_documents/               # Small sample documents (~10 files, various extensions)
│   ├── download.py                   # Script to download additional demo data
│   └── __pycache__/
│
├── chroma_db/                        # Persisted ChromaDB store (gitignored in production)
│
├── scripts/
│   └── start_server.sh               # Convenience script to launch the MCP server
│
├── .github/workflows/                # GitHub Actions CI (if configured)
│
├── pyproject.toml                    # Project metadata, dependencies, uv config
├── uv.lock                           # Locked dependency manifest (managed by uv)
├── .python-version                   # Python version pin (3.14)
├── Dockerfile                        # Container build definition
├── docker-compose.yaml               # Compose service definitions
├── .env.example                      # Environment variable template
├── .env                              # Local environment overrides (gitignored)
├── AGENTS.md                         # Agent/contributor instructions
├── ARCHITECTURE.md                   # This file
├── TASK.md                           # Task backlog
├── README.md                         # User-facing documentation
├── report.md                         # Project report
├── __main__.py                       # Package entry point (PYTHONPATH=uv run python -m mcp.server)
└── skills-lock.json                  # Skill version lock file
```

---

## Component responsibilities

### `src/core/` — Configuration & shared utilities
- **`settings.py`**: Centralised application configuration via Pydantic `BaseSettings`. All tunable parameters live here: chunk size (500), overlap (50), top_k (10), model name (`RAG_OLLAMA_MODEL`), ChromaDB path, supported file extensions, etc. Supports `Settings.override()` context manager for tests.
- **`logging.py`**: Structured logging setup.

### `src/mcp_server/` — MCP protocol integration
- **`server.py`**: Defines the FastMCP server instance and registers all four tools. Single source of truth for tool registration.
- **`tools/`**: One module per tool. Each implements the MCP tool handler signature (receives params, calls downstream services, returns results).
- **`schemas.py`**: Pydantic models for tool input/output validation.
- **`tool_descriptions.py`**: Human-readable tool descriptions loaded into `prompts/mcp_tool_descriptions.md`.

### `src/graph/` — LangGraph Corrective RAG pipeline
The heart of the system. Orchestrates the query-to-answer flow as a directed graph:

```
START
  │
  ▼
rewrite_query  →  Query is rewritten for better retrieval
  │
  ▼
retrieve       →  Hybrid search: BM25 + vector → RRF fusion
  │
  ▼
grade_chunks   →  LLM grades each chunk's relevance
  │
  ├─ enough relevant? (≥ MIN_RELEVANT_CHUNKS) ──yes──▶ generate_answer → END
  │
  └─ not enough + budget left (≤ MAX_BROADEN_LOOPS) ──▶ broaden → loop back to retrieve
```

- **`state.py`**: `RAGState` TypedDict defining all pipeline state fields.
- **`builder.py`**: Constructs the LangGraph `StateGraph`, wires nodes and edges.
- **`nodes.py`**: Each node function delegates to the appropriate service (retrieval, LLM) and updates state. Loads prompts from `prompts/*.md` at runtime.
- **`edges.py`**: Conditional edge logic — primarily `should_broaden()` which decides whether to retry with a broader query or proceed to answer generation.

### `src/retrieval/` — Search & indexing
- **`indexer.py`**: Reads documents from a directory, dispatches them through the splitter factory, converts text + code chunks into embeddings, and upserts them into ChromaDB. Idempotent — supports re-indexing.
- **`retriever.py`**: Dual-path retriever. Runs BM25 keyword search and dense vector search in parallel, then merges results using Reciprocal Rank Fusion (RRF). Configurable `top_k`.
- **`bm25_store.py`**: In-memory BM25 inverted index implementation (term frequency, document frequency, inverse document frequency, collection statistics).
- **`embedding_fn.py`**: Thin wrapper that delegates to the selected embedding model backend.

### `src/document_processing/` — Parsing & chunking
- **`factory.py`**: Extension-based dispatcher. Given a file extension, returns the appropriate splitter class.
- **`base.py`**: Abstract `BaseSplitter` interface with `split(text, metadata)` method contract.
- **`models.py`**: `Chunk` dataclass carrying text, metadata, and optional position info (start/end offsets).
- **Specialised splitters**:
  - `text_splitter.py`: Character/window-based splitting for plain text and markdown.
  - `code_splitter.py`: AST/tree-sitter aware splitting that respects function/class boundaries for `.py`, `.js`, `.ts`.
  - `markdown_splitter.py`: Splits on headers while preserving heading hierarchy in chunk metadata.
  - `yaml_splitter.py`: Splits YAML documents by top-level keys.
  - `json_splitter.py`: Splits JSON documents by nested objects.

### `src/llm/` — LLM backend abstraction
Decouples the RAG pipeline from any specific LLM provider. Two categories:

- **Chat models** (`chat_models/`): Generate text for answer creation, query rewriting, relevance grading, and query broadening.
  - `ollama.py`: Connects to local Ollama instances. Default backend.
  - `openai_compat.py`: Connects to any OpenAI-compatible API (Together.ai, vLLM, Groq, etc.).
- **Embedding models** (`embed_models/`): Convert text to vectors for semantic search.
  - `openai_compat.py`: Embeddings via OpenAI-compatible API.
- **`factory.py`**: Factory function that creates model instances based on settings (model name, API key, base URL).

### `prompts/` — Prompt engineering
All LLM interaction text lives in `.md` files, loaded dynamically. This enables prompt iteration without code changes:
- **`query_rewrite.md`**: Rewrites user questions into retrieval-friendly form.
- **`relevance_grade.md`**: Evaluates each chunk against the query on a structured scale.
- **`answer_generation.md`**: Synthesises relevant chunks into a coherent answer with citations.
- **`query_broaden.md`**: Expands queries when too few relevant chunks are found.
- **`fallback_message.md`**: Graceful message when no content matches.
- **`mcp_tool_descriptions.md`**: Tool descriptions shown in MCP clients.

---

## Data flow — indexing

```
Directory with documents
        │
        ▼
┌──────────────────┐
│  indexer.py       │  Scan directory, filter by supported extensions
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  factory.py       │  Dispatch: .md → MarkdownSplitter, .py → CodeSplitter, etc.
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  Splitters        │  Parse & split into chunks with metadata
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  embedding_fn.py  │  Convert chunk text → vector
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  ChromaDB         │  Upsert (id, text, vector, metadata)
└──────────────────┘
```

## Data flow — querying (Corrective RAG)

```
User question via MCP tool
        │
        ▼
┌──────────────────┐
│  LangGraph Graph  │  builder.py constructs the pipeline
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  rewrite_query    │  Prompt: prompts/query_rewrite.md
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  retrieve         │  BM25 (bm25_store.py) + Vector (ChromaDB) → RRF merge
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│  grade_chunks     │  Prompt: prompts/relevance_grade.md — LLM rates each chunk
└──────┬───────────┘
       │
       ├── ≥ MIN_RELEVANT_CHUNKS ──▶ generate_answer → return to user
       │
       └── < MIN_RELEVANT_CHUNKS & loops < MAX_BROADEN_LOOPS
                  │
                  ▼
           ┌──────────────┐
           │  broaden      │  Prompt: prompts/query_broaden.md → wider query
           └──────┬───────┘
                  │
                  └──────────▶ loop back to retrieve
```

---

## External dependencies

| Layer | Dependency | Purpose |
|-------|-----------|---------|
| Graph | LangGraph | Stateful DAG orchestration for RAG pipeline |
| Storage | ChromaDB | Persistent vector store for embeddings |
| Retrieval | rank-bm25 | BM25 keyword scoring |
| Code | tree-sitter | AST-based code splitting |
| LLM | ollama / openai | Chat completions + embeddings |
| Protocol | mcp (Python SDK) | Model Context Protocol server/client |
| Config | pydantic-settings | Type-safe environment variable loading |
| Testing | pytest | Test framework |

Managed via `uv` — see `pyproject.toml` and `uv.lock` for exact versions.
