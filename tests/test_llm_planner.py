from __future__ import annotations

import unittest

from miniagentlab import Agent, LLMPlanner, ToolRegistry, TraceLogger
from miniagentlab.builtin_tools import calculator


class FakeLLM:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self.responses:
            raise AssertionError("FakeLLM has no remaining responses")
        return self.responses.pop(0)


class LLMPlannerTests(unittest.TestCase):
    def test_llm_planner_runs_agent_from_valid_json(self) -> None:
        llm = FakeLLM(
            [
                """
                {
                  "goal": "calculate an expression",
                  "steps": [
                    {
                      "id": "step_1",
                      "description": "Evaluate the expression.",
                      "tool": "calculator",
                      "args": {"expression": "123 * 456"}
                    }
                  ]
                }
                """
            ]
        )
        registry = ToolRegistry()
        registry.register(calculator, name="calculator")
        agent = Agent(
            planner=LLMPlanner(llm=llm),
            tools=registry,
            trace_logger=TraceLogger(),
        )

        result = agent.run("calculate 123 * 456")

        self.assertTrue(result.success)
        self.assertEqual(result.outputs["step_1"], "56088")
        self.assertIn("Registered tools", llm.prompts[0])

    def test_llm_planner_repairs_invalid_json_response(self) -> None:
        llm = FakeLLM(
            [
                "not json",
                """
                {
                  "goal": "calculate an expression",
                  "steps": [
                    {
                      "id": "step_1",
                      "description": "Evaluate the expression.",
                      "tool": "calculator",
                      "args": {"expression": "2 + 2"}
                    }
                  ]
                }
                """,
            ]
        )
        registry = ToolRegistry()
        registry.register(calculator, name="calculator")
        planner = LLMPlanner(llm=llm, max_retries=1)

        plan = planner.plan("calculate 2 + 2", registry)

        self.assertEqual(plan.steps[0].args["expression"], "2 + 2")
        self.assertEqual(len(llm.prompts), 2)
        self.assertIn("Validation error", llm.prompts[1])

    def test_llm_planner_rejects_unknown_tool(self) -> None:
        llm = FakeLLM(
            [
                """
                {
                  "goal": "use an unavailable tool",
                  "steps": [
                    {
                      "id": "step_1",
                      "description": "Try a missing tool.",
                      "tool": "web_search",
                      "args": {"query": "MiniAgentLab"}
                    }
                  ]
                }
                """
            ]
        )
        registry = ToolRegistry()
        registry.register(calculator, name="calculator")
        planner = LLMPlanner(llm=llm, max_retries=0)

        with self.assertRaisesRegex(ValueError, "unknown tool"):
            planner.plan("search MiniAgentLab", registry)


if __name__ == "__main__":
    unittest.main()
