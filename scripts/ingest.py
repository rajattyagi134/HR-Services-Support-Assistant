"""CLI helper: ingest every PDF currently in data/pdfs into ChromaDB.

Usage:
    python scripts/ingest.py
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.ingestion import ingest_directory  # noqa: E402


def main():
    pdf_dir = settings.resolve_path(settings.pdf_dir)
    files, chunks = ingest_directory(pdf_dir)
    if not files:
        print(f"No PDFs found in {pdf_dir}. Add some HR policy PDFs there first.")
        return
    print(f"Ingested {len(files)} file(s), {chunks} chunk(s) total:")
    for name in files:
        print(f"  - {name}")


if __name__ == "__main__":
    main()
