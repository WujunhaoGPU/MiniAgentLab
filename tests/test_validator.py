from __future__ import annotations

import unittest

from miniagentlab import Agent, ConversationMemory, PlanValidator, ToolRegistry
from miniagentlab.builtin_tools import calculator
from miniagentlab.planner import Planner
from miniagentlab.schemas import OperationHint, Plan, PlannerContext, Step


class StaticPlanner(Planner):
    def __init__(self, plan: Plan) -> None:
        self._plan = plan

    def plan(self, task: str, tools: ToolRegistry, context: PlannerContext | None = None) -> Plan:
        return self._plan


class PlanValidatorTests(unittest.TestCase):
    def test_accepts_valid_known_tool_plan(self) -> None:
        registry = ToolRegistry()
        registry.register(calculator, name="calculator")
        plan = Plan(
            goal="calculate",
            steps=[
                Step(
                    id="step_1",
                    description="Calculate expression.",
                    tool="calculator",
                    args={"expression": "2 + 2"},
                )
            ],
        )

        result = PlanValidator().validate(plan, registry, max_steps=1)

        self.assertTrue(result.valid)
        self.assertEqual(result.issues, [])

    def test_rejects_unknown_tool(self) -> None:
        registry = ToolRegistry()
        plan = Plan(
            goal="search",
            steps=[
                Step(
                    id="step_1",
                    description="Use missing tool.",
                    tool="web_search",
                    args={"query": "MiniAgentLab"},
                )
            ],
        )

        result = PlanValidator().validate(plan, registry)

        self.assertFalse(result.valid)
        self.assertEqual(result.issues[0].code, "unknown_tool")
        self.assertEqual(result.issues[0].step_id, "step_1")

    def test_rejects_plan_exceeding_max_steps(self) -> None:
        registry = ToolRegistry()
        registry.register(calculator, name="calculator")
        plan = Plan(
            goal="too many steps",
            steps=[
                Step("step_1", "First calculation.", "calculator", {"expression": "1 + 1"}),
                Step("step_2", "Second calculation.", "calculator", {"expression": "2 + 2"}),
            ],
        )

        result = PlanValidator().validate(plan, registry, max_steps=1)

        self.assertFalse(result.valid)
        self.assertEqual(result.issues[0].code, "too_many_steps")
        self.assertIn("max_steps=1", result.issues[0].message)

    def test_rejects_operation_hint_conflict(self) -> None:
        registry = ToolRegistry()
        registry.register(calculator, name="calculator")
        plan = Plan(
            goal="subtract from previous result",
            steps=[
                Step(
                    id="step_1",
                    description="Wrong operation.",
                    tool="calculator",
                    args={"expression": "100 * 12"},
                )
            ],
        )
        context = PlannerContext(
            conversation=[
                {"role": "assistant", "content": "Done\nResult: 100", "metadata": {"success": True}},
            ],
            operation_hints=[
                OperationHint(
                    intent="arithmetic_transform",
                    reference="previous_result",
                    operator="-",
                    operand="12",
                    raw_text="subtract 12 from it",
                )
            ],
        )

        result = PlanValidator().validate(plan, registry, context=context)

        self.assertFalse(result.valid)
        self.assertEqual(result.issues[0].code, "operation_hint_conflict")
        self.assertEqual(result.issues[0].metadata["expected_expression"], "100 - 12")
        self.assertEqual(result.issues[0].metadata["actual_expression"], "100 * 12")

    def test_agent_repairs_high_confidence_validation_failure(self) -> None:
        registry = ToolRegistry()
        registry.register(calculator, name="calculator")
        conversation = ConversationMemory()
        conversation.add("assistant", "Done\nResult: 100", success=True, run_id="run_previous")
        plan = Plan(
            goal="subtract from previous result",
            steps=[
                Step(
                    id="step_1",
                    description="Wrong operation.",
                    tool="calculator",
                    args={"expression": "100 * 12"},
                )
            ],
        )
        agent = Agent(
            planner=StaticPlanner(plan),
            tools=registry,
            conversation_memory=conversation,
        )

        result = agent.run("subtract 12 from it")

        self.assertTrue(result.success)
        self.assertEqual(result.outputs["step_1"], "88")
        self.assertTrue(result.validation["valid"])
        self.assertEqual(result.reflections[0]["action"], "repair_plan")
        self.assertEqual(result.trace["steps"][0]["step"]["args"]["expression"], "100 - 12")

    def test_agent_fails_when_reflection_cannot_repair(self) -> None:
        registry = ToolRegistry()
        plan = Plan(
            goal="use missing tool",
            steps=[
                Step(
                    id="step_1",
                    description="Use unknown tool.",
                    tool="web_search",
                    args={"query": "MiniAgentLab"},
                )
            ],
        )
        agent = Agent(
            planner=StaticPlanner(plan),
            tools=registry,
            max_reflections=1,
        )

        result = agent.run("search MiniAgentLab")

        self.assertFalse(result.success)
        self.assertEqual(result.outputs, {})
        self.assertEqual(result.trace["steps"], [])
        self.assertFalse(result.validation["valid"])
        self.assertEqual(result.reflections[0]["action"], "replan")


if __name__ == "__main__":
    unittest.main()
