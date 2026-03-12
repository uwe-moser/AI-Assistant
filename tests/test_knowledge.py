"""
Unit tests for the Knowledge Base module (knowledge.py).

Tests document indexing, search, listing, and removal with mocked
OpenAI embeddings so no API calls are made.

Run with:  pytest tests/test_knowledge.py -v --tb=short
"""

import os
import json
from unittest.mock import patch, MagicMock

import pytest

# Capture real os.path.join before any patching
_real_path_join = os.path.join


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def kb_dirs(tmp_path):
    """Create temporary knowledge and chroma directories."""
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    chroma_dir = tmp_path / "chroma_db"
    chroma_dir.mkdir()
    return str(knowledge_dir), str(chroma_dir)


@pytest.fixture
def mock_embeddings():
    """Patch OpenAIEmbeddings to return deterministic fake vectors."""
    with patch("knowledge.OpenAIEmbeddings") as MockEmbed:
        mock_instance = MagicMock()
        # Return a 10-dim vector for each document chunk
        mock_instance.embed_documents.side_effect = lambda texts: [
            [float(i)] * 10 for i in range(len(texts))
        ]
        mock_instance.embed_query.return_value = [0.5] * 10
        MockEmbed.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def kb(kb_dirs, mock_embeddings):
    """Create a KnowledgeBase instance with mocked embeddings and temp dirs."""
    from knowledge import KnowledgeBase

    knowledge_dir, chroma_dir = kb_dirs
    return KnowledgeBase(
        knowledge_dir=knowledge_dir,
        chroma_dir=chroma_dir,
        collection_name="test_kb",
    )


@pytest.fixture
def sample_txt(kb_dirs):
    """Create a sample text file in the knowledge directory."""
    knowledge_dir, _ = kb_dirs
    path = os.path.join(knowledge_dir, "notes.txt")
    with open(path, "w") as f:
        f.write("This is a test document about machine learning.\n"
                "Neural networks are a key technique in deep learning.\n"
                "Transformers have revolutionised natural language processing.")
    return path


@pytest.fixture
def sample_md(kb_dirs):
    """Create a sample markdown file in the knowledge directory."""
    knowledge_dir, _ = kb_dirs
    path = os.path.join(knowledge_dir, "guide.md")
    with open(path, "w") as f:
        f.write("# Python Guide\n\n"
                "Python is a versatile programming language.\n"
                "It is widely used in data science and web development.")
    return path


@pytest.fixture
def sample_csv(kb_dirs):
    """Create a sample CSV file in the knowledge directory."""
    knowledge_dir, _ = kb_dirs
    path = os.path.join(knowledge_dir, "data.csv")
    with open(path, "w") as f:
        f.write("Name,Score,Topic\n"
                "Alice,95,Mathematics\n"
                "Bob,87,Physics\n"
                "Carol,92,Chemistry\n")
    return path


@pytest.fixture
def sample_pdf(kb_dirs):
    """Create a sample PDF in the knowledge directory."""
    from fpdf import FPDF

    knowledge_dir, _ = kb_dirs
    path = os.path.join(knowledge_dir, "report.pdf")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(200, 10, text="Quarterly Report Q3 2025")
    pdf.ln(10)
    pdf.cell(200, 10, text="Revenue increased by 15 percent year over year.")
    pdf.output(path)
    return path


# ===================================================================
# Text Extraction
# ===================================================================

class TestExtractText:
    """Tests for the _extract_text helper."""

    def test_extracts_txt(self, sample_txt):
        from knowledge import _extract_text
        text = _extract_text(sample_txt)
        assert "machine learning" in text
        assert "Transformers" in text

    def test_extracts_md(self, sample_md):
        from knowledge import _extract_text
        text = _extract_text(sample_md)
        assert "Python Guide" in text
        assert "data science" in text

    def test_extracts_csv(self, sample_csv):
        from knowledge import _extract_text
        text = _extract_text(sample_csv)
        assert "Alice" in text
        assert "Mathematics" in text

    def test_extracts_pdf(self, sample_pdf):
        from knowledge import _extract_text
        text = _extract_text(sample_pdf)
        assert "Quarterly Report" in text

    def test_unsupported_extension_returns_empty(self, tmp_path):
        from knowledge import _extract_text
        path = str(tmp_path / "data.json")
        with open(path, "w") as f:
            f.write('{"key": "value"}')
        assert _extract_text(path) == ""


