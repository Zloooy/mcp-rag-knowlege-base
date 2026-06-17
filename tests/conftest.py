"""Shared test fixtures: temp ChromaDB dirs, sample documents, helpers."""

from __future__ import annotations

import sys
from collections.abc import Generator
from pathlib import Path

# Ensure src/ is on the path so local packages can be imported.
_project_root = Path(__file__).resolve().parent.parent
_src_dir = str(_project_root / "src")
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

import chromadb  # noqa: E402
import pytest  # noqa: E402

from core.settings import settings  # noqa: E402

# ---------------------------------------------------------------------------
# Temp directories for ChromaDB (tests don't interfere with each other)
# ---------------------------------------------------------------------------


@pytest.fixture()
def chroma_dir(tmp_path: Path) -> Path:
    """Return a temp directory path to use as ChromaDB persist location."""
    d = tmp_path / "chroma_test"
    d.mkdir(parents=True, exist_ok=True)
    return d


@pytest.fixture()
def sample_docs(tmp_path: Path) -> Path:
    """Create small test document files and return the parent dir.

    Files created::

        docs/
          introduction.md
          python_basics.txt
          config.yaml
          script.py
    """
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    (docs_dir / "introduction.md").write_text(
        "# Introduction\n\nThis is a guide about Python programming.\n"
        "Python is a versatile language used in web development, data science,\n"
        "and automation. It supports multiple paradigms including procedural,\n"
        "object-oriented, and functional programming styles.\n\n"
        "## Getting Started\n\nInstall Python from python.org and start coding.",
        encoding="utf-8",
    )

    (docs_dir / "python_basics.txt").write_text(
        "Python basics tutorial:\n"
        "Variables are dynamically typed. Strings can use single or double quotes.\n"
        "Lists store ordered collections. Dictionaries map keys to values.\n"
        "Functions are defined with the def keyword. Classes define objects.\n"
        "Modules help organize code into reusable packages.",
        encoding="utf-8",
    )

    (docs_dir / "config.yaml").write_text(
        "database:\n  host: localhost\n  port: 5432\n  name: mydb\n\n"
        "server:\n  host: 0.0.0.0\n  port: 8000\n",
        encoding="utf-8",
    )

    (docs_dir / "script.py").write_text(
        "#!/usr/bin/env python3\n"
        "'\"'\"'Quick utility script.'\"'\"'\n\n"
        "def main():\n"
        "    print('Hello world')\n\n"
        "if __name__ == '__main__':\n"
        "    main()\n",
        encoding="utf-8",
    )

    (docs_dir / "app.ts").write_text(
        "// Simple TypeScript example for testing CodeSplitter.\n\n"
        "interface Config {\n"
        "    host: string;\n"
        "    port: number;\n"
        "}\n\n"
        "function createConfig(host: string, port: number): Config {\n"
        "    return { host, port };\n"
        "}\n\n"
        "class Server {\n"
        "    private config: Config;\n\n"
        "    constructor(config: Config) {\n"
        "        this.config = config;\n"
        "    }\n\n"
        "    start(): void {\n"
        "        console.log(`Listening on ${this.config.host}:${this.config.port}`);\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    return docs_dir


# ---------------------------------------------------------------------------
# Helper to populate / clear the index
# ---------------------------------------------------------------------------


def _clear_collection(persist_dir: str) -> None:
    """Drop the collection so tests start clean."""
    client = chromadb.PersistentClient(path=persist_dir)
    try:
        client.delete_collection(name=settings.CHROMA_COLLECTION)
    except Exception:  # pragma: no cover — collection may not exist yet
        pass


@pytest.fixture()
def populated_index(sample_docs: Path, chroma_dir: Path) -> Generator[Path, None, None]:
    """Index *sample_docs* into ChromaDB backed by *chroma_dir* and yield it."""
    _clear_collection(str(chroma_dir))
    from retrieval import Indexer

    indexer = Indexer(persist_dir=str(chroma_dir))
    result = indexer.index_folder(folder_path=str(sample_docs))
    assert result.indexed_count > 0
    assert result.total_chunks > 0
    yield sample_docs


@pytest.fixture()
def empty_index(chroma_dir: Path) -> Path:
    """Return a ChromaDB directory with no indexed chunks."""
    _clear_collection(str(chroma_dir))
    return chroma_dir
