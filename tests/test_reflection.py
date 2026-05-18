from __future__ import annotations

import unittest

from miniagentlab import PlanReflection
from miniagentlab.reflection import ReflectionResult
from miniagentlab.schemas import Plan, PlannerContext, Step
from miniagentlab.validator import PlanValidationIssue, PlanValidationResult


class PlanReflectionTests(unittest.TestCase):
    def test_repairs_operation_hint_conflict(self) -> None:
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
        validation = PlanValidationResult.invalid(
            [
                PlanValidationIssue(
                    code="operation_hint_conflict",
                    message="wrong operation",
                    step_id="step_1",
                    metadata={
                        "expected_expression": "100 - 12",
                        "actual_expression": "100 * 12",
                    },
                )
            ]
        )

        reflection = PlanReflection().reflect(plan, validation, PlannerContext())

        self.assertIsInstance(reflection, ReflectionResult)
        self.assertEqual(reflection.action, "repair_plan")
        self.assertIsNotNone(reflection.plan)
        self.assertEqual(reflection.plan.steps[0].args["expression"], "100 - 12")

    def test_requests_replan_for_unknown_tool(self) -> None:
        plan = Plan(
            goal="search",
            steps=[Step("step_1", "Search web.", "web_search", {"query": "MiniAgentLab"})],
        )
        validation = PlanValidationResult.invalid(
            [
                PlanValidationIssue(
                    code="unknown_tool",
                    message="unknown tool",
                    step_id="step_1",
                    metadata={"tool": "web_search"},
                )
            ]
        )

        reflection = PlanReflection().reflect(plan, validation, PlannerContext())

        self.assertEqual(reflection.action, "replan")
        self.assertEqual(reflection.feedback["source"], "PlanValidator")


if __name__ == "__main__":
    unittest.main()
