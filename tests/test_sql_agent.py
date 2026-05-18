from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from miniagentlab import Agent, SQLReflection, ToolRegistry
from miniagentlab.planner import Planner
from miniagentlab.schemas import Plan, PlannerContext, Step
from miniagentlab.sql_tools import describe_table, list_tables, run_sql


class StaticPlanner(Planner):
    def __init__(self, plan: Plan) -> None:
        self._plan = plan

    def plan(self, task: str, tools: ToolRegistry, context: PlannerContext | None = None) -> Plan:
        return self._plan


class FeedbackPlanner(Planner):
    def __init__(self, initial_plan: Plan, repaired_plan: Plan) -> None:
        self.initial_plan = initial_plan
        self.repaired_plan = repaired_plan
        self.calls = 0
        self.feedback_seen: list[dict[str, object]] = []

    def plan(self, task: str, tools: ToolRegistry, context: PlannerContext | None = None) -> Plan:
        self.calls += 1
        if context is not None:
            self.feedback_seen.extend(context.reflection_feedback)
        if context is not None and context.reflection_feedback:
            return self.repaired_plan
        return self.initial_plan


class SQLAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "shop.db"
        self._create_database(self.db_path)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_agent_runs_local_sql_analysis_loop(self) -> None:
        plan = Plan(
            goal="Find paid revenue by customer.",
            steps=[
                Step(
                    id="step_1",
                    description="List tables.",
                    tool="list_tables",
                    args={"db_path": str(self.db_path)},
                ),
                Step(
                    id="step_2",
                    description="Inspect orders schema.",
                    tool="describe_table",
                    args={"db_path": str(self.db_path), "table_name": "orders"},
                ),
                Step(
                    id="step_3",
                    description="Calculate paid revenue by customer.",
                    tool="run_sql",
                    args={
                        "db_path": str(self.db_path),
                        "sql": """
                        SELECT c.name, SUM(o.amount) AS paid_revenue
                        FROM customers c
                        JOIN orders o ON o.customer_id = c.id
                        WHERE o.status = 'paid'
                        GROUP BY c.name
                        ORDER BY paid_revenue DESC
                        """,
                    },
                ),
            ],
        )
        agent = Agent(planner=StaticPlanner(plan), tools=self._build_registry())

        result = agent.run("Find paid revenue by customer")

        self.assertTrue(result.success)
        self.assertEqual(result.outputs["step_1"], ["customers", "orders"])
        self.assertEqual(result.outputs["step_3"]["rows"], [{"name": "Ada", "paid_revenue": 160.5}])
        self.assertTrue(result.validation["valid"])
        self.assertEqual(result.trace["steps"][2]["step"]["tool"], "run_sql")

    def test_agent_blocks_unsafe_sql(self) -> None:
        plan = Plan(
            goal="Delete rows.",
            steps=[
                Step(
                    id="step_1",
                    description="Try unsafe SQL.",
                    tool="run_sql",
                    args={"db_path": str(self.db_path), "sql": "DELETE FROM orders"},
                )
            ],
        )
        agent = Agent(planner=StaticPlanner(plan), tools=self._build_registry(), reflection=SQLReflection())

        result = agent.run("Delete all orders")

        self.assertFalse(result.success)
        self.assertIn("Only read-only SELECT or WITH queries are allowed", result.final_answer)
        self.assertEqual(result.outputs, {})
        self.assertEqual(result.reflections[0]["action"], "fail")
        self.assertEqual(result.reflections[0]["feedback"]["error_type"], "unsafe_sql")

    def test_sql_reflection_replans_after_missing_column(self) -> None:
        initial_plan = Plan(
            goal="Find paid revenue by customer.",
            steps=[
                Step(
                    id="step_1",
                    description="List tables.",
                    tool="list_tables",
                    args={"db_path": str(self.db_path)},
                ),
                Step(
                    id="step_2",
                    description="Inspect orders schema.",
                    tool="describe_table",
                    args={"db_path": str(self.db_path), "table_name": "orders"},
                ),
                Step(
                    id="step_3",
                    description="Use a wrong column name.",
                    tool="run_sql",
                    args={
                        "db_path": str(self.db_path),
                        "sql": """
                        SELECT c.name, SUM(o.total) AS paid_revenue
                        FROM customers c
                        JOIN orders o ON o.customer_id = c.id
                        WHERE o.status = 'paid'
                        GROUP BY c.name
                        """,
                    },
                ),
            ],
        )
        repaired_plan = Plan(
            goal="Find paid revenue by customer.",
            steps=[
                Step(
                    id="step_1",
                    description="List tables.",
                    tool="list_tables",
                    args={"db_path": str(self.db_path)},
                ),
                Step(
                    id="step_2",
                    description="Inspect orders schema.",
                    tool="describe_table",
                    args={"db_path": str(self.db_path), "table_name": "orders"},
                ),
                Step(
                    id="step_3",
                    description="Use the existing amount column.",
                    tool="run_sql",
                    args={
                        "db_path": str(self.db_path),
                        "sql": """
                        SELECT c.name, SUM(o.amount) AS paid_revenue
                        FROM customers c
                        JOIN orders o ON o.customer_id = c.id
                        WHERE o.status = 'paid'
                        GROUP BY c.name
                        """,
                    },
                ),
            ],
        )
        planner = FeedbackPlanner(initial_plan, repaired_plan)
        agent = Agent(
            planner=planner,
            tools=self._build_registry(),
            reflection=SQLReflection(),
            max_reflections=1,
        )

        result = agent.run("Find paid revenue by customer")

        self.assertTrue(result.success)
        self.assertEqual(result.outputs["step_3"]["rows"], [{"name": "Ada", "paid_revenue": 160.5}])
        self.assertEqual(planner.calls, 2)
        self.assertEqual(result.reflections[0]["action"], "replan")
        self.assertEqual(result.reflections[0]["feedback"]["error_type"], "missing_column")
        self.assertIn("describe_table", result.reflections[0]["feedback"]["guidance"])

    def _build_registry(self) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register(list_tables, name="list_tables", description="List SQLite tables.")
        registry.register(describe_table, name="describe_table", description="Describe one SQLite table.")
        registry.register(run_sql, name="run_sql", description="Run one read-only SQLite query.")
        return registry

    def _create_database(self, path: Path) -> None:
        connection = sqlite3.connect(path)
        try:
            connection.executescript(
                """
                CREATE TABLE customers (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    city TEXT
                );

                CREATE TABLE orders (
                    id INTEGER PRIMARY KEY,
                    customer_id INTEGER NOT NULL,
                    amount REAL NOT NULL,
                    status TEXT NOT NULL
                );

                INSERT INTO customers (id, name, city) VALUES
                    (1, 'Ada', 'Beijing'),
                    (2, 'Linus', 'Shanghai');

                INSERT INTO orders (id, customer_id, amount, status) VALUES
                    (1, 1, 100.0, 'paid'),
                    (2, 1, 60.5, 'paid'),
                    (3, 2, 80.0, 'pending');
                """
            )
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
