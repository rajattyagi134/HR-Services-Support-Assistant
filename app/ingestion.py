"""PDF ingestion pipeline: load -> split -> embed -> store in Chroma."""
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.vectorstore import get_vectorstore

_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)


def ingest_pdf(path: Path) -> int:
    """Load a single PDF, chunk it, and add it to the vector store. Returns chunk count."""
    loader = PyPDFLoader(str(path))
    docs = loader.load()
    for doc in docs:
        doc.metadata["source"] = path.name

    chunks = _splitter.split_documents(docs)
    if not chunks:
        return 0

    store = get_vectorstore()
    store.add_documents(chunks)
    return len(chunks)


def ingest_directory(directory: Path) -> tuple[list[str], int]:
    files_ingested: list[str] = []
    total_chunks = 0
    for pdf_path in sorted(directory.glob("*.pdf")):
        added = ingest_pdf(pdf_path)
        if added:
            files_ingested.append(pdf_path.name)
            total_chunks += added
    return files_ingested, total_chunks
