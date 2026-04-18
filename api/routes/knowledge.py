"""Knowledge base: list, upload, reindex, delete."""

import os
import shutil

from fastapi import APIRouter, File, HTTPException, UploadFile

from knowledge import KnowledgeBase, KNOWLEDGE_DIR, SUPPORTED_EXTENSIONS
from api.schemas import KnowledgeDoc, KnowledgeOpResult, KnowledgeOverview

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


def _kb() -> KnowledgeBase:
    return KnowledgeBase()


def _overview(kb: KnowledgeBase) -> KnowledgeOverview:
    docs: dict[str, int] = {}
    if kb._collection.count() > 0:
        for meta in kb._collection.get()["metadatas"]:
            source = meta.get("source", "unknown")
            docs[source] = docs.get(source, 0) + 1
    return KnowledgeOverview(
        total_chunks=kb._collection.count(),
        documents=[
            KnowledgeDoc(filename=name, chunks=count)
            for name, count in sorted(docs.items())
        ],
    )


@router.get("", response_model=KnowledgeOverview)
async def list_documents() -> KnowledgeOverview:
    return _overview(_kb())


@router.post("/upload", response_model=KnowledgeOpResult)
async def upload(files: list[UploadFile] = File(...)) -> KnowledgeOpResult:
    if not files:
        raise HTTPException(400, "no files provided")

    os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
    kb = _kb()
    messages: list[str] = []

    for upload in files:
        ext = os.path.splitext(upload.filename)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            messages.append(f"skipped {upload.filename}: unsupported extension {ext}")
            continue

        dest = os.path.join(KNOWLEDGE_DIR, os.path.basename(upload.filename))
        with open(dest, "wb") as out:
            shutil.copyfileobj(upload.file, out)
        messages.append(kb.add_document(dest))

    return KnowledgeOpResult(message="\n".join(messages), overview=_overview(kb))


@router.post("/reindex", response_model=KnowledgeOpResult)
async def reindex() -> KnowledgeOpResult:
    kb = _kb()
    return KnowledgeOpResult(message=kb.index_all(), overview=_overview(kb))


@router.delete("/{filename}", response_model=KnowledgeOpResult)
async def delete_document(filename: str) -> KnowledgeOpResult:
    kb = _kb()
    msg = kb.remove_document(filename)
    path = os.path.join(KNOWLEDGE_DIR, filename)
    if os.path.isfile(path):
        os.remove(path)
    return KnowledgeOpResult(message=msg, overview=_overview(kb))
