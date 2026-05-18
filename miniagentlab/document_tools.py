from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path
from typing import Any
from uuid import uuid4


_SUPPORTED_SUFFIXES = {".md", ".txt"}
_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_SENTENCE_PATTERN = re.compile(r"[^.!?\n\u3002\uff01\uff1f]+[.!?\u3002\uff01\uff1f]?")
_WHAT_DOES_PATTERN = re.compile(r"\bwhat\s+does\s+(.+?)\s+do\b", re.IGNORECASE)
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "does",
    "do",
    "for",
    "in",
    "is",
    "of",
    "the",
    "to",
    "what",
}
_VECTOR_STORES: dict[str, dict[str, Any]] = {}


def load_document(path: str, encoding: str = "utf-8") -> dict[str, Any]:
    """Load a local Markdown or text document."""
    document_path = Path(path).expanduser()
    if not document_path.exists():
        raise FileNotFoundError(f"Document not found: {path}")
    if not document_path.is_file():
        raise ValueError(f"Document path is not a file: {path}")
    if document_path.suffix.lower() not in _SUPPORTED_SUFFIXES:
        raise ValueError(f"Unsupported document type: {document_path.suffix}")

    text = document_path.read_text(encoding=encoding)
    return {
        "path": str(document_path),
        "text": text,
        "metadata": {
            "name": document_path.name,
            "suffix": document_path.suffix.lower(),
            "encoding": encoding,
        },
    }


