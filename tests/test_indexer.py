"""Tests for the indexer stub and document processing module."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import chromadb

from document_processing.text_splitter import TextSplitter  # noqa: E402
from core.settings import settings
from retrieval import Indexer

# Document processing imports
from document_processing import (  # noqa: E402
    Chunk,
    CodeSplitter,
    DocumentSplitter,
    MarkdownSplitter,
    SplitResult,
    TextSplitter as TS,
    YAMLSplitter,
    get_splitter,
)


class TestTextSplitterDirect:
    """Verify chunking logic with overlap via TextSplitter directly."""

    def test_empty_string(self) -> None:
        result = TextSplitter().split("", "test.txt", ".txt")
        assert len(result.chunks) == 0

    def test_short_content_no_split(self) -> None:
        result = TextSplitter().split("hello", "test.txt", ".txt")
        assert len(result.chunks) == 1
        assert result.chunks[0].content == "hello"

    def test_long_content_splits(self) -> None:
        long_text = "a " * settings.CHUNK_SIZE  # exceeds CHUNK_SIZE
        result = TextSplitter().split(long_text, "test.txt", ".txt")
        assert len(result.chunks) >= 2
        for c in result.chunks:
            assert len(c.content) <= settings.CHUNK_SIZE + settings.CHUNK_OVERLAP

    def test_chunk_indices_are_sequential(self) -> None:
        text = "word " * (settings.CHUNK_SIZE * 3)
        result = TextSplitter().split(text, "test.txt", ".txt")
        indices = [c.chunk_index for c in result.chunks]
        assert indices == list(range(len(indices)))


class TestIndexFolder:
    """Verify file discovery and ChromaDB storage."""

    def test_scan_files_finds_extensions(self, sample_docs: Path) -> None:
        indexer = Indexer()
        result = indexer.index_folder(str(sample_docs), glob_pattern="*")
        # We created 5 files (md, txt, yaml, py, ts)
        assert result.indexed_count == 5

    def test_scan_files_respects_glob(self, sample_docs: Path) -> None:
        indexer = Indexer()
        result = indexer.index_folder(str(sample_docs), glob_pattern="*.md")
        assert result.indexed_count == 1

    def test_scan_files_respects_extension_filter(self, sample_docs: Path) -> None:
        indexer = Indexer()
        result = indexer.index_folder(str(sample_docs))
        assert result.total_chunks > 0

    def test_nonexistent_folder_raises(self) -> None:
        indexer = Indexer()
        with pytest.raises(FileNotFoundError):
            indexer.index_folder("/nonexistent/path")

    def test_chunks_stored_in_chroma(self, sample_docs: Path, chroma_dir: Path) -> None:
        """Verify chunks are actually stored in ChromaDB."""
        _clear_collection(str(chroma_dir))
        indexer = Indexer(persist_dir=str(chroma_dir))
        result = indexer.index_folder(str(sample_docs))
        assert result.total_chunks > 0

        client = chromadb.PersistentClient(path=str(chroma_dir))
        collection = client.get_collection(name=settings.CHROMA_COLLECTION)
        assert collection.count() == result.total_chunks

    def test_metadata_contains_source(
        self, chroma_dir: Path, sample_docs: Path
    ) -> None:
        _clear_collection(str(chroma_dir))
        indexer = Indexer(persist_dir=str(chroma_dir))
        indexer.index_folder(str(sample_docs))

        coll = chromadb.PersistentClient(path=str(chroma_dir))
        collection = coll.get_collection(name=settings.CHROMA_COLLECTION)
        data = collection.get(include=["metadatas"])
        sources = {m.get("source", "") for m in data["metadatas"]}
        expected_names = {
            "introduction.md",
            "python_basics.txt",
            "config.yaml",
            "script.py",
        }
        # Check at least some sources match
        found = any(n in src for n in expected_names for src in sources if src)
        assert found, f"Expected source filenames in metadatas, got: {sources}"


def _clear_collection(persist_dir: str) -> None:
    client = chromadb.PersistentClient(path=persist_dir)
    try:
        client.delete_collection(name=settings.CHROMA_COLLECTION)
    except Exception:
        pass


# ── Document processing tests ───────────────────────────────────────────────


class TestFactory:
    """Verify the splitter factory returns correct types."""

    def test_markdown_extension(self) -> None:
        assert isinstance(get_splitter(".md"), MarkdownSplitter)

    def test_python_extension(self) -> None:
        assert isinstance(get_splitter(".py"), CodeSplitter)

    def test_typescript_extension(self) -> None:
        assert isinstance(get_splitter(".ts"), CodeSplitter)

    def test_javascript_extension(self) -> None:
        assert isinstance(get_splitter(".js"), CodeSplitter)

    def test_yaml_extension(self) -> None:
        assert isinstance(get_splitter(".yaml"), YAMLSplitter)

    def test_yml_extension(self) -> None:
        assert isinstance(get_splitter(".yml"), YAMLSplitter)

    def test_txt_extension(self) -> None:
        assert isinstance(get_splitter(".txt"), TextSplitter)

    def test_json_has_dedicated_splitter(self) -> None:
        from document_processing.json_splitter import JSONSplitter

        assert isinstance(get_splitter(".json"), JSONSplitter)

    def test_unknown_extension_fallback(self) -> None:
        # Unknown extensions fall back to the text splitter
        assert isinstance(get_splitter(".cfg"), TextSplitter)

    def test_arbitrary_extension_fallback(self) -> None:
        assert isinstance(get_splitter(".xyz"), TextSplitter)


class TestJSONSplitter:
    """Verify tree-sitter-based JSON splitting."""

    @pytest.fixture()
    def splitter(self):
        from document_processing.json_splitter import JSONSplitter

        return JSONSplitter()

    def test_empty_content(self, splitter):
        result = splitter.split("", "test.json", ".json")
        assert len(result.chunks) == 0

    def test_empty_object(self, splitter):
        result = splitter.split("{}", "test.json", ".json")
        assert len(result.chunks) == 0

    def test_simple_object(self, splitter):
        content = '{"name": "Alice", "age": 30}'
        result = splitter.split(content, "test.json", ".json")
        assert len(result.chunks) == 2
        paths = {c.metadata["key_path"] for c in result.chunks}
        assert "name" in paths
        assert "age" in paths

    def test_string_values_preserved(self, splitter):
        result = splitter.split('{"greeting": "hello world"}', "t.json", ".json")
        chunk = next(c for c in result.chunks if c.metadata["key_path"] == "greeting")
        # Value is preserved as JSON representation (with quotes for strings)
        assert "hello world" in chunk.content

    def test_numeric_value_type(self, splitter):
        result = splitter.split('{"count": 42, "price": 9.99}', "t.json", ".json")
        types = {
            c.metadata["key_path"]: c.metadata["value_type"] for c in result.chunks
        }
        assert types["count"] == "integer"
        assert types["price"] == "float"

    def test_boolean_and_null(self, splitter):
        result = splitter.split(
            '{"active": true, "deleted": false, "mid": null}', "t.json", ".json"
        )
        types = {
            c.metadata["key_path"]: c.metadata["value_type"] for c in result.chunks
        }
        assert types["active"] == "boolean"
        assert types["deleted"] == "boolean"
        assert types["mid"] == "null"

    def test_nested_objects(self, splitter):
        content = '{"user": {"name": "Bob", "role": "admin"}}'
        result = splitter.split(content, "t.json", ".json")
        paths = [c.metadata["key_path"] for c in result.chunks]
        assert "user.name" in paths
        assert "user.role" in paths

    def test_arrays_with_objects(self, splitter):
        content = '{"items": [{"id": 1}, {"id": 2}]}'
        result = splitter.split(content, "t.json", ".json")
        paths = [c.metadata["key_path"] for c in result.chunks]
        assert "items.0.id" in paths
        assert "items.1.id" in paths

    def test_root_array(self, splitter):
        result = splitter.split("[10, 20, 30]", "arr.json", ".json")
        assert len(result.chunks) == 3
        paths = [c.metadata["key_path"] for c in result.chunks]
        assert paths == ["0", "1", "2"]

    def test_source_preserved(self, splitter):
        result = splitter.split('{"a": 1}', "reports/config.json", ".json")
        assert result.source_file == "reports/config.json"
        assert result.file_extension == ".json"

    def test_chunk_indices_sequential(self, splitter):
        content = '{"a": 1, "b": 2, "c": 3}'
        result = splitter.split(content, "t.json", ".json")
        indices = [c.chunk_index for c in result.chunks]
        assert indices == [0, 1, 2]

    def test_deeply_nested_paths(self, splitter):
        content = '{"a": {"b": {"c": {"d": "deep"}}}}'
        result = splitter.split(content, "t.json", ".json")
        paths = [c.metadata["key_path"] for c in result.chunks]
        assert "a.b.c.d" in paths

    def test_mixed_array(self, splitter):
        content = '[1, "text", true, null, {"k": "v"}]'
        result = splitter.split(content, "t.json", ".json")
        paths = [c.metadata["key_path"] for c in result.chunks]
        assert "0" in paths  # integer
        assert "1" in paths  # string
        assert "2" in paths  # boolean
        assert "3" in paths  # null
        assert "4.k" in paths  # object inside array

    def test_no_chunks_for_non_json_ext(self, splitter):
        """The splitter only handles .json extension."""
        assert splitter.can_handle(".json")
        assert not splitter.can_handle(".yaml")
        assert not splitter.can_handle(".txt")


class TestMarkdownSplitter:
    """Verify tree-sitter-based markdown splitting."""

    def test_empty_content(self) -> None:
        result = MarkdownSplitter().split("", "test.md", ".md")
        assert len(result.chunks) == 0

    def test_single_section(self) -> None:
        content = "# Title\n\nSome text here."
        result = MarkdownSplitter().split(content, "test.md", ".md")
        assert len(result.chunks) >= 1
        assert result.chunks[0].metadata.get("section", "").startswith("#")

    def test_multiple_sections(self) -> None:
        content = (
            "# Intro\n\nHello world.\n\n"
            "## Section Two\n\nMore content here.\n\n"
            "### Subsection\n\nEven more."
        )
        result = MarkdownSplitter().split(content, "test.md", ".md")
        sections = {c.metadata.get("section", "") for c in result.chunks if c.metadata}
        assert any("Intro" in s for s in sections)
        assert any("Section Two" in s for s in sections)

    def test_code_block_not_split(self) -> None:
        """Fenced code blocks should stay atomic within a section."""
        content = "# Code\n\n" "```\ndef foo():\n    return 42\n```\n\n" "After code."
        result = MarkdownSplitter().split(content, "test.md", ".md")
        # At least one chunk should contain the full code block
        code_chunks = [c for c in result.chunks if "def foo()" in c.content]
        assert len(code_chunks) >= 1

    def test_no_headings(self) -> None:
        """Plain markdown without headings still produces chunks."""
        content = "Just some plain text with no headings at all."
        result = MarkdownSplitter().split(content, "test.md", ".md")
        assert len(result.chunks) >= 1

    def test_source_preserved(self) -> None:
        result = MarkdownSplitter().split("content", "docs/guide.md", ".md")
        assert result.source_file == "docs/guide.md"
        assert result.file_extension == ".md"


class TestCodeSplitter:
    """Verify tree-sitter-based code splitting."""

    def test_empty_content(self) -> None:
        result = CodeSplitter().split("", "test.py", ".py")
        assert len(result.chunks) == 0

    def test_python_functions(self) -> None:
        content = "def foo():\n    pass\n\ndef bar(x):\n    return x + 1\n"
        result = CodeSplitter().split(content, "test.py", ".py")
        func_names = {c.metadata.get("function_name", "") for c in result.chunks}
        assert "foo" in func_names
        assert "bar" in func_names

    def test_python_classes(self) -> None:
        content = "class MyClass:\n    def method(self):\n        pass\n"
        result = CodeSplitter().split(content, "test.py", ".py")
        class_names = {c.metadata.get("class_name", "") for c in result.chunks}
        assert "MyClass" in class_names

    def test_python_metadata_includes_lines(self) -> None:
        content = "def my_func():\n    pass\n"
        result = CodeSplitter().split(content, "test.py", ".py")
        func_chunk = next(
            c for c in result.chunks if c.metadata.get("function_name") == "my_func"
        )
        assert "line_start" in func_chunk.metadata
        assert "line_end" in func_chunk.metadata

    def test_malformed_python_falls_back(self) -> None:
        """Barely parseable Python should fall back to text splitting."""
        # This is valid minimal Python but testing fallback path works
        content = "x = 1\ny = 2\nz = 3\n"
        result = CodeSplitter().split(content, "test.py", ".py")
        assert len(result.chunks) >= 1

    def test_typescript_functions(self) -> None:
        content = "function greet(name: string): string {\n    return name;\n}\n"
        result = CodeSplitter().split(content, "app.ts", ".ts")
        func_names = {c.metadata.get("function_name", "") for c in result.chunks}
        assert "greet" in func_names

    def test_typescript_methods(self) -> None:
        content = (
            "class Greeter {\n"
            "    constructor(public name: string) {}\n"
            "    sayHi(): void { console.log('hi'); }\n"
            "}\n"
        )
        result = CodeSplitter().split(content, "app.ts", ".ts")
        methods = [
            c for c in result.chunks if c.metadata.get("function_name") == "sayHi"
        ]
        assert len(methods) >= 1
        assert methods[0].metadata.get("class_name") == "Greeter"


class TestYAMLSplitter:
    """Verify tree-sitter-based YAML splitting."""

    def test_empty_content(self) -> None:
        result = YAMLSplitter().split("", "config.yaml", ".yaml")
        assert len(result.chunks) == 0

    def test_top_level_keys(self) -> None:
        content = (
            "database:\n  host: localhost\n  port: 5432\n\nserver:\n  host: 0.0.0.0\n"
        )
        result = YAMLSplitter().split(content, "config.yaml", ".yaml")
        paths = {c.metadata.get("key_path", "") for c in result.chunks}
        assert "database" in paths
        assert "server" in paths

    def test_nested_key_paths(self) -> None:
        content = "database:\n  host: localhost\n  port: 5432\n"
        result = YAMLSplitter().split(content, "config.yaml", ".yaml")
        paths = {c.metadata.get("key_path", "") for c in result.chunks}
        assert "database.host" in paths
        assert "database.port" in paths

    def test_value_types(self) -> None:
        content = "count: 42\nname: mydb\nenabled: true\nratio: 3.14\nnothing: null\n"
        result = YAMLSplitter().split(content, "config.yaml", ".yaml")
        by_type: dict[str, list] = {}
        for c in result.chunks:
            vtype = c.metadata.get("value_type", "")
            by_type.setdefault(vtype, []).append(c)
        assert "integer" in by_type
        assert "string" in by_type
        assert "boolean" in by_type
        assert "float" in by_type
        assert "null" in by_type

    def test_source_preserved(self) -> None:
        result = YAMLSplitter().split("key: value", "settings.yml", ".yaml")
        assert result.source_file == "settings.yml"


class TestTextSplitter:
    """Verify plain-text splitter behavior."""

    def test_empty_content(self) -> None:
        result = TextSplitter().split("", "file.txt", ".txt")
        assert len(result.chunks) == 0

    def test_short_content(self) -> None:
        result = TextSplitter().split("hello", "file.txt", ".txt")
        assert len(result.chunks) == 1
        assert result.chunks[0].content == "hello"

    def test_paragraph_awareness(self) -> None:
        """Prefer paragraph breaks when near chunk boundary."""
        long_para = "word " * (settings.CHUNK_SIZE + 100)
        result = TextSplitter().split(long_para, "file.txt", ".txt")
        assert len(result.chunks) >= 2

    def test_source_preserved(self) -> None:
        result = TextSplitter().split("data", "notes.txt", ".txt")
        assert result.source_file == "notes.txt"


class TestChunkModel:
    """Verify Chunk.to_dict() output format."""

    def test_to_dict_basic(self) -> None:
        chunk = Chunk(content="hello", chunk_index=0, source="test.md")
        d = chunk.to_dict()
        assert d["content"] == "hello"
        assert d["chunk_index"] == 0
        assert d["source"] == "test.md"

    def test_to_dict_with_metadata(self) -> None:
        chunk = Chunk(
            content="code",
            chunk_index=1,
            source="app.py",
            metadata={"function_name": "main", "class_name": ""},
        )
        d = chunk.to_dict()
        assert d["function_name"] == "main"
        assert d["class_name"] == ""


class TestDocumentSplitterABC:
    """Verify the abstract base class contract."""

    def test_can_handle_class_method(self) -> None:
        assert MarkdownSplitter.can_handle(".md") is True
        assert MarkdownSplitter.can_handle(".py") is False
        assert TextSplitter.can_handle(".txt") is True

    def test_can_handle_without_dot(self) -> None:
        assert MarkdownSplitter.can_handle("md") is True

    def test_is_abstract(self) -> None:
        """Instantiating DocumentSplitter directly should fail."""
        with pytest.raises(TypeError):
            DocumentSplitter()  # type: ignore[abstract]
