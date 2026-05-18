from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from miniagentlab.sql_tools import describe_table, list_tables, run_sql


class SQLToolsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "shop.db"
        self._create_database(self.db_path)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_list_tables_returns_user_tables(self) -> None:
        tables = list_tables(str(self.db_path))

        self.assertEqual(tables, ["customers", "orders"])

    def test_describe_table_returns_schema(self) -> None:
        schema = describe_table(str(self.db_path), "orders")

        self.assertEqual(schema["table"], "orders")
        column_names = [column["name"] for column in schema["columns"]]
        self.assertEqual(column_names, ["id", "customer_id", "amount", "status"])
        self.assertTrue(schema["columns"][0]["primary_key"])

    def test_run_sql_returns_rows(self) -> None:
        result = run_sql(
            str(self.db_path),
            """
            SELECT c.name, SUM(o.amount) AS total_amount
            FROM customers c
            JOIN orders o ON o.customer_id = c.id
            GROUP BY c.name
            ORDER BY total_amount DESC
            """,
        )

        self.assertEqual(result["columns"], ["name", "total_amount"])
        self.assertEqual(result["rows"][0], {"name": "Ada", "total_amount": 160.5})
        self.assertEqual(result["row_count"], 2)
        self.assertFalse(result["truncated"])

    def test_run_sql_truncates_rows(self) -> None:
        result = run_sql(str(self.db_path), "SELECT id FROM orders ORDER BY id", max_rows=2)

        self.assertEqual(result["row_count"], 2)
        self.assertTrue(result["truncated"])

    def test_run_sql_rejects_unsafe_sql(self) -> None:
        unsafe_cases = [
            "DELETE FROM orders",
            "UPDATE orders SET amount = 0",
            "DROP TABLE orders",
            "SELECT * FROM orders; SELECT * FROM customers",
        ]

        for sql in unsafe_cases:
            with self.subTest(sql=sql):
                with self.assertRaises(ValueError):
                    run_sql(str(self.db_path), sql)

    def test_describe_table_rejects_missing_table(self) -> None:
        with self.assertRaisesRegex(ValueError, "Table not found"):
            describe_table(str(self.db_path), "missing")

    def test_missing_database_raises_clear_error(self) -> None:
        with self.assertRaises(FileNotFoundError):
            list_tables(str(Path(self.tempdir.name) / "missing.db"))

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
