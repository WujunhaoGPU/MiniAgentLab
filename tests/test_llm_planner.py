from __future__ import annotations

import unittest

from miniagentlab import Agent, ConversationMemory, LLMPlanner, PlannerContext, ToolRegistry, TraceLogger, parse_operation_hints
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

    def test_llm_planner_prompt_includes_recent_conversation(self) -> None:
        llm = FakeLLM(
            [
                """
                {
                  "goal": "continue from conversation",
                  "steps": [
                    {
                      "id": "step_1",
                      "description": "Repeat previous result.",
                      "tool": "calculator",
                      "args": {"expression": "21"}
                    }
                  ]
                }
                """
            ]
        )
        registry = ToolRegistry()
        registry.register(calculator, name="calculator")
        planner = LLMPlanner(llm=llm)
        context = PlannerContext(
            conversation=[
                {"role": "user", "content": "calculate 3 * 7", "metadata": {}},
                {"role": "assistant", "content": "Result: 21", "metadata": {"success": True}},
            ]
        )

        planner.plan("explain the previous result", registry, context=context)

        self.assertIn("Recent conversation before this task", llm.prompts[0])
        self.assertIn("Resolved prior results from recent conversation", llm.prompts[0])
        self.assertIn("calculate 3 * 7", llm.prompts[0])
        self.assertIn("Result: 21", llm.prompts[0])
        self.assertIn('"value": "21"', llm.prompts[0])

    def test_llm_planner_uses_operation_hint_fast_path(self) -> None:
        llm = FakeLLM([])
        registry = ToolRegistry()
        registry.register(calculator, name="calculator")
        planner = LLMPlanner(llm=llm)
        context = PlannerContext(
            conversation=[
                {"role": "assistant", "content": "Result: 21", "metadata": {"success": True}},
            ],
            operation_hints=parse_operation_hints("add 5 to the previous result"),
        )

        plan = planner.plan("add 5 to the previous result", registry, context=context)

        self.assertEqual(plan.steps[0].tool, "calculator")
        self.assertEqual(plan.steps[0].args["expression"], "21 + 5")
        self.assertEqual(llm.prompts, [])

    def test_agent_passes_prior_conversation_to_llm_planner(self) -> None:
        llm = FakeLLM(
            [
                """
                {
                  "goal": "first calculation",
                  "steps": [
                    {
                      "id": "step_1",
                      "description": "Calculate the first expression.",
                      "tool": "calculator",
                      "args": {"expression": "3 * 7"}
                    }
                  ]
                }
                """,
                """
                {
                  "goal": "repeat prior result",
                  "steps": [
                    {
                      "id": "step_1",
                      "description": "Repeat the previous result.",
                      "tool": "calculator",
                      "args": {"expression": "21"}
                    }
                  ]
                }
                """,
            ]
        )
        registry = ToolRegistry()
        registry.register(calculator, name="calculator")
        conversation = ConversationMemory()
        agent = Agent(
            planner=LLMPlanner(llm=llm),
            tools=registry,
            trace_logger=TraceLogger(),
            conversation_memory=conversation,
        )

        first = agent.run("calculate 3 * 7")
        second = agent.run("explain the previous result")

        self.assertEqual(first.outputs["step_1"], "21")
        self.assertEqual(second.outputs["step_1"], "21")
        self.assertIn("calculate 3 * 7", llm.prompts[1])
        self.assertIn("Result: 21", llm.prompts[1])
        self.assertIn("Parsed operation hints", llm.prompts[1])
        conversation_block = llm.prompts[1].split("Recent conversation before this task:")[1].split(
            "Resolved prior results from recent conversation:"
        )[0]
        self.assertNotIn("explain the previous result", conversation_block)


if __name__ == "__main__":
    unittest.main()
