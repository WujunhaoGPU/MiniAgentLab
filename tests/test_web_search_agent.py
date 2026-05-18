from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from miniagentlab import Agent, ToolRegistry
from miniagentlab.planner import Planner
from miniagentlab.schemas import Plan, PlannerContext, Step
from miniagentlab.web_tools import extract_text, fetch_page, search_web, summarize_text


class StaticPlanner(Planner):
    def __init__(self, plan: Plan) -> None:
        self._plan = plan

    def plan(self, task: str, tools: ToolRegistry, context: PlannerContext | None = None) -> Plan:
        return self._plan


class WebSearchAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.page_path = Path(self.tempdir.name) / "reflection.html"
        self.search_path = Path(self.tempdir.name) / "search.html"
        self.page_path.write_text(
            """
            <html>
              <head><title>Reflection Notes</title></head>
              <body>
                <p>Reflection analyzes failed plans and tool execution errors.</p>
                <p>Memory stores step outputs.</p>
              </body>
            </html>
            """,
            encoding="utf-8",
        )
        self.search_path.write_text(
            f'<a class="result__a" href="{self.page_path.as_uri()}">Reflection Notes</a>',
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_agent_runs_web_search_loop(self) -> None:
        query = "reflection failed plans"
        plan = Plan(
            goal=query,
            steps=[
                Step("step_1", "Search web.", "search_web", {"query": query, "search_url": self.search_path.as_uri()}),
                Step("step_2", "Fetch first result.", "fetch_page", {"url": "$memory.step_1.0.url"}),
                Step("step_3", "Extract text.", "extract_text", {"page": "$memory.step_2"}),
                Step("step_4", "Summarize text.", "summarize_text", {"text": "$memory.step_3", "query": query}),
            ],
        )
        agent = Agent(planner=StaticPlanner(plan), tools=self._build_registry(), max_retries=0)

        result = agent.run(query)

        self.assertTrue(result.success)
        self.assertIn("Reflection analyzes failed plans", result.outputs["step_4"]["summary"])
        self.assertEqual(result.trace["steps"][1]["step"]["args"]["url"], self.page_path.as_uri())

    def _build_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register(search_web, name="search_web", description="Search web pages.")
        registry.register(fetch_page, name="fetch_page", description="Fetch an HTML page.")
        registry.register(extract_text, name="extract_text", description="Extract readable text.")
        registry.register(summarize_text, name="summarize_text", description="Summarize extracted text.")
        return registry


if __name__ == "__main__":
    unittest.main()
