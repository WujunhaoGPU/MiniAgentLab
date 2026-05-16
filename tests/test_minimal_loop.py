from __future__ import annotations

import unittest

from miniagentlab import Agent, RuleBasedPlanner, ToolRegistry, TraceLogger
from miniagentlab.builtin_tools import calculator


class MinimalLoopTests(unittest.TestCase):
    def test_tool_registry_calls_registered_tool(self) -> None:
        registry = ToolRegistry()
        registry.register(calculator, name="calculator")

        result = registry.call("calculator", expression="2 + 3 * 4")

        self.assertTrue(result.success)
        self.assertEqual(result.output, "14")

    def test_tool_registry_rejects_duplicate_names(self) -> None:
        registry = ToolRegistry()
        registry.register(calculator, name="calculator")

        with self.assertRaises(ValueError):
            registry.register(calculator, name="calculator")

    def test_agent_runs_calculator_loop_and_records_trace(self) -> None:
        registry = ToolRegistry()
        registry.register(calculator, name="calculator")
        agent = Agent(
            planner=RuleBasedPlanner(),
            tools=registry,
            trace_logger=TraceLogger(),
            max_retries=1,
        )

        result = agent.run("计算 123 * 456")

        self.assertTrue(result.success)
        self.assertIn("56088", result.final_answer)
        self.assertEqual(result.outputs["step_1"], "56088")
        self.assertEqual(result.trace["steps"][0]["step"]["tool"], "calculator")


if __name__ == "__main__":
    unittest.main()
