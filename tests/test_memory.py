from __future__ import annotations

import unittest

from miniagentlab import Agent, RuleBasedPlanner, ShortTermMemory, ToolRegistry, TraceLogger
from miniagentlab.builtin_tools import calculator
from miniagentlab.planner import Planner
from miniagentlab.schemas import Plan, PlannerContext, Step


def label_value(value: object) -> str:
    return f"value={value}"


def join_values(values: list[object]) -> str:
    return ",".join(str(value) for value in values)


class StaticPlanner(Planner):
    def __init__(self, plan: Plan) -> None:
        self._plan = plan

    def plan(self, task: str, tools: ToolRegistry, context: PlannerContext | None = None) -> Plan:
        return self._plan


class ShortTermMemoryTests(unittest.TestCase):
    def test_memory_set_get_clear_and_snapshot(self) -> None:
        memory = ShortTermMemory()

        memory.set("step_1", "56088", source="calculator", args={"expression": "123 * 456"})

        self.assertEqual(memory.get("step_1"), "56088")
        self.assertEqual(memory.get("missing", default="fallback"), "fallback")
        self.assertEqual(memory.to_dict()["step_1"]["source"], "calculator")
        self.assertEqual(memory.to_dict()["step_1"]["metadata"]["args"]["expression"], "123 * 456")

        memory.clear()

        self.assertEqual(memory.to_dict(), {})

    def test_agent_stores_successful_step_output_in_memory(self) -> None:
        registry = ToolRegistry()
        registry.register(calculator, name="calculator")
        memory = ShortTermMemory()
        agent = Agent(
            planner=RuleBasedPlanner(),
            tools=registry,
            trace_logger=TraceLogger(),
            memory=memory,
        )

        result = agent.run("calculate 123 * 456")

        self.assertTrue(result.success)
        self.assertEqual(memory.get("step_1"), "56088")
        self.assertEqual(result.memory["step_1"]["value"], "56088")
        self.assertEqual(result.memory["step_1"]["source"], "calculator")
        self.assertEqual(result.memory["step_1"]["metadata"]["args"]["expression"], "123 * 456")

    def test_agent_clears_short_term_memory_between_runs(self) -> None:
        registry = ToolRegistry()
        registry.register(calculator, name="calculator")
        memory = ShortTermMemory()
        agent = Agent(
            planner=RuleBasedPlanner(),
            tools=registry,
            trace_logger=TraceLogger(),
            memory=memory,
        )

        first = agent.run("calculate 123 * 456")
        second = agent.run("calculate 2 + 2")

        self.assertEqual(first.memory["step_1"]["value"], "56088")
        self.assertEqual(second.memory["step_1"]["value"], "4")
        self.assertEqual(memory.get("step_1"), "4")

    def test_failed_step_does_not_write_memory(self) -> None:
        registry = ToolRegistry()
        registry.register(calculator, name="calculator")
        plan = Plan(
            goal="bad calculation",
            steps=[
                Step(
                    id="step_1",
                    description="Divide by zero.",
                    tool="calculator",
                    args={"expression": "1 / 0"},
                )
            ],
        )
        memory = ShortTermMemory()
        agent = Agent(
            planner=StaticPlanner(plan),
            tools=registry,
            trace_logger=TraceLogger(),
            memory=memory,
            max_retries=0,
        )

        result = agent.run("bad calculation")

        self.assertFalse(result.success)
        self.assertEqual(memory.to_dict(), {})
        self.assertEqual(result.memory, {})

    def test_step_args_can_reference_previous_memory_output(self) -> None:
        registry = ToolRegistry()
        registry.register(calculator, name="calculator")
        registry.register(label_value, name="label_value")
        plan = Plan(
            goal="reuse previous output",
            steps=[
                Step(
                    id="step_1",
                    description="Calculate the value.",
                    tool="calculator",
                    args={"expression": "3 * 7"},
                ),
                Step(
                    id="step_2",
                    description="Label the previous value.",
                    tool="label_value",
                    args={"value": "$memory.step_1"},
                ),
            ],
        )
        agent = Agent(
            planner=StaticPlanner(plan),
            tools=registry,
            trace_logger=TraceLogger(),
            memory=ShortTermMemory(),
        )

        result = agent.run("reuse previous output")

        self.assertTrue(result.success)
        self.assertEqual(result.outputs["step_1"], "21")
        self.assertEqual(result.outputs["step_2"], "value=21")
        self.assertEqual(result.trace["plan"]["steps"][1]["args"]["value"], "$memory.step_1")
        self.assertEqual(result.trace["steps"][1]["step"]["args"]["value"], "21")
        self.assertEqual(result.memory["step_2"]["metadata"]["raw_args"]["value"], "$memory.step_1")

    def test_nested_step_args_can_reference_memory_output(self) -> None:
        registry = ToolRegistry()
        registry.register(calculator, name="calculator")
        registry.register(join_values, name="join_values")
        plan = Plan(
            goal="reuse output inside a list",
            steps=[
                Step(
                    id="step_1",
                    description="Calculate the value.",
                    tool="calculator",
                    args={"expression": "2 + 2"},
                ),
                Step(
                    id="step_2",
                    description="Join values.",
                    tool="join_values",
                    args={"values": ["answer", "$memory.step_1"]},
                ),
            ],
        )
        agent = Agent(
            planner=StaticPlanner(plan),
            tools=registry,
            trace_logger=TraceLogger(),
            memory=ShortTermMemory(),
        )

        result = agent.run("reuse output inside a list")

        self.assertTrue(result.success)
        self.assertEqual(result.outputs["step_2"], "answer,4")
        self.assertEqual(result.trace["steps"][1]["step"]["args"]["values"], ["answer", "4"])

    def test_memory_reference_can_access_dict_field(self) -> None:
        memory = ShortTermMemory()
        memory.set("step_1", {"store_id": "notes", "chunk_count": 3}, source="index_chunks")

        resolved = memory.resolve_references("$memory.step_1.store_id")

        self.assertEqual(resolved, "notes")

    def test_memory_reference_can_access_list_index(self) -> None:
        memory = ShortTermMemory()
        memory.set("step_1", ["first", "second"], source="list_values")

        resolved = memory.resolve_references("$memory.step_1.1")

        self.assertEqual(resolved, "second")

    def test_missing_memory_reference_fails_step_before_tool_call(self) -> None:
        registry = ToolRegistry()
        registry.register(label_value, name="label_value")
        plan = Plan(
            goal="missing memory reference",
            steps=[
                Step(
                    id="step_1",
                    description="Reference a missing value.",
                    tool="label_value",
                    args={"value": "$memory.missing"},
                )
            ],
        )
        agent = Agent(
            planner=StaticPlanner(plan),
            tools=registry,
            trace_logger=TraceLogger(),
            memory=ShortTermMemory(),
            max_retries=0,
        )

        result = agent.run("missing memory reference")

        self.assertFalse(result.success)
        self.assertIn("Memory reference not found", result.final_answer)
        self.assertEqual(result.outputs, {})
        self.assertEqual(result.memory, {})
        self.assertIn("MemoryReferenceError", result.trace["steps"][0]["error"])


if __name__ == "__main__":
    unittest.main()