# ===================================================================
# File Hash
# ===================================================================

class TestFileHash:
    """Tests for the _file_hash helper."""

    def test_same_content_same_hash(self, tmp_path):
        from knowledge import _file_hash
        f1 = str(tmp_path / "a.txt")
        f2 = str(tmp_path / "b.txt")
        for path in (f1, f2):
            with open(path, "w") as f:
                f.write("identical content")
        assert _file_hash(f1) == _file_hash(f2)

    def test_different_content_different_hash(self, tmp_path):
        from knowledge import _file_hash
        f1 = str(tmp_path / "a.txt")
        f2 = str(tmp_path / "b.txt")
        with open(f1, "w") as f:
            f.write("content A")
        with open(f2, "w") as f:
            f.write("content B")
        assert _file_hash(f1) != _file_hash(f2)


# ===================================================================
# KnowledgeBase — add_document
# ===================================================================

class TestAddDocument:
    """Tests for KnowledgeBase.add_document."""

    def test_adds_txt_file(self, kb, sample_txt):
        result = kb.add_document(sample_txt)
        assert "Indexed" in result
        assert "notes.txt" in result
        assert "chunks" in result

    def test_adds_pdf_file(self, kb, sample_pdf):
        result = kb.add_document(sample_pdf)
        assert "Indexed" in result
        assert "report.pdf" in result

    def test_adds_csv_file(self, kb, sample_csv):
        result = kb.add_document(sample_csv)
        assert "Indexed" in result
        assert "data.csv" in result

    def test_adds_md_file(self, kb, sample_md):
        result = kb.add_document(sample_md)
        assert "Indexed" in result
        assert "guide.md" in result

    def test_file_not_found(self, kb):
        result = kb.add_document("/nonexistent/file.txt")
        assert "Error" in result
        assert "not found" in result

    def test_unsupported_extension(self, kb, tmp_path):
        path = str(tmp_path / "data.json")
        with open(path, "w") as f:
            f.write('{"key": "value"}')
        result = kb.add_document(path)
        assert "Error" in result
        assert "unsupported" in result

    def test_empty_file(self, kb, kb_dirs):
        knowledge_dir, _ = kb_dirs
        path = os.path.join(knowledge_dir, "empty.txt")
        with open(path, "w") as f:
            f.write("")
        result = kb.add_document(path)
        assert "Error" in result
        assert "no extractable text" in result

    def test_reindex_replaces_old_chunks(self, kb, sample_txt):
        # Index the file twice
        kb.add_document(sample_txt)
        first_count = kb._collection.count()

        kb.add_document(sample_txt)
        second_count = kb._collection.count()

        # Should be the same — old chunks are removed before adding new ones
        assert first_count == second_count

    def test_resolves_filename_in_knowledge_dir(self, kb, sample_txt):
        # Pass just the filename — should resolve inside knowledge_dir
        result = kb.add_document("notes.txt")
        assert "Indexed" in result


# ===================================================================
# KnowledgeBase — search
# ===================================================================

class TestSearch:
    """Tests for KnowledgeBase.search."""

    def test_empty_kb_returns_message(self, kb):
        result = kb.search("anything")
        assert "empty" in result.lower()

    def test_search_returns_results(self, kb, sample_txt):
        kb.add_document(sample_txt)
        result = kb.search("neural networks")
        assert "Result 1" in result
        assert "notes.txt" in result

    def test_search_returns_similarity_score(self, kb, sample_txt):
        kb.add_document(sample_txt)
        result = kb.search("deep learning")
        assert "similarity" in result

    def test_search_respects_k_parameter(self, kb, sample_txt):
        kb.add_document(sample_txt)
        result = kb.search("machine learning", k=1)
        assert "Result 1" in result
        assert "Result 2" not in result

    def test_search_multiple_documents(self, kb, sample_txt, sample_md):
        kb.add_document(sample_txt)
        kb.add_document(sample_md)
        result = kb.search("programming")
        assert "Result 1" in result


# ===================================================================
# KnowledgeBase — list_documents
# ===================================================================

