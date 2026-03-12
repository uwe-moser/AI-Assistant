"""
Knowledge Base module for ApexFlow.

Provides document indexing, embedding, and semantic search over local files
using ChromaDB as the vector store and OpenAI embeddings.

Supported file types: PDF, TXT, Markdown, CSV.
"""

import hashlib
import os
from typing import Optional

import chromadb
from chromadb.config import Settings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from pypdf import PdfReader


KNOWLEDGE_DIR = os.path.join("sandbox", "knowledge")
CHROMA_DIR = os.path.join("sandbox", "chroma_db")

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".md", ".csv"}

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def _file_hash(path: str) -> str:
    """Return the SHA-256 hex digest of a file's contents."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return h.hexdigest()


def _extract_text(path: str) -> str:
    """Extract plain text from a supported file."""
    ext = os.path.splitext(path)[1].lower()

    if ext == ".pdf":
        reader = PdfReader(path)
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text)
        return "\n\n".join(pages)

    if ext in (".txt", ".md", ".csv"):
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()

    return ""


class KnowledgeBase:
    """Manages a ChromaDB-backed vector store for local document search."""

    def __init__(
        self,
        knowledge_dir: str = KNOWLEDGE_DIR,
        chroma_dir: str = CHROMA_DIR,
        collection_name: str = "apexflow_kb",
    ):
        self.knowledge_dir = knowledge_dir
        self.chroma_dir = chroma_dir
        self.collection_name = collection_name

        self._embeddings = OpenAIEmbeddings()
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )

        os.makedirs(self.knowledge_dir, exist_ok=True)
        os.makedirs(self.chroma_dir, exist_ok=True)

        self._client = chromadb.PersistentClient(
            path=self.chroma_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_document(self, file_path: str) -> str:
        """Index a single file. Returns a status message.

        Args:
            file_path: Path to the file — either absolute, relative to cwd,
                       or just a filename (resolved inside knowledge_dir).
        """
        path = self._resolve_path(file_path)
        if not os.path.isfile(path):
            return f"Error: file not found at {path}"

        ext = os.path.splitext(path)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            return f"Error: unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"

        text = _extract_text(path)
        if not text.strip():
            return f"Error: no extractable text in {os.path.basename(path)}"

        filename = os.path.basename(path)
        file_hash = _file_hash(path)

        # Remove old chunks for this file before re-indexing
        self._remove_chunks_for_file(filename)

        chunks = self._splitter.split_text(text)
        embeddings = self._embeddings.embed_documents(chunks)

        ids = [f"{filename}::{i}" for i in range(len(chunks))]
        metadatas = [
            {"source": filename, "chunk_index": i, "file_hash": file_hash}
            for i in range(len(chunks))
        ]

        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas,
        )

        return f"Indexed '{filename}': {len(chunks)} chunks added to knowledge base."

    def index_all(self) -> str:
        """Scan the knowledge directory and index all supported files.

        Skips files whose hash hasn't changed since last indexing.
        """
        if not os.path.isdir(self.knowledge_dir):
            return "Knowledge directory does not exist."

        files = [
            f for f in os.listdir(self.knowledge_dir)
            if os.path.splitext(f)[1].lower() in SUPPORTED_EXTENSIONS
        ]

        if not files:
            return "No supported files found in the knowledge directory."

        results = []
        for filename in sorted(files):
            path = os.path.join(self.knowledge_dir, filename)
            file_hash = _file_hash(path)

            # Check if already indexed with the same hash
            existing = self._collection.get(
                where={"source": filename},
                limit=1,
            )
            if existing["metadatas"] and existing["metadatas"][0].get("file_hash") == file_hash:
                results.append(f"  {filename}: unchanged, skipped")
                continue

            result = self.add_document(path)
            results.append(f"  {result}")

        return f"Re-index complete ({len(files)} files scanned):\n" + "\n".join(results)

    def search(self, query: str, k: int = 5) -> str:
        """Search the knowledge base for chunks relevant to the query.

        Returns a formatted string with the top-k results.
        """
        if self._collection.count() == 0:
            return "The knowledge base is empty. Add documents first."

        query_embedding = self._embeddings.embed_query(query)

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(k, self._collection.count()),
        )

        if not results["documents"] or not results["documents"][0]:
            return "No relevant results found."

        output_parts = []
        for i, (doc, meta, dist) in enumerate(zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )):
            similarity = 1 - dist  # cosine distance to similarity
            source = meta.get("source", "unknown")
            chunk_idx = meta.get("chunk_index", "?")
            output_parts.append(
                f"--- Result {i + 1} [source: {source}, chunk: {chunk_idx}, "
                f"similarity: {similarity:.3f}] ---\n{doc}"
            )

        return "\n\n".join(output_parts)

    def list_documents(self) -> str:
        """List all indexed documents with their chunk counts."""
        if self._collection.count() == 0:
            return "The knowledge base is empty."

        all_meta = self._collection.get()["metadatas"]
        doc_chunks: dict[str, int] = {}
        for meta in all_meta:
            source = meta.get("source", "unknown")
            doc_chunks[source] = doc_chunks.get(source, 0) + 1

        lines = [f"Knowledge base contains {len(doc_chunks)} document(s):"]
        for source, count in sorted(doc_chunks.items()):
            lines.append(f"  - {source} ({count} chunks)")
        lines.append(f"Total chunks: {self._collection.count()}")
        return "\n".join(lines)

    def remove_document(self, filename: str) -> str:
        """Remove all chunks for a given filename from the index."""
        removed = self._remove_chunks_for_file(filename)
        if removed == 0:
            return f"No indexed chunks found for '{filename}'."
        return f"Removed {removed} chunks for '{filename}' from the knowledge base."

    def _remove_chunks_for_file(self, filename: str) -> int:
        """Delete all chunks whose source matches filename. Returns count removed."""
        existing = self._collection.get(where={"source": filename})
        if existing["ids"]:
            self._collection.delete(ids=existing["ids"])
            return len(existing["ids"])
        return 0

    def _resolve_path(self, file_path: str) -> str:
        """Resolve a file path: absolute stays as-is, relative checked against
        knowledge_dir first, then cwd."""
        if os.path.isabs(file_path):
            return file_path
        # Check if it's in the knowledge directory
        in_knowledge = os.path.join(self.knowledge_dir, file_path)
        if os.path.isfile(in_knowledge):
            return in_knowledge
        # Fall back to relative from cwd
        return file_path
