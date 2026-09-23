"""Chroma vector store wrapper (single collection: hr_docs)."""
from langchain_chroma import Chroma

from app.config import settings
from app.embeddings import get_embeddings

_COLLECTION_NAME = "hr_docs"
_store: Chroma | None = None


def get_vectorstore() -> Chroma:
    global _store
    if _store is None:
        persist_dir = str(settings.resolve_path(settings.chroma_dir))
        _store = Chroma(
            collection_name=_COLLECTION_NAME,
            embedding_function=get_embeddings(),
            persist_directory=persist_dir,
        )
    return _store
