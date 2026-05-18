from __future__ import annotations

from pathlib import Path
import sqlite3
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from miniagentlab import Agent, SQLReflection, ToolRegistry, TraceLogger
from miniagentlab.planner import Planner
from miniagentlab.schemas import Plan, PlannerContext, Step
from miniagentlab.sql_tools import describe_table, list_tables, run_sql


class DemoSQLPlanner(Planner):
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def plan(self, task: str, tools: ToolRegistry, context: PlannerContext | None = None) -> Plan:
        return Plan(
            goal=task,
            steps=[
                Step(
                    id="step_1",
                    description="List available tables.",
                    tool="list_tables",
                    args={"db_path": str(self.db_path)},
                ),
                Step(
                    id="step_2",
                    description="Inspect the orders table schema.",
                    tool="describe_table",
                    args={"db_path": str(self.db_path), "table_name": "orders"},
                ),
                Step(
                    id="step_3",
                    description="Compute paid revenue by customer.",
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


def build_agent(db_path: Path) -> Agent:
    registry = ToolRegistry()
    registry.register(list_tables, name="list_tables", description="List SQLite tables.")
    registry.register(describe_table, name="describe_table", description="Describe one SQLite table.")
    registry.register(run_sql, name="run_sql", description="Run one read-only SQLite query.")
    return Agent(
        planner=DemoSQLPlanner(db_path),
        tools=registry,
        trace_logger=TraceLogger(),
        reflection=SQLReflection(),
        max_retries=0,
    )


def prepare_demo_database(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        return

    connection = sqlite3.connect(db_path)
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


def main() -> None:
    db_path = Path("traces") / "demo_shop.db"
    prepare_demo_database(db_path)

    agent = build_agent(db_path)
    result = agent.run("Find paid revenue by customer")
    print(result.final_answer)
    print(result.outputs["step_3"])

    trace_path = agent.trace_logger.export_json(Path("traces") / "sql_agent_trace.json")
    print(f"Trace saved to: {trace_path}")


if __name__ == "__main__":
    main()
