"""
rag_pipeline.py
----------------
The Retrieval-Augmented Generation pipeline: loads the /data knowledge base,
chunks it, embeds each chunk with Gemini's text-embedding-004, stores the
vectors in a persistent ChromaDB collection, and retrieves the top-k most
relevant chunks for a given query.

Design notes
------------
- Chunking uses LangChain's RecursiveCharacterTextSplitter when the package
  is available (as specified in the assignment's tech stack), with a
  behaviourally-equivalent pure-Python fallback so the module still imports
  and the pipeline still runs in environments where langchain isn't
  installed. The fallback uses the exact same separator-priority algorithm
  (paragraphs -> lines -> sentences -> words -> characters).
- Every chunk's metadata includes the source filename and a position marker:
  the PDF page number for PDFs, or the nearest preceding Markdown/plain-text
  section heading otherwise — satisfying the "source + page/section" metadata
  requirement.
- ChromaDB is used in persistent mode so the index survives across runs and
  doesn't need to be rebuilt on every app launch (see ingest_if_needed()).
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.config import settings
from src.utils import call_with_backoff, get_genai_client


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------
def _split_text_fallback(text: str, chunk_size: int, chunk_overlap: int) -> list:
    """
    Pure-Python re-implementation of LangChain's RecursiveCharacterTextSplitter
    behaviour: recursively try separators in priority order (paragraph,
    line, sentence/word, character) so chunks break at the most natural
    boundary available, then apply a sliding overlap between chunks.
    """
    separators = ["\n\n", "\n", ". ", " ", ""]

    def split_on(text_piece, seps):
        if not seps:
            return [text_piece]
        sep = seps[0]
        if sep == "":
            return list(text_piece)
        parts = text_piece.split(sep)
        # Re-attach separator (except for the trailing piece) so meaning is preserved
        rebuilt = [p + sep if i < len(parts) - 1 else p for i, p in enumerate(parts)]
        return [p for p in rebuilt if p != ""]

    def recursive_merge(pieces, seps):
        # Greedily merge small pieces up to chunk_size; recurse into any
        # piece that's still too large using the next separator.
        chunks, current = [], ""
        for piece in pieces:
            if len(piece) > chunk_size and seps[1:]:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.extend(recursive_merge(split_on(piece, seps[1:]), seps[1:]))
                continue
            if len(current) + len(piece) <= chunk_size:
                current += piece
            else:
                if current:
                    chunks.append(current)
                current = piece
        if current:
            chunks.append(current)
        return chunks

    raw_chunks = recursive_merge(split_on(text, separators), separators)

    # Apply overlap
    if chunk_overlap <= 0 or len(raw_chunks) <= 1:
        return [c.strip() for c in raw_chunks if c.strip()]

    overlapped = []
    for i, chunk in enumerate(raw_chunks):
        if i == 0:
            overlapped.append(chunk)
        else:
            prev_tail = raw_chunks[i - 1][-chunk_overlap:]
            overlapped.append(prev_tail + chunk)
    return [c.strip() for c in overlapped if c.strip()]


def split_text(text: str, chunk_size: int, chunk_overlap: int) -> list:
    """Splits text into chunks, preferring LangChain's splitter if installed."""
    try:
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
        except ImportError:
            from langchain.text_splitter import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )
        return splitter.split_text(text)
    except ImportError:
        return _split_text_fallback(text, chunk_size, chunk_overlap)


def _nearest_heading(text: str, position: int) -> str:
    """Finds the nearest preceding Markdown '#' heading before `position`."""
    preceding = text[:position]
    heading = "General"
    for line in preceding.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
    return heading


# ---------------------------------------------------------------------------
# Document loading
# ---------------------------------------------------------------------------
@dataclass
class LoadedChunk:
    text: str
    source: str
    section: str
    page: Optional[int] = None


def _load_pdf(path: Path) -> list:
    """Extracts text per page from a PDF, then chunks each page independently
    so page-number metadata stays accurate."""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    chunks = []
    for page_num, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        if not page_text.strip():
            continue
        for piece in split_text(page_text, settings.chunk_size, settings.chunk_overlap):
            chunks.append(LoadedChunk(text=piece, source=path.name, section=None, page=page_num))
    return chunks


