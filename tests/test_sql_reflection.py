from __future__ import annotations

import unittest

from miniagentlab.executor import ExecutionResult
from miniagentlab.schemas import Plan, PlannerContext, Step
from miniagentlab.sql_reflection import SQLReflection


class SQLReflectionTests(unittest.TestCase):
    def test_replans_missing_table_error(self) -> None:
        failed_step = Step(
            id="step_1",
            description="Query missing table.",
            tool="run_sql",
            args={"sql": "SELECT * FROM sales"},
        )
        execution = ExecutionResult(
            success=False,
            error="OperationalError: no such table: sales",
            failed_step=failed_step,
        )

        reflection = SQLReflection().reflect_execution(
            Plan(goal="query", steps=[failed_step]),
            execution,
            PlannerContext(),
        )

        self.assertEqual(reflection.action, "replan")
        self.assertEqual(reflection.feedback["error_type"], "missing_table")
        self.assertIn("list_tables", reflection.feedback["guidance"])

    def test_fails_unsafe_sql_without_replan(self) -> None:
        failed_step = Step(
            id="step_1",
            description="Delete rows.",
            tool="run_sql",
            args={"sql": "DELETE FROM orders"},
        )
        execution = ExecutionResult(
            success=False,
            error="ValueError: Only read-only SELECT or WITH queries are allowed",
            failed_step=failed_step,
        )

        reflection = SQLReflection().reflect_execution(
            Plan(goal="delete", steps=[failed_step]),
            execution,
            PlannerContext(),
        )

        self.assertEqual(reflection.action, "fail")
        self.assertEqual(reflection.feedback["error_type"], "unsafe_sql")


if __name__ == "__main__":
    unittest.main()
