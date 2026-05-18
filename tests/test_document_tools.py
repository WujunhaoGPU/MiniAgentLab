from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miniagentlab.document_tools import (
    answer_question,
    chunk_document,
    clear_vector_stores,
    index_chunks,
    load_document,
    retrieve_chunks,
)


class DocumentToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_vector_stores()
        self.tempdir = tempfile.TemporaryDirectory()
        self.document_path = Path(self.tempdir.name) / "notes.md"
        self.document_path.write_text(
            (
                "MiniAgentLab separates planning, tools, memory, reflection, and trace logging.\n\n"
                "Reflection analyzes failures and can ask the planner to create a repaired plan.\n\n"
                "ShortTermMemory stores step outputs for one agent run."
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        clear_vector_stores()
        self.tempdir.cleanup()

    def test_load_document_reads_markdown(self) -> None:
        document = load_document(str(self.document_path))

        self.assertEqual(document["metadata"]["name"], "notes.md")
        self.assertIn("MiniAgentLab separates", document["text"])

    def test_chunk_document_creates_overlapping_chunks(self) -> None:
        document = load_document(str(self.document_path))
        chunks = chunk_document(document, chunk_size=60, overlap=10)

        self.assertGreater(len(chunks), 1)
        self.assertEqual(chunks[0]["id"], "chunk_1")
        self.assertEqual(chunks[0]["metadata"]["name"], "notes.md")

    def test_chunk_document_preserves_markdown_headings(self) -> None:
        self.document_path.write_text(
            (
                "# Reflection\n\n"
                "Reflection analyzes failed plans and tool errors.\n\n"
                "# Memory\n\n"
                "Memory stores intermediate step outputs."
            ),
            encoding="utf-8",
        )

        chunks = chunk_document(load_document(str(self.document_path)), chunk_size=120, overlap=20)

        self.assertEqual(chunks[0]["metadata"]["heading"], "Reflection")
        self.assertEqual(chunks[0]["metadata"]["heading_level"], 1)
        self.assertEqual(chunks[1]["metadata"]["heading"], "Memory")
        self.assertIn("Reflection", chunks[0]["text"])

    def test_index_and_retrieve_chunks(self) -> None:
        document = load_document(str(self.document_path))
        chunks = chunk_document(document, chunk_size=120, overlap=20)
        index = index_chunks(chunks, store_id="notes")

        results = retrieve_chunks(index["store_id"], "reflection failures planner", top_k=2)

        self.assertEqual(index["store_id"], "notes")
        self.assertGreaterEqual(len(results), 1)
        self.assertIn("Reflection analyzes failures", results[0]["text"])
        self.assertGreater(results[0]["score"], 0)

    def test_retrieve_chunks_uses_heading_and_keyword_bonus(self) -> None:
        chunks = [
            {
                "id": "chunk_1",
                "text": "Reflection\n\nIt analyzes failures and planner feedback.",
                "metadata": {"heading": "Reflection"},
            },
            {
                "id": "chunk_2",
                "text": "Memory\n\nIt stores step outputs and intermediate values.",
                "metadata": {"heading": "Memory"},
            },
        ]
        index_chunks(chunks, store_id="quality")

        results = retrieve_chunks("quality", "How does reflection handle failures?", top_k=2)

        self.assertEqual(results[0]["id"], "chunk_1")
        self.assertGreater(results[0]["score_details"]["heading_overlap"], 0)

    def test_answer_question_uses_retrieved_evidence(self) -> None:
        chunks = [
            {
                "id": "chunk_1",
                "text": "Reflection analyzes failures and asks the planner to repair plans.",
                "metadata": {"name": "notes.md"},
                "score": 0.9,
            }
        ]

        answer = answer_question("What does Reflection do?", chunks)

        self.assertIn("Reflection analyzes failures", answer["answer"])
        self.assertEqual(answer["sources"][0]["id"], "chunk_1")

    def test_answer_question_ranks_sentences_instead_of_returning_whole_chunk(self) -> None:
        chunks = [
            {
                "id": "chunk_1",
                "text": (
                    "Memory stores temporary values. "
                    "Reflection analyzes failures and asks the planner for a new plan. "
                    "TraceLogger records execution details."
                ),
                "metadata": {"name": "notes.md"},
                "score": 0.9,
            }
        ]

        answer = answer_question("What does Reflection do?", chunks)

        self.assertIn("Reflection analyzes failures", answer["answer"])
        self.assertNotIn("Memory stores temporary values", answer["answer"])

    def test_retrieve_missing_store_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "Vector store not found"):
            retrieve_chunks("missing", "reflection")

    def test_rejects_unsupported_document_type(self) -> None:
        pdf_path = Path(self.tempdir.name) / "notes.pdf"
        pdf_path.write_text("fake pdf", encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "Unsupported document type"):
            load_document(str(pdf_path))


if __name__ == "__main__":
    unittest.main()