def _load_text_like(path: Path) -> list:
    """Loads a .txt or .md file natively and chunks it, tagging each chunk
    with the nearest preceding section heading."""
    text = path.read_text(encoding="utf-8")
    chunks = []
    cursor = 0
    for piece in split_text(text, settings.chunk_size, settings.chunk_overlap):
        # Best-effort locate the chunk to find its nearest heading
        pos = text.find(piece[:40], cursor) if piece else cursor
        pos = pos if pos != -1 else cursor
        section = _nearest_heading(text, pos)
        chunks.append(LoadedChunk(text=piece, source=path.name, section=section, page=None))
        cursor = max(cursor, pos)
    return chunks


def load_and_chunk_documents(data_dir: Optional[str] = None) -> list:
    """Loads every supported file in the data directory and returns a flat
    list of LoadedChunk objects ready for embedding."""
    data_path = Path(data_dir or settings.data_dir)
    all_chunks = []
    for path in sorted(data_path.iterdir()):
        if path.suffix.lower() == ".pdf":
            all_chunks.extend(_load_pdf(path))
        elif path.suffix.lower() in (".txt", ".md"):
            all_chunks.extend(_load_text_like(path))
        # .docx support could be added here via python-docx if needed
    return all_chunks


# ---------------------------------------------------------------------------
# RAG Pipeline (embedding + ChromaDB + retrieval)
# ---------------------------------------------------------------------------
class LocalRAGPipeline:
    def __init__(self, db_dir: Optional[str] = None):
        import chromadb

        self.db_dir = db_dir or settings.chroma_persist_dir
        self.chroma_client = chromadb.PersistentClient(path=self.db_dir)
        self.collection = self.chroma_client.get_or_create_collection(
            name=settings.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    # -- embeddings -----------------------------------------------------------
    def get_embedding(self, text: str) -> list:
        client = get_genai_client()

        def _call():
            return client.models.embed_content(model=settings.embedding_model, contents=text)

        response = call_with_backoff(_call, max_retries=settings.max_api_retries)
        return response.embeddings[0].values

    # -- ingestion --------------------------------------------------------------
    def ingest_document(self, doc_name: str, chunks: list):
        """Embeds and stores a list of LoadedChunk objects for one source document."""
        for idx, chunk in enumerate(chunks):
            embedding = self.get_embedding(chunk.text)
            chunk_id = f"{doc_name}_chunk_{idx}"
            metadata = {"source": chunk.source, "chunk_index": idx}
            if chunk.page is not None:
                metadata["page"] = chunk.page
            if chunk.section:
                metadata["section"] = chunk.section

            self.collection.add(
                ids=[chunk_id],
                embeddings=[embedding],
                metadatas=[metadata],
                documents=[chunk.text],
            )

    def ingest_all(self, data_dir: Optional[str] = None, force: bool = False) -> int:
        """Ingests every document in the knowledge base. Skips re-ingestion if
        the collection is already populated, unless force=True."""
        if not force and self.collection.count() > 0:
            return self.collection.count()

        if force and self.collection.count() > 0:
            self.chroma_client.delete_collection(settings.collection_name)
            self.collection = self.chroma_client.get_or_create_collection(
                name=settings.collection_name, metadata={"hnsw:space": "cosine"}
            )

        chunks_by_doc = {}
        for chunk in load_and_chunk_documents(data_dir):
            chunks_by_doc.setdefault(chunk.source, []).append(chunk)

        total = 0
        for doc_name, chunks in chunks_by_doc.items():
            self.ingest_document(doc_name, chunks)
            total += len(chunks)
        return total

    # -- retrieval ----------------------------------------------------------------
    def retrieve_context(self, query: str, top_k: Optional[int] = None) -> list:
        """Embeds the query and returns the top-k most similar chunks, each
        with its source, section/page, and a 0-1 similarity-derived score."""
        top_k = top_k or settings.top_k
        query_vector = self.get_embedding(query)

        results = self.collection.query(query_embeddings=[query_vector], n_results=top_k)

        retrieved = []
        if results and results.get("documents") and results["documents"][0]:
            for i in range(len(results["documents"][0])):
                meta = results["metadatas"][0][i]
                distance = results["distances"][0][i] if results.get("distances") else 0.0
                # Chroma's cosine "distance" is 1 - cosine_similarity; convert back.
                score = max(0.0, 1.0 - distance)
                retrieved.append(
                    {
                        "text": results["documents"][0][i],
                        "source": meta.get("source"),
                        "page": meta.get("page"),
                        "section": meta.get("section"),
                        "score": round(score, 4),
                    }
                )
        return retrieved
