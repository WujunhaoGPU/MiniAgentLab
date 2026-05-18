from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from miniagentlab import Agent, ToolRegistry, TraceLogger
from miniagentlab.planner import Planner
from miniagentlab.schemas import Plan, PlannerContext, Step
from miniagentlab.web_tools import extract_text, fetch_page, search_web, summarize_text


class DemoWebSearchPlanner(Planner):
    def __init__(self, search_url: str, query: str) -> None:
        self.search_url = search_url
        self.query = query

    def plan(self, task: str, tools: ToolRegistry, context: PlannerContext | None = None) -> Plan:
        return Plan(
            goal=task,
            steps=[
                Step(
                    id="step_1",
                    description="Search for relevant pages.",
                    tool="search_web",
                    args={"query": self.query, "search_url": self.search_url},
                ),
                Step(
                    id="step_2",
                    description="Fetch the first search result.",
                    tool="fetch_page",
                    args={"url": "$memory.step_1.0.url"},
                ),
                Step(
                    id="step_3",
                    description="Extract readable text.",
                    tool="extract_text",
                    args={"page": "$memory.step_2"},
                ),
                Step(
                    id="step_4",
                    description="Summarize the relevant page.",
                    tool="summarize_text",
                    args={"text": "$memory.step_3", "query": self.query, "max_sentences": 2},
                ),
            ],
        )


def prepare_demo_pages() -> tuple[str, str]:
    demo_dir = (Path("traces") / "web_demo").resolve()
    demo_dir.mkdir(parents=True, exist_ok=True)
    page_path = demo_dir / "reflection.html"
    search_path = demo_dir / "search.html"
    page_path.write_text(
        """
        <html>
          <head><title>MiniAgentLab Reflection</title></head>
          <body>
            <h1>Reflection</h1>
            <p>Reflection analyzes failed plans and tool execution errors.</p>
            <p>It can request a new plan with structured feedback.</p>
          </body>
        </html>
        """,
        encoding="utf-8",
    )
    search_path.write_text(
        f'<a class="result__a" href="{page_path.as_uri()}">MiniAgentLab Reflection</a>',
        encoding="utf-8",
    )
    return search_path.as_uri(), "What does Reflection do?"


def build_agent(search_url: str, query: str) -> Agent:
    registry = ToolRegistry()
    registry.register(search_web, name="search_web", description="Search web pages.")
    registry.register(fetch_page, name="fetch_page", description="Fetch an HTML page.")
    registry.register(extract_text, name="extract_text", description="Extract readable text from HTML.")
    registry.register(summarize_text, name="summarize_text", description="Summarize text for a query.")
    return Agent(
        planner=DemoWebSearchPlanner(search_url, query),
        tools=registry,
        trace_logger=TraceLogger(),
        max_retries=0,
    )


def main() -> None:
    search_url, query = prepare_demo_pages()
    agent = build_agent(search_url, query)
    result = agent.run(query)
    print(result.outputs["step_4"]["summary"])
    trace_path = agent.trace_logger.export_json(Path("traces") / "web_search_trace.json")
    print(f"Trace saved to: {trace_path}")


if __name__ == "__main__":
    main()