def chunk_document(document: dict[str, Any] | str, chunk_size: int = 500, overlap: int = 80) -> list[dict[str, Any]]:
    """Split a document into heading- and paragraph-aware chunks."""
    if chunk_size < 1:
        raise ValueError("chunk_size must be at least 1")
    if overlap < 0:
        raise ValueError("overlap must not be negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    text, metadata = _document_text_and_metadata(document)
    text = text.strip()
    if not text:
        return []

    blocks = _split_document_blocks(text)
    chunks: list[dict[str, Any]] = []
    chunk_index = 1

    for block_index, block in enumerate(blocks, start=1):
        block_text = block["text"]
        if not block_text:
            continue
        parts = _split_long_text(block_text, chunk_size=chunk_size, overlap=overlap)
        for part_index, part in enumerate(parts, start=1):
            chunk_text = _chunk_text_with_heading(str(block.get("heading") or ""), part)
            chunks.append(
                {
                    "id": f"chunk_{chunk_index}",
                    "text": chunk_text,
                    "metadata": {
                        **metadata,
                        "heading": block.get("heading"),
                        "heading_level": block.get("heading_level"),
                        "block_index": block_index,
                        "part_index": part_index,
                    },
                }
            )
            chunk_index += 1

    return chunks


def index_chunks(chunks: list[dict[str, Any]], store_id: str | None = None) -> dict[str, Any]:
    """Index chunks in a lightweight in-memory vector store."""
    if not chunks:
        raise ValueError("chunks must not be empty")

    resolved_store_id = store_id or f"store_{uuid4().hex}"
    indexed_chunks = []
    vocabulary: set[str] = set()

    for chunk in chunks:
        text = str(chunk.get("text", ""))
        tokens = _tokenize(text)
        vector = Counter(tokens)
        vocabulary.update(vector)
        indexed_chunks.append(
            {
                "id": str(chunk.get("id", f"chunk_{len(indexed_chunks) + 1}")),
                "text": text,
                "metadata": dict(chunk.get("metadata", {})),
                "vector": vector,
            }
        )

    _VECTOR_STORES[resolved_store_id] = {
        "chunks": indexed_chunks,
        "vocabulary": sorted(vocabulary),
    }
    return {
        "store_id": resolved_store_id,
        "chunk_count": len(indexed_chunks),
        "vocabulary_size": len(vocabulary),
    }


def retrieve_chunks(store_id: str, query: str, top_k: int = 3) -> list[dict[str, Any]]:
    """Retrieve the most relevant chunks from an in-memory store."""
    if top_k < 1:
        raise ValueError("top_k must be at least 1")

    store = _VECTOR_STORES.get(store_id)
    if store is None:
        raise ValueError(f"Vector store not found: {store_id}")

    query_vector = Counter(_tokenize(query))
    if not query_vector:
        return []

    scored_chunks = []
    query_terms = _meaningful_terms(query)
    for chunk in store["chunks"]:
        score, score_details = _score_chunk(query, query_terms, query_vector, chunk)
        if score <= 0:
            continue
        scored_chunks.append(
            {
                "id": chunk["id"],
                "text": chunk["text"],
                "metadata": chunk["metadata"],
                "score": round(score, 6),
                "score_details": score_details,
            }
        )

    return sorted(scored_chunks, key=lambda item: item["score"], reverse=True)[:top_k]


def answer_question(question: str, chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """Create a concise evidence-based answer from retrieved chunks."""
    if not chunks:
        return {
            "answer": "I could not find relevant evidence in the retrieved document chunks.",
            "sources": [],
        }

    query_terms = _focus_terms(question) or _meaningful_terms(question)
    ranked_sentences: list[tuple[float, str, str]] = []
    sources_by_id: dict[str, dict[str, Any]] = {}

    for chunk in chunks:
        text = str(chunk.get("text", ""))
        chunk_id = str(chunk.get("id", ""))
        chunk_score = float(chunk.get("score") or 0)
        ranked_sentences.extend(_rank_sentences(text, query_terms, chunk_id, chunk_score))

        sources_by_id[chunk_id] = {
            "id": chunk_id,
            "score": chunk.get("score"),
            "metadata": dict(chunk.get("metadata", {})),
        }

    ranked_sentences.sort(key=lambda item: item[0], reverse=True)
    selected_ranked_sentences = _select_top_sentences(ranked_sentences)
    selected_sentences = [sentence for _, sentence, _ in selected_ranked_sentences]
    if not selected_sentences:
        selected_sentences = [str(chunks[0].get("text", "")).strip()]

    selected_source_ids = [chunk_id for _, _, chunk_id in selected_ranked_sentences]
    if not selected_source_ids:
        selected_source_ids = list(sources_by_id)

    answer = " ".join(_dedupe_preserve_order(selected_sentences))[:1200].strip()
    return {
        "answer": answer,
        "sources": [sources_by_id[source_id] for source_id in _dedupe_preserve_order(selected_source_ids)],
    }


def clear_vector_stores() -> None:
    """Clear in-memory vector stores. Primarily useful for tests."""
    _VECTOR_STORES.clear()


def _document_text_and_metadata(document: dict[str, Any] | str) -> tuple[str, dict[str, Any]]:
    if isinstance(document, str):
        return document, {}
    return str(document.get("text", "")), dict(document.get("metadata", {}))


def _tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in _TOKEN_PATTERN.finditer(text)]


def _cosine_similarity(left: Counter[str], right: Counter[str]) -> float:
    shared_terms = set(left) & set(right)
    if not shared_terms:
        return 0.0

    dot_product = sum(left[term] * right[term] for term in shared_terms)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot_product / (left_norm * right_norm)


def _split_document_blocks(text: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    current_heading: str | None = None
    current_heading_level: int | None = None
    paragraph_lines: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph_lines
        paragraph = " ".join(line.strip() for line in paragraph_lines if line.strip()).strip()
        if paragraph:
            blocks.append(
                {
                    "text": paragraph,
                    "heading": current_heading,
                    "heading_level": current_heading_level,
                }
            )
        paragraph_lines = []

    for line in text.splitlines():
        heading_match = _HEADING_PATTERN.match(line)
        if heading_match is not None:
            flush_paragraph()
            current_heading = heading_match.group(2).strip()
            current_heading_level = len(heading_match.group(1))
            continue

        if not line.strip():
            flush_paragraph()
            continue

        paragraph_lines.append(line)

    flush_paragraph()
    if blocks:
        return blocks
    return [{"text": text, "heading": None, "heading_level": None}]


def _split_long_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text.strip()]

    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        part = text[start:end].strip()
        if part:
            parts.append(part)
        if end == len(text):
            break
        start = end - overlap
    return parts


def _chunk_text_with_heading(heading: str, text: str) -> str:
    if heading and heading not in text:
        return f"{heading}\n\n{text}"
    return text


def _score_chunk(
    query: str,
    query_terms: set[str],
    query_vector: Counter[str],
    chunk: dict[str, Any],
) -> tuple[float, dict[str, float]]:
    text = str(chunk.get("text", ""))
    metadata = dict(chunk.get("metadata", {}))
    text_terms = set(_tokenize(text))
    heading_terms = set(_tokenize(str(metadata.get("heading") or "")))

    cosine = _cosine_similarity(query_vector, chunk["vector"])
    overlap = len(query_terms & text_terms) / max(len(query_terms), 1)
    heading_overlap = len(query_terms & heading_terms) / max(len(query_terms), 1)
    phrase = 1.0 if _normalized_query(query) and _normalized_query(query) in text.lower() else 0.0

    score = cosine + (0.2 * overlap) + (0.25 * heading_overlap) + (0.3 * phrase)
    return score, {
        "cosine": round(cosine, 6),
        "keyword_overlap": round(overlap, 6),
        "heading_overlap": round(heading_overlap, 6),
        "exact_phrase": phrase,
    }


def _rank_sentences(text: str, query_terms: set[str], chunk_id: str, chunk_score: float) -> list[tuple[float, str, str]]:
    matches: list[tuple[float, str]] = []
    for sentence_match in _SENTENCE_PATTERN.finditer(text):
        sentence = sentence_match.group(0).strip()
        if not sentence:
            continue
        sentence_terms = set(_tokenize(sentence))
        if len(sentence_terms) < 2:
            continue
        shared_terms = sentence_terms & query_terms
        if len(shared_terms) < 2 and len(sentence_terms) <= 3:
            continue
        if shared_terms:
            score = (len(shared_terms) / math.sqrt(max(len(sentence_terms), 1))) + (0.15 * chunk_score)
            matches.append((score, sentence))
    matches.sort(key=lambda item: item[0], reverse=True)
    return [(score, sentence, chunk_id) for score, sentence in matches[:3]]


def _meaningful_terms(text: str) -> set[str]:
    terms = set(_tokenize(text))
    filtered = {term for term in terms if term not in _STOPWORDS}
    return filtered or terms


def _focus_terms(question: str) -> set[str]:
    match = _WHAT_DOES_PATTERN.search(question)
    if match is None:
        return set()
    return _meaningful_terms(match.group(1))


def _select_top_sentences(ranked_sentences: list[tuple[float, str, str]]) -> list[tuple[float, str, str]]:
    if not ranked_sentences:
        return []
    best_score = ranked_sentences[0][0]
    selected = [item for item in ranked_sentences if item[0] >= best_score * 0.9]
    return selected[:3]


def _normalized_query(query: str) -> str:
    return " ".join(_tokenize(query))


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped
