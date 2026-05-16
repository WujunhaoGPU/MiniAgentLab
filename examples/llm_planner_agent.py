from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from miniagentlab import Agent, LLMPlanner, OpenAICompatibleLLM, ToolRegistry, TraceLogger
from miniagentlab.builtin_tools import calculator


def build_agent() -> Agent:
    registry = ToolRegistry()
    registry.register(calculator, name="calculator", description="Evaluate a basic arithmetic expression.")
    llm = OpenAICompatibleLLM.from_env()
    return Agent(
        planner=LLMPlanner(llm=llm, max_retries=1),
        tools=registry,
        trace_logger=TraceLogger(),
        max_retries=1,
        max_steps=5,
    )


def main() -> None:
    agent = build_agent()
    result = agent.run("请计算 123 * 456，并只使用 calculator 工具。")
    print(result.final_answer)
    trace_path = agent.trace_logger.export_json(Path("traces") / "llm_planner_trace.json")
    print(f"Trace saved to: {trace_path}")


if __name__ == "__main__":
    main()
