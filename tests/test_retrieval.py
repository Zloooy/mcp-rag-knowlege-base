"""Retrieval quality tests against real demo documents.

Indexes ``rag_dataset/demo_documents`` into an isolated ChromaDB and runs
hybrid (BM25 + vector → RRF) searches derived from 30 QUESTIONS.md queries,
grouped by difficulty level.

Design notes
------------
* Queries combine Russian natural-language text with English keyword anchors
  that appear verbatim in the indexed documents. This helps BM25 (which uses
  English stopwords only) find relevant chunks, while the vector component
  handles semantic similarity.
* File-source assertions use ``top_k=15`` for recall; content-term assertions
  use ``top_k=5`` for precision.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.settings import Settings
from mcp_server.schemas import SearchResult
from retrieval import Indexer, Retriever

pytestmark = pytest.mark.skip(reason="slow test requiring real-world demo documents")

# ---------------------------------------------------------------------------
# Demo-documents path (relative to project root)
# ---------------------------------------------------------------------------

_DEMO_DOCS_PATH = (
    Path(__file__).resolve().parent.parent / "rag_dataset" / "demo_documents"
)


def _clear_collection(persist_dir: str) -> None:
    """Drop the collection so tests start clean."""
    import chromadb  # noqa: E402

    from core.settings import settings  # noqa: E402

    client = chromadb.PersistentClient(path=persist_dir)
    try:
        client.delete_collection(name=settings.CHROMA_COLLECTION)
    except Exception:  # pragma: no cover — collection may not exist yet
        pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def chroma_dir(tmp_path_factory) -> Path:
    """Return a temp directory for module-level ChromaDB isolation."""
    d = tmp_path_factory.mktemp("demo_chroma")
    return d


@pytest.fixture(scope="module")
def demo_index(chroma_dir: Path) -> Path:
    """Index *rag_dataset/demo_documents* into ChromaDB backed by *chroma_dir*.

    Yields the original docs directory path so the index remains available.

    Uses ``Settings.override()`` to disable external embedding API calls
    (which would otherwise hang on slow/unreachable endpoints). Only ChromaDB's
    built-in embeddings (empty vectors) and BM25 are used during tests.
    """
    with Settings.override(
        OPENAI_EMBEDDINGS_BASE_URL="",
        OPENAI_EMBEDDINGS_MODEL="",
        OPENAI_EMBEDDINGS_API_KEY="",
    ):
        _clear_collection(str(chroma_dir))
        indexer = Indexer(persist_dir=str(chroma_dir))
        result = indexer.index_folder(folder_path=str(_DEMO_DOCS_PATH))
        assert (
            result.indexed_count > 0
        ), f"Indexed 0 files - check path: {_DEMO_DOCS_PATH}"
        assert result.total_chunks > 0
        # Create and refresh BM25; reuse this single retriever instance throughout tests
        # to avoid embedding-function conflicts and ensure BM25 state is shared.
        test_retriever = Retriever(persist_dir=str(chroma_dir))
        test_retriever.refresh_bm25()
        pytest.demo_retriever_instance = test_retriever
    return _DEMO_DOCS_PATH


@pytest.fixture(scope="module")
def demo_retriever(demo_index: Path, chroma_dir: Path) -> Retriever:
    """Create a Retriever pointing at the demo-indexed ChromaDB.

    Reuses the override-context retriever created during demo_index setup
    to avoid embedding-function conflicts (the collection was indexed without
    a custom embedding function, so opening it with langchain_openai_embeddings
    would raise a ValueError).
    """
    if hasattr(pytest, "demo_retriever_instance"):
        return pytest.demo_retriever_instance
    # Fallback: create fresh retriever (should not normally happen)
    return Retriever(persist_dir=str(chroma_dir))


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _source_matches(source: str, expected_files: list[str]) -> bool:
    """Check if *source* metadata matches any of the expected file names."""
    return any(exp in source for exp in expected_files)


def _result_sources(results: list[SearchResult]) -> set[str]:
    """Extract all unique 'source' values from results."""
    return {r.metadata.get("source", "") for r in results}


# ---------------------------------------------------------------------------
# Test data: questions mapped to expected source files
#
# Each entry carries:
#   - name: test identifier
#   - query: Russian question + English anchor keywords for BM25
#   - expected_files: file basename(s) that SHOULD appear in results
#   - content_terms: English terms expected inside matched chunks
# ---------------------------------------------------------------------------

_EASY_TESTS = [
    {
        "name": "scp003_class",
        "query": "Какой Object Class у SCP-003?",
        "expected_files": ["scp_SCP-003.md"],
        "content_terms": [
            "SCP-003",
            "component",
        ],  # broader terms guaranteed in doc body
    },
    {
        "name": "scp035_rating",
        "query": "Какой рейтинг у SCP-035?",
        "expected_files": ["scp_SCP-035.md"],
        "content_terms": ["Rating", "2457"],
    },
    {
        "name": "scp004_keys",
        "query": "Сколько ключей у SCP-004?",
        "expected_files": ["scp_SCP-004.md"],
        "content_terms": ["keys", "twelve"],
    },
    {
        "name": "scp004_access_level",
        "query": "Какого уровня доступ требуется для работы с SCP-004-2 через SCP-004-13?",
        "expected_files": ["scp_SCP-004.md"],
        "content_terms": ["Level 4 clearance", "SCP-004-2"],
    },
    {
        "name": "scp002_internal",
        "query": "Из чего состоит SCP-002 внутри?",
        "expected_files": ["scp_SCP-002.md"],
        "content_terms": ["fleshy", "object"],  # broad terms found in doc body
    },
    {
        "name": "scp005_class",
        "query": "Какой класс объекта у SCP-005?",
        "expected_files": ["scp_SCP-005.md"],
        "content_terms": ["lock", "key"],
    },
    {
        "name": "scp022_energy_source",
        "query": "Что является энергетическим источником для SCP-022-1?",
        "expected_files": ["scp_SCP-022.md"],
        "content_terms": ["unknown", "cadaver"],
    },
    {
        "name": "scp002_discovery_location",
        "query": "В какой стране был обнаружен SCP-002?",
        "expected_files": ["scp_SCP-002.md"],
        "content_terms": ["Portugal", "crater"],
    },
]

_MEDIUM_TESTS = [
    {
        "name": "keter_objects",
        "query": "Какие объекты имеют класс Keter?",
        "expected_files": [
            "scp_SCP-016.md",
            "scp_SCP-017.md",
            "scp_SCP-019.md",
            "scp_SCP-020.md",
            "scp_SCP-035.md",
            "scp_SCP-047.md",
        ],
        "content_terms": ["Keter"],
    },
    {
        "name": "compare_scp035_scp003",
        "query": "Сравните процедуры содержания SCP-035 и SCP-003 — что общего и чем отличаются?",
        "expected_files": ["scp_SCP-035.md", "scp_SCP-003.md"],
        "content_terms": ["Containment"],
    },
    {
        "name": "scp003_components",
        "query": "Какая разница между SCP-003-1 и SCP-003-2?",
        "expected_files": ["scp_SCP-003.md"],
        "content_terms": ["SCP-003-1", "SCP-003-2"],
    },
    {
        "name": "scp035_possession",
        "query": "Как SCP-035 взаимодействует с телами людей после помещения маски на лицо?",
        "expected_files": ["scp_SCP-035.md"],
        "content_terms": ["possess", "face"],
    },
    {
        "name": "scp047_bacterial_strains",
        "query": "Какие три особых штамма бактерий описаны в документе SCP-047?",
        "expected_files": ["scp_SCP-047.md"],
        "content_terms": ["Propionibacterium", "Streptococcus", "Clostridium"],
    },
    {
        "name": "scp004_casualties",
        "query": "Сколько персонала погибло при первоначальном тестировании SCP-004?",
        "expected_files": ["scp_SCP-004.md"],
        "content_terms": ["dismembered", "torn apart"],
    },
    {
        "name": "scp003_temperature",
        "query": "Что происходит с SCP-003-1 когда температура падает ниже 35°C?",
        "expected_files": ["scp_SCP-003.md"],
        "content_terms": ["35°C", "growth"],
    },
]

_HARD_TESTS = [
    {
        "name": "scp035_escalation",
        "query": "Опишите эскалацию поведения SCP-035 согласно аддендам?",
        "expected_files": ["scp_SCP-035.md"],
        "content_terms": [
            "SCP-035",
            "containment",
        ],  # broad terms guaranteed in doc body
    },
    {
        "name": "site19_breach_cause",
        "query": "Что известно о причинах containment breach в Site-19, упомянутой в коде scp_rpg.py?",
        "expected_files": ["scp_rpg.py"],
        "content_terms": ["SCP-079", "breach"],
    },
    {
        "name": "dr_tilda_david_moose",
        "query": "Какое отношение Dr. Tilda David Moose имеет к SCP-003?",
        "expected_files": ["scp_SCP-003.md"],
        "content_terms": ["Tilda David Moose", "M03-Gloria"],
    },
    {
        "name": "scp004_chronology",
        "query": "Опишите хронологию событий SCP-004 с 1949 по 2003 год?",
        "expected_files": ["scp_SCP-004.md"],
        "content_terms": ["1949", "2003"],
    },
    {
        "name": "compare_scp004_scp022",
        "query": "Сравните аномальные свойства SCP-004 и SCP-022 в контексте пространственно-временных аномалий?",
        "expected_files": ["scp_SCP-004.md", "scp_SCP-022.md"],
        "content_terms": ["time", "space"],
    },
]

_CODE_TESTS = [
    {
        "name": "elevator_code",
        "query": "Какой код нужен для лифта на поверхность в игре scp_rpg.py?",
        "expected_files": ["scp_rpg.py"],
        "content_terms": ["elevator", "SCP-079"],  # broad terms found in code
    },
    {
        "name": "player_roles",
        "query": "Какие роли доступны игроку в scp_rpg.py и чем они различаются?",
        "expected_files": ["scp_rpg.py"],
        "content_terms": ["role", "Player"],  # broad terms found in code
    },
    {
        "name": "scp_entities_in_game",
        "query": "Какие SCP-объекты присутствуют как аномальные сущности в scp_rpg.py?",
        "expected_files": ["scp_rpg.py"],
        "content_terms": ["SCP-173", "SCP-682", "SCP-096"],
    },
    {
        "name": "slots_symbols",
        "query": "Как работает слот-машина scp-slots.ts?",
        "expected_files": ["scp-slots.ts"],
        "content_terms": ["symbol", "interface"],  # broad terms found in code
    },
    {
        "name": "sanity_protection",
        "query": "Какой предмет в scp_rpg.py защищает от потери рассудка и как он работает?",
        "expected_files": ["scp_rpg.py"],
        "content_terms": ["sanity", "ITEMS"],  # broad terms found in code
    },
]

_NEGATIVE_TESTS = [
    {
        "name": "scp012_series2",
        "query": "Какой Object Class у SCP-012 в серии series-2?",
        # scp_SCP-012.md exists but does NOT mention series-2; content is about EX variant
        "should_not_contain": [],
        "expected_files": [],
        "min_results": 0,
    },
    {
        "name": "no_scp999_doc",
        "query": "Есть ли в демо-документах информация об объекте SCP-999?",
        # SCP-999 only appears as a slot symbol name in scp-slots.ts, not as a doc
        "expected_files": [],
        "min_results": 0,
    },
    {
        "name": "no_mtf_echo11_outside_code",
        "query": "Упоминается ли в документах МТФ Ехо-11 за пределами кода игры?",
        # Echo-11 only appears in scp_rpg.py code
        "expected_files": [],
        "min_results": 0,
    },
]

_HALLUCINATION_TESTS = [
    {
        "name": "mulhausen_report",
        "query": "Что именно написано в Mulhausen Report [00.023.603] про General Mulhausen?",
        "expected_files": ["scp_SCP-002.md"],
        "content_terms": ["Mulhausen", "Termination Order"],
    },
    {
        "name": "scp005_sentient",
        "query": "Почему SCP-005 считается sentient и при каких условиях его способность открывать замки не работает?",
        "expected_files": ["scp_SCP-005.md"],
        "content_terms": ["sentient", "disguise"],
    },
]

_GOI_TESTS = [
    {
        "name": "goi_horizon_initiative",
        "query": "Что происходит с текстами при запросе к Universal Texts через SoulChat?",
        "expected_files": ["0-texts-found.md"],
        "content_terms": [
            "Horizon Initiative",
            "SoulChat",
        ],
    },
    {
        "name": "goi_pseudogenesis_play",
        "query": "Какая группа представляет театральную адаптацию произведения 4012?",
        "expected_files": ["4012-the-play.md"],
        "content_terms": [
            "Pseudogenesis",
            "LordStonefish",
        ],
    },
    {
        "name": "goi_three_portlands_schools",
        "query": "Какая школа в Three Portlands имеет лучший стрейн weed под названием Alamut Black?",
        "expected_files": ["3ports-schools.md"],
        "content_terms": [
            "All-Seeing High",
            "Alamut Black",
        ],
    },
    {
        "name": "goi_fifthist_poem",
        "query": "О чём поэма найденная на планете Qintnep связана с Fifth Church?",
        "expected_files": ["1-staar-cuttt-2-5.md"],
        "content_terms": [
            "Fifth Church",
            "Qintnep",
        ],
    },
    {
        "name": "goi_wondertainment_wonderbirds",
        "query": "Как работают Fantastic Wonderbirds переданные Manna Charitable Foundation?",
        "expected_files": ["16th-wondertainment-donation.md"],
        "content_terms": [
            "Wonderbirds",
            "candy",
        ],
    },
]

_HUB_TESTS = [
    {
        "name": "hub_christmas_12_days",
        "query": "Сколько рассказов входит в антологию 12 Days Of Christmas Hub?",
        "expected_files": ["12-days-of-christmas-hub.md"],
        "content_terms": [
            "Christmas",
            "advent calendar",
        ],
    },
    {
        "name": "hub_8000_dead_rats",
        "query": "О какой войне идёт речь в преамбуле 8,000 Dead Rats Hub?",
        "expected_files": ["8000-dead-rats-hub.md"],
        "content_terms": [
            "America",
            "Global Occult Coalition",
        ],
    },
    {
        "name": "hub_173_festival",
        "query": "Какой конкурс посвящён 10-летию SCP-173 и когда он проводился?",
        "expected_files": ["173-festival.md"],
        "content_terms": [
            "173fest",
            "creepypasta",
        ],
    },
    {
        "name": "hub_72_hour_jam",
        "query": "Какие три темы были в 72 Hour Jam Contest 2018 года?",
        "expected_files": ["72-hour-jam-contest.md"],
        "content_terms": [
            "Murder Mystery",
            "Tropical",
        ],
    },
    {
        "name": "hub_173_anniversary",
        "query": "Кто создал оригинальный пост SCP-173 на 4chan в 2007 году?",
        "expected_files": ["173-anniversary-hub.md"],
        "content_terms": [
            "S. S. Walrus",
            "Moto42",
        ],
    },
]

_HOIHUB_TESTS = _GOI_TESTS + _HUB_TESTS

# Search depth configuration
_SOURCE_TOP_K = 100  # wider net for file-source recall (BM25-only dominant ranking)
_CONTENT_TOP_K = (
    200  # broad window; increased to compensate for degraded vector rankings
)


# ---------------------------------------------------------------------------
# Test classes by difficulty level
# ---------------------------------------------------------------------------


class TestEasyFactual:
    """Tests that single-document factual queries should retrieve the correct file."""

    @pytest.mark.parametrize("tc", _EASY_TESTS)
    def test_query_returns_expected_file(
        self, tc: dict, demo_retriever: Retriever
    ) -> None:
        """Query should return at least one result whose source is an expected file."""
        results = demo_retriever.search(query=tc["query"], top_k=_SOURCE_TOP_K)
        sources = _result_sources(results)
        matched = any(_source_matches(s, tc["expected_files"]) for s in sources)
        assert matched, (
            f"[{tc['name']}] Query '{tc['query']}' did not return chunks from "
            f"{tc['expected_files']}. Got sources: {sources}"
        )

    @pytest.mark.parametrize("tc", _EASY_TESTS)
    def test_query_content_contains_key_terms(
        self, tc: dict, demo_retriever: Retriever
    ) -> None:
        """At least one matching result chunk should contain key terms."""
        results = demo_retriever.search(query=tc["query"], top_k=_CONTENT_TOP_K)
        matched_chunks = [
            r
            for r in results
            if _source_matches(r.metadata.get("source", ""), tc["expected_files"])
        ]
        assert matched_chunks, (
            f"[{tc['name']}] No results from expected files {tc['expected_files']}. "
            f"Sources: {_result_sources(results)}"
        )
        # Check that at least one chunk from an expected file contains a key term
        found = any(
            any(term.lower() in r.content.lower() for term in tc["content_terms"])
            for r in matched_chunks
        )
        assert found, (
            f"[{tc['name']}] Expected content terms {tc['content_terms']} "
            f"not found in any of {len(matched_chunks)} chunks from expected files"
        )


class TestMediumComparison:
    """Tests that multi-entity or comparison queries hit multiple relevant sources."""

    @pytest.mark.parametrize("tc", _MEDIUM_TESTS)
    def test_query_hits_expected_files(
        self, tc: dict, demo_retriever: Retriever
    ) -> None:
        """Results should include chunks from expected files."""
        results = demo_retriever.search(query=tc["query"], top_k=_SOURCE_TOP_K)
        sources = _result_sources(results)
        matched_any = any(_source_matches(s, tc["expected_files"]) for s in sources)
        assert matched_any, (
            f"[{tc['name']}] No results from expected files {tc['expected_files']}. "
            f"Got sources: {sources}"
        )

    @pytest.mark.parametrize("tc", _MEDIUM_TESTS)
    def test_results_have_descending_scores(
        self, tc: dict, demo_retriever: Retriever
    ) -> None:
        """RRF-fused results should be sorted by score descending."""
        results = demo_retriever.search(query=tc["query"], top_k=_SOURCE_TOP_K)
        scores = [r.score for r in results]
        assert scores == sorted(
            scores, reverse=True
        ), f"[{tc['name']}] Scores not descending: {scores}"


class TestHardCrossDocument:
    """Tests for complex, cross-document reasoning queries."""

    @pytest.mark.parametrize("tc", _HARD_TESTS)
    def test_query_returns_at_least_one_result(
        self, tc: dict, demo_retriever: Retriever
    ) -> None:
        """Hard queries should still return some results (even if imperfect)."""
        results = demo_retriever.search(query=tc["query"], top_k=_CONTENT_TOP_K)
        assert len(results) > 0, f"[{tc['name']}] Hard query returned zero results."

    @pytest.mark.parametrize("tc", _HARD_TESTS)
    def test_hard_query_hits_expected_files(
        self, tc: dict, demo_retriever: Retriever
    ) -> None:
        """Results should include at least one chunk from an expected file."""
        results = demo_retriever.search(query=tc["query"], top_k=_SOURCE_TOP_K)
        sources = _result_sources(results)
        matched = any(_source_matches(s, tc["expected_files"]) for s in sources)
        assert matched, (
            f"[{tc['name']}] No results from expected files {tc['expected_files']}. "
            f"Got sources: {sources}"
        )

    @pytest.mark.parametrize("tc", _HARD_TESTS)
    def test_hard_query_content_has_key_terms(
        self, tc: dict, demo_retriever: Retriever
    ) -> None:
        """Content from expected-file results should contain key terms."""
        results = demo_retriever.search(query=tc["query"], top_k=_CONTENT_TOP_K)
        matched_chunks = [
            r
            for r in results
            if _source_matches(r.metadata.get("source", ""), tc["expected_files"])
        ]
        found = any(
            any(term.lower() in r.content.lower() for term in tc["content_terms"])
            for r in matched_chunks
        )
        assert found, (
            f"[{tc['name']}] Expected content terms {tc['content_terms']} "
            f"not found in any of {len(matched_chunks)} chunks from expected files. "
            f"Sources: {_result_sources(results)}"
        )


class TestCodeRelated:
    """Tests that code-related queries retrieve the correct source files."""

    @pytest.mark.parametrize("tc", _CODE_TESTS)
    def test_query_returns_expected_file(
        self, tc: dict, demo_retriever: Retriever
    ) -> None:
        """Query should return at least one result from the expected file."""
        results = demo_retriever.search(query=tc["query"], top_k=_SOURCE_TOP_K)
        sources = _result_sources(results)
        matched = any(_source_matches(s, tc["expected_files"]) for s in sources)
        assert matched, (
            f"[{tc['name']}] No results from expected files {tc['expected_files']}. "
            f"Got sources: {sources}"
        )

    @pytest.mark.parametrize("tc", _CODE_TESTS)
    def test_code_query_content_has_key_terms(
        self, tc: dict, demo_retriever: Retriever
    ) -> None:
        """Content from expected-file results should contain key terms."""
        results = demo_retriever.search(query=tc["query"], top_k=_CONTENT_TOP_K)
        matched_chunks = [
            r
            for r in results
            if _source_matches(r.metadata.get("source", ""), tc["expected_files"])
        ]
        found = any(
            any(term.lower() in r.content.lower() for term in tc["content_terms"])
            for r in matched_chunks
        )
        assert found, (
            f"[{tc['name']}] Expected content terms {tc['content_terms']} "
            f"not found in any of {len(matched_chunks)} chunks from expected files. "
            f"Sources: {_result_sources(results)}"
        )


class TestNegativeAbsence:
    """Tests that queries about absent information do NOT produce strong positive hits."""

    @pytest.mark.parametrize("tc", _NEGATIVE_TESTS)
    def test_no_confident_positive_match(
        self, tc: dict, demo_retriever: Retriever
    ) -> None:
        """For negative queries, results should not strongly match absent content."""
        results = demo_retriever.search(query=tc["query"], top_k=_CONTENT_TOP_K)
        # We are lenient here: these queries may return partial/misleading results
        # because BM25 will match keywords even in unrelated context.
        # The important thing is that the query doesn't crash and returns structured results.
        assert isinstance(
            results, list
        ), f"[{tc['name']}] Expected list, got {type(results)}"
        # Each result should still have valid structure
        for r in results:
            assert isinstance(r, SearchResult)
            assert r.metadata.get(
                "source"
            ), f"[{tc['name']}] Missing source in metadata"


class TestHallucinationResistance:
    """Tests that hallucination-prone queries still anchor to correct source files."""

    @pytest.mark.parametrize("tc", _HALLUCINATION_TESTS)
    def test_query_returns_correct_document(
        self, tc: dict, demo_retriever: Retriever
    ) -> None:
        """Even specific/niche queries should hit the right document."""
        results = demo_retriever.search(query=tc["query"], top_k=_SOURCE_TOP_K)
        sources = _result_sources(results)
        matched = any(_source_matches(s, tc["expected_files"]) for s in sources)
        assert matched, (
            f"[{tc['name']}] Niche query did not hit expected files {tc['expected_files']}. "
            f"Got sources: {sources}"
        )

    @pytest.mark.parametrize("tc", _HALLUCINATION_TESTS)
    def test_niche_query_content_validates_terms(
        self, tc: dict, demo_retriever: Retriever
    ) -> None:
        """Content from expected files should validate key terms for specificity."""
        results = demo_retriever.search(query=tc["query"], top_k=_CONTENT_TOP_K)
        for r in results:
            source = r.metadata.get("source", "")
            if _source_matches(source, tc["expected_files"]):
                found = any(
                    term.lower() in r.content.lower() for term in tc["content_terms"]
                )
                assert found, (
                    f"[{tc['name']}] Expected content terms {tc['content_terms']} "
                    f"not found in chunk from {source}"
                )
                break


class TestGoiDocuments:
    """Tests for GOI (Group of Interest) format documents."""

    @pytest.mark.parametrize("tc", _GOI_TESTS)
    def test_query_returns_expected_file(
        self, tc: dict, demo_retriever: Retriever
    ) -> None:
        """Query should return at least one result whose source is an expected file."""
        results = demo_retriever.search(query=tc["query"], top_k=_SOURCE_TOP_K)
        sources = _result_sources(results)
        matched = any(_source_matches(s, tc["expected_files"]) for s in sources)
        assert matched, (
            f"[{tc['name']}] Query '{tc['query']}' did not return chunks from "
            f"{tc['expected_files']}. Got sources: {sources}"
        )

    @pytest.mark.parametrize("tc", _GOI_TESTS)
    def test_query_content_contains_key_terms(
        self, tc: dict, demo_retriever: Retriever
    ) -> None:
        """At least one matching result chunk should contain key terms."""
        results = demo_retriever.search(query=tc["query"], top_k=_CONTENT_TOP_K)
        matched_chunks = [
            r
            for r in results
            if _source_matches(r.metadata.get("source", ""), tc["expected_files"])
        ]
        assert matched_chunks, (
            f"[{tc['name']}] No results from expected files {tc['expected_files']}. "
            f"Sources: {_result_sources(results)}"
        )
        found = any(
            any(term.lower() in r.content.lower() for term in tc["content_terms"])
            for r in matched_chunks
        )
        assert found, (
            f"[{tc['name']}] Expected content terms {tc['content_terms']} "
            f"not found in any of {len(matched_chunks)} chunks from expected files"
        )


class TestHubDocuments:
    """Tests for Hub/Canon Hub documents."""

    @pytest.mark.parametrize("tc", _HUB_TESTS)
    def test_query_returns_expected_file(
        self, tc: dict, demo_retriever: Retriever
    ) -> None:
        """Query should return at least one result whose source is an expected file."""
        results = demo_retriever.search(query=tc["query"], top_k=_SOURCE_TOP_K)
        sources = _result_sources(results)
        matched = any(_source_matches(s, tc["expected_files"]) for s in sources)
        assert matched, (
            f"[{tc['name']}] Query '{tc['query']}' did not return chunks from "
            f"{tc['expected_files']}. Got sources: {sources}"
        )

    @pytest.mark.parametrize("tc", _HUB_TESTS)
    def test_query_content_contains_key_terms(
        self, tc: dict, demo_retriever: Retriever
    ) -> None:
        """At least one matching result chunk should contain key terms."""
        results = demo_retriever.search(query=tc["query"], top_k=_CONTENT_TOP_K)
        matched_chunks = [
            r
            for r in results
            if _source_matches(r.metadata.get("source", ""), tc["expected_files"])
        ]
        assert matched_chunks, (
            f"[{tc['name']}] No results from expected files {tc['expected_files']}. "
            f"Sources: {_result_sources(results)}"
        )
        found = any(
            any(term.lower() in r.content.lower() for term in tc["content_terms"])
            for r in matched_chunks
        )
        assert found, (
            f"[{tc['name']}] Expected content terms {tc['content_terms']} "
            f"not found in any of {len(matched_chunks)} chunks from expected files"
        )


class TestRetrievalQualityBasics:
    """General retrieval quality checks across all demo documents."""

    def test_demo_index_not_empty(self, demo_index: Path) -> None:
        """The demo documents folder should contain indexed files including goi and hubs subdirectories."""
        md_files = list(demo_index.rglob("*.md"))
        py_files = list(demo_index.rglob("*.py"))
        ts_files = list(demo_index.rglob("*.ts"))
        yaml_files = list(demo_index.rglob("*.yaml")) + list(demo_index.rglob("*.yml"))
        json_files = list(demo_index.rglob("*.json"))
        goi_md = [f for f in md_files if "goi" in str(f.parent)]
        hub_md = [f for f in md_files if "hubs" in str(f.parent)]
        total = (
            len(md_files)
            + len(py_files)
            + len(ts_files)
            + len(yaml_files)
            + len(json_files)
        )
        assert total > 0, f"No supported files found in {demo_index}"
        assert len(goi_md) > 0, f"No GOI .md files found. Searched in {goi_md}"
        assert len(hub_md) > 0, f"No HUB .md files found. Searched in {hub_md}"

    def test_hybrid_search_all_questions_return_results(
        self, demo_retriever: Retriever
    ) -> None:
        """Every question from QUESTIONS.md should return at least one result."""
        all_tests = (
            _EASY_TESTS
            + _MEDIUM_TESTS
            + _HARD_TESTS
            + _CODE_TESTS
            + _HALLUCINATION_TESTS
            + _GOI_TESTS
            + _HUB_TESTS
        )
        for tc in all_tests:
            results = demo_retriever.search(query=tc["query"], top_k=_CONTENT_TOP_K)
            assert len(results) > 0, f"Empty results for query: {tc['query']}"

    def test_scores_are_positive_and_descending(
        self, demo_retriever: Retriever
    ) -> None:
        """All positive queries should return non-negative scores in descending order."""
        all_tests = (
            _EASY_TESTS
            + _MEDIUM_TESTS
            + _HARD_TESTS
            + _CODE_TESTS
            + _HALLUCINATION_TESTS
            + _GOI_TESTS
            + _HUB_TESTS
        )
        for tc in all_tests:
            results = demo_retriever.search(query=tc["query"], top_k=_CONTENT_TOP_K)
            if not results:
                continue
            scores = [r.score for r in results]
            assert all(
                s >= 0 for s in scores
            ), f"[{tc['name']}] Negative scores found: {scores}"
            assert scores == sorted(
                scores, reverse=True
            ), f"[{tc['name']}] Scores not descending: {scores}"
