"""Knowledge base tools: search, index, and manage user documents."""

import os

from langchain_core.tools import Tool

from config import SANDBOX_DIR
from knowledge import KnowledgeBase


_kb: KnowledgeBase | None = None


def _get_kb() -> KnowledgeBase:
    """Lazy-initialise and return the singleton KnowledgeBase instance."""
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb


def search_knowledge_base(query: str) -> str:
    """Search your personal knowledge base for information relevant to the query."""
    kb = _get_kb()
    return kb.search(query)


def add_to_knowledge_base(file_path: str) -> str:
    """Add a document to the knowledge base for future semantic search.
    Pass a file path relative to the sandbox directory.
    """
    full_path = os.path.join(SANDBOX_DIR, file_path)
    kb = _get_kb()
    return kb.add_document(full_path)


def list_knowledge_base() -> str:
    """List all documents currently indexed in the knowledge base."""
    kb = _get_kb()
    return kb.list_documents()


def remove_from_knowledge_base(filename: str) -> str:
    """Remove a document from the knowledge base by filename."""
    kb = _get_kb()
    return kb.remove_document(filename)


def reindex_knowledge_base() -> str:
    """Re-scan the sandbox/knowledge/ directory and index all new or changed files."""
    kb = _get_kb()
    return kb.index_all()


def get_tools():
    """Return all knowledge base tools."""
    return [
        Tool(
            name="search_knowledge_base",
            func=search_knowledge_base,
            description=(
                "Search your personal knowledge base for information relevant to a query. "
                "Returns the most relevant text chunks with source file info."
            ),
        ),
        Tool(
            name="add_to_knowledge_base",
            func=add_to_knowledge_base,
            description=(
                "Add a document to the knowledge base for future semantic search. "
                "Pass a file path relative to the sandbox directory. "
                "Supported formats: PDF, TXT, Markdown, CSV."
            ),
        ),
        Tool(
            name="list_knowledge_base",
            func=list_knowledge_base,
            description="List all documents currently indexed in the knowledge base with their chunk counts.",
        ),
        Tool(
            name="remove_from_knowledge_base",
            func=remove_from_knowledge_base,
            description="Remove a document from the knowledge base search index by filename.",
        ),
    ]
