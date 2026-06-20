#!/usr/bin/env python3
"""
ingest.py
---------
Standalone script to (re)build the vector index from /data.

Usage:
    python ingest.py            # ingest only if the collection is empty
    python ingest.py --force    # wipe and rebuild the index from scratch

Run this once after adding/editing knowledge base documents. Both cli.py
and app.py also call this automatically on first launch, but a dedicated
script makes the ingestion step easy to demo and re-run independently.
"""

import argparse
import sys
import time

from src.config import validate_settings
from src.rag_pipeline import LocalRAGPipeline, load_and_chunk_documents


def main():
    parser = argparse.ArgumentParser(description="Ingest the support knowledge base into ChromaDB.")
    parser.add_argument("--force", action="store_true", help="Rebuild the index even if it already exists.")
    args = parser.parse_args()

    problems = validate_settings()
    if problems:
        for p in problems:
            print(f"[CONFIG WARNING] {p}", file=sys.stderr)
        if not any("GEMINI_API_KEY" not in p for p in problems):
            pass  # missing key is a warning, not a hard stop, for inspection purposes
        if any("data directory" in p.lower() for p in problems):
            sys.exit(1)

    print("Loading and chunking documents from /data ...")
    chunks = load_and_chunk_documents()
    by_doc = {}
    for c in chunks:
        by_doc.setdefault(c.source, 0)
        by_doc[c.source] += 1
    for doc, count in sorted(by_doc.items()):
        print(f"  - {doc}: {count} chunk(s)")
    print(f"Total: {len(chunks)} chunks across {len(by_doc)} document(s).\n")

    print("Connecting to ChromaDB and generating embeddings via Gemini ...")
    start = time.time()
    pipeline = LocalRAGPipeline()
    total = pipeline.ingest_all(force=args.force)
    elapsed = time.time() - start

    print(f"Done. Collection now contains {total} chunks. ({elapsed:.1f}s)")
    print(f"Persisted to: {pipeline.db_dir}")


if __name__ == "__main__":
    main()
