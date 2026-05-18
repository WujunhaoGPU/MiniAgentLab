from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from miniagentlab import Agent, ToolRegistry, TraceLogger
from miniagentlab.document_tools import answer_question, chunk_document, index_chunks, load_document, retrieve_chunks
from miniagentlab.planner import Planner
from miniagentlab.schemas import Plan, PlannerContext, Step


class DemoDocumentQAPlanner(Planner):
    def __init__(self, document_path: Path, question: str) -> None:
        self.document_path = document_path
        self.question = question

    def plan(self, task: str, tools: ToolRegistry, context: PlannerContext | None = None) -> Plan:
        return Plan(
            goal=task,
            steps=[
                Step(
                    id="step_1",
                    description="Load the document.",
                    tool="load_document",
                    args={"path": str(self.document_path)},
                ),
                Step(
                    id="step_2",
                    description="Chunk the document.",
                    tool="chunk_document",
                    args={"document": "$memory.step_1", "chunk_size": 260, "overlap": 40},
                ),
                Step(
                    id="step_3",
                    description="Index chunks.",
                    tool="index_chunks",
                    args={"chunks": "$memory.step_2", "store_id": "miniagentlab_notes"},
                ),
                Step(
                    id="step_4",
                    description="Retrieve relevant chunks.",
                    tool="retrieve_chunks",
                    args={
                        "store_id": "miniagentlab_notes",
                        "query": self.question,
                        "top_k": 2,
                    },
                ),
                Step(
                    id="step_5",
                    description="Answer from retrieved evidence.",
                    tool="answer_question",
                    args={"question": self.question, "chunks": "$memory.step_4"},
                ),
            ],
        )


def build_agent(document_path: Path, question: str) -> Agent:
    registry = ToolRegistry()
    registry.register(load_document, name="load_document", description="Load a local .md or .txt document.")
    registry.register(chunk_document, name="chunk_document", description="Split a document into chunks.")
    registry.register(index_chunks, name="index_chunks", description="Index chunks in an in-memory vector store.")
    registry.register(retrieve_chunks, name="retrieve_chunks", description="Retrieve relevant chunks from a store.")
    registry.register(answer_question, name="answer_question", description="Answer using retrieved chunks.")
    return Agent(
        planner=DemoDocumentQAPlanner(document_path, question),
        tools=registry,
        trace_logger=TraceLogger(),
        max_retries=0,
    )


def main() -> None:
    document_path = Path("examples") / "docs" / "miniagentlab_notes.md"
    question = "What does Reflection do in MiniAgentLab?"
    agent = build_agent(document_path, question)
    result = agent.run(question)
    print(result.outputs["step_5"]["answer"])

    trace_path = agent.trace_logger.export_json(Path("traces") / "document_qa_trace.json")
    print(f"Trace saved to: {trace_path}")


if __name__ == "__main__":
    main()
