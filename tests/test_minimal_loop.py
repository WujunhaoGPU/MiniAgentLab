from __future__ import annotations

import unittest

from miniagentlab import Agent, RuleBasedPlanner, ToolRegistry, TraceLogger
from miniagentlab.builtin_tools import calculator
from miniagentlab.planner import Planner
from miniagentlab.schemas import Plan, Step


class StaticPlanner(Planner):
    def __init__(self, plan: Plan) -> None:
        self._plan = plan

    def plan(self, task: str, tools: ToolRegistry) -> Plan:
        return self._plan


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

    def test_unknown_tool_returns_standard_error(self) -> None:
        registry = ToolRegistry()

        result = registry.call("missing_tool")

        self.assertFalse(result.success)
        self.assertEqual(result.error, "Unknown tool: missing_tool")

    def test_tool_parameter_error_returns_standard_error(self) -> None:
        registry = ToolRegistry()
        registry.register(calculator, name="calculator")

        result = registry.call("calculator")

        self.assertFalse(result.success)
        self.assertIn("TypeError", result.error or "")
        self.assertIn("expression", result.error or "")

    def test_calculator_rejects_unsupported_expression(self) -> None:
        registry = ToolRegistry()
        registry.register(calculator, name="calculator")

        result = registry.call("calculator", expression="2 + unknown")

        self.assertFalse(result.success)
        self.assertIn("ValueError", result.error or "")
        self.assertIn("Unsupported expression node", result.error or "")

    def test_calculator_reports_division_by_zero(self) -> None:
        registry = ToolRegistry()
        registry.register(calculator, name="calculator")

        result = registry.call("calculator", expression="1 / 0")

        self.assertFalse(result.success)
        self.assertIn("ZeroDivisionError", result.error or "")

    def test_agent_runs_calculator_loop_and_records_trace(self) -> None:
        registry = ToolRegistry()
        registry.register(calculator, name="calculator")
        agent = Agent(
            planner=RuleBasedPlanner(),
            tools=registry,
            trace_logger=TraceLogger(),
            max_retries=1,
        )

        result = agent.run("calculate 123 * 456")

        self.assertTrue(result.success)
        self.assertIn("56088", result.final_answer)
        self.assertEqual(result.outputs["step_1"], "56088")
        self.assertTrue(result.trace["run_id"].startswith("run_"))
        self.assertEqual(result.trace["steps"][0]["step"]["tool"], "calculator")

    def test_agent_fails_when_plan_exceeds_max_steps(self) -> None:
        registry = ToolRegistry()
        registry.register(calculator, name="calculator")
        plan = Plan(
            goal="too many steps",
            steps=[
                Step(
                    id="step_1",
                    description="First calculation.",
                    tool="calculator",
                    args={"expression": "1 + 1"},
                ),
                Step(
                    id="step_2",
                    description="Second calculation.",
                    tool="calculator",
                    args={"expression": "2 + 2"},
                ),
            ],
        )
        agent = Agent(
            planner=StaticPlanner(plan),
            tools=registry,
            trace_logger=TraceLogger(),
            max_steps=1,
        )

        result = agent.run("run a plan with too many steps")

        self.assertFalse(result.success)
        self.assertIn("exceeding max_steps=1", result.final_answer)
        self.assertEqual(result.outputs, {})
        self.assertEqual(result.trace["steps"], [])

    def test_executor_rejects_invalid_max_steps(self) -> None:
        registry = ToolRegistry()
        registry.register(calculator, name="calculator")

        with self.assertRaises(ValueError):
            Agent(
                planner=RuleBasedPlanner(),
                tools=registry,
                trace_logger=TraceLogger(),
                max_steps=0,
            )


if __name__ == "__main__":
    unittest.main()
