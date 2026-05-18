from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miniagentlab import Agent, ToolRegistry
from miniagentlab.document_tools import (
    answer_question,
    chunk_document,
    clear_vector_stores,
    index_chunks,
    load_document,
    retrieve_chunks,
)
from miniagentlab.planner import Planner
from miniagentlab.schemas import Plan, PlannerContext, Step


class StaticPlanner(Planner):
    def __init__(self, plan: Plan) -> None:
        self._plan = plan

    def plan(self, task: str, tools: ToolRegistry, context: PlannerContext | None = None) -> Plan:
        return self._plan


class DocumentQAAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_vector_stores()
        self.tempdir = tempfile.TemporaryDirectory()
        self.document_path = Path(self.tempdir.name) / "notes.md"
        self.document_path.write_text(
            (
                "MiniAgentLab keeps planning and tool execution separate.\n\n"
                "Reflection analyzes failures and can request a new plan with structured feedback.\n\n"
                "TraceLogger records plans, tool outputs, errors, and the final answer."
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        clear_vector_stores()
        self.tempdir.cleanup()

    def test_agent_runs_document_qa_loop(self) -> None:
        question = "What does Reflection do?"
        plan = Plan(
            goal=question,
            steps=[
                Step("step_1", "Load document.", "load_document", {"path": str(self.document_path)}),
                Step(
                    "step_2",
                    "Chunk document.",
                    "chunk_document",
                    {"document": "$memory.step_1", "chunk_size": 120, "overlap": 20},
                ),
                Step("step_3", "Index chunks.", "index_chunks", {"chunks": "$memory.step_2", "store_id": "qa_test"}),
                Step(
                    "step_4",
                    "Retrieve chunks.",
                    "retrieve_chunks",
                    {"store_id": "qa_test", "query": question, "top_k": 2},
                ),
                Step(
                    "step_5",
                    "Answer question.",
                    "answer_question",
                    {"question": question, "chunks": "$memory.step_4"},
                ),
            ],
        )
        agent = Agent(planner=StaticPlanner(plan), tools=self._build_registry(), max_retries=0)

        result = agent.run(question)

        self.assertTrue(result.success)
        self.assertIn("Reflection analyzes failures", result.outputs["step_5"]["answer"])
        self.assertEqual(result.outputs["step_3"]["store_id"], "qa_test")
        self.assertEqual(result.trace["steps"][4]["step"]["tool"], "answer_question")
        self.assertEqual(result.trace["steps"][4]["step"]["args"]["chunks"], result.outputs["step_4"])

    def _build_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register(load_document, name="load_document", description="Load a local document.")
        registry.register(chunk_document, name="chunk_document", description="Chunk a document.")
        registry.register(index_chunks, name="index_chunks", description="Index document chunks.")
        registry.register(retrieve_chunks, name="retrieve_chunks", description="Retrieve relevant chunks.")
        registry.register(answer_question, name="answer_question", description="Answer from chunks.")
        return registry


if __name__ == "__main__":
    unittest.main()