class TestListDocuments:
    """Tests for KnowledgeBase.list_documents."""

    def test_empty_kb(self, kb):
        result = kb.list_documents()
        assert "empty" in result.lower()

    def test_lists_indexed_documents(self, kb, sample_txt, sample_md):
        kb.add_document(sample_txt)
        kb.add_document(sample_md)
        result = kb.list_documents()
        assert "notes.txt" in result
        assert "guide.md" in result
        assert "2 document(s)" in result

    def test_shows_chunk_counts(self, kb, sample_txt):
        kb.add_document(sample_txt)
        result = kb.list_documents()
        assert "chunks" in result.lower()


# ===================================================================
# KnowledgeBase — remove_document
# ===================================================================

class TestRemoveDocument:
    """Tests for KnowledgeBase.remove_document."""

    def test_remove_nonexistent(self, kb):
        result = kb.remove_document("nonexistent.txt")
        assert "No indexed chunks" in result

    def test_remove_existing(self, kb, sample_txt):
        kb.add_document(sample_txt)
        assert kb._collection.count() > 0

        result = kb.remove_document("notes.txt")
        assert "Removed" in result
        assert kb._collection.count() == 0

    def test_remove_only_target_document(self, kb, sample_txt, sample_md):
        kb.add_document(sample_txt)
        kb.add_document(sample_md)
        total_before = kb._collection.count()

        kb.remove_document("notes.txt")
        total_after = kb._collection.count()

        assert total_after < total_before
        # guide.md should still be there
        result = kb.list_documents()
        assert "guide.md" in result
        assert "notes.txt" not in result


# ===================================================================
# KnowledgeBase — index_all
# ===================================================================

class TestIndexAll:
    """Tests for KnowledgeBase.index_all."""

    def test_index_empty_directory(self, kb):
        result = kb.index_all()
        assert "No supported files" in result

    def test_indexes_all_files(self, kb, sample_txt, sample_md):
        result = kb.index_all()
        assert "Re-index complete" in result
        assert "2 files scanned" in result
        assert kb._collection.count() > 0

    def test_skips_unchanged_files(self, kb, sample_txt):
        kb.index_all()
        # Index again — file hasn't changed
        result = kb.index_all()
        assert "unchanged" in result

    def test_reindexes_changed_file(self, kb, sample_txt):
        kb.index_all()
        # Modify the file
        with open(sample_txt, "a") as f:
            f.write("\nNew content added.")
        result = kb.index_all()
        assert "Indexed" in result

    def test_nonexistent_directory(self, kb):
        kb.knowledge_dir = "/nonexistent/path"
        result = kb.index_all()
        assert "does not exist" in result


# ===================================================================
# Tool functions in sidekick_tools.py
# ===================================================================

class TestKnowledgeBaseTools:
    """Tests for the knowledge base tool wrappers in sidekick_tools.py."""

    def test_search_kb_tool_delegates(self, kb):
        with patch("sidekick_tools._get_kb", return_value=kb):
            from sidekick_tools import search_knowledge_base
            result = search_knowledge_base("test query")
            assert "empty" in result.lower()

    def test_add_kb_tool_delegates(self, kb, sample_txt):
        with patch("sidekick_tools._get_kb", return_value=kb):
            with patch("sidekick_tools.os.path.join", return_value=sample_txt):
                from sidekick_tools import add_to_knowledge_base
                result = add_to_knowledge_base("notes.txt")
                assert "Indexed" in result

    def test_list_kb_tool_delegates(self, kb):
        with patch("sidekick_tools._get_kb", return_value=kb):
            from sidekick_tools import list_knowledge_base
            result = list_knowledge_base()
            assert "empty" in result.lower()

    def test_remove_kb_tool_delegates(self, kb):
        with patch("sidekick_tools._get_kb", return_value=kb):
            from sidekick_tools import remove_from_knowledge_base
            result = remove_from_knowledge_base("nonexistent.txt")
            assert "No indexed chunks" in result

    def test_reindex_kb_tool_delegates(self, kb):
        with patch("sidekick_tools._get_kb", return_value=kb):
            from sidekick_tools import reindex_knowledge_base
            result = reindex_knowledge_base()
            assert "No supported files" in result
