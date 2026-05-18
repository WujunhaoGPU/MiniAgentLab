from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any


_READONLY_START_PATTERN = re.compile(r"^(select|with)\b", re.IGNORECASE)
_COMMENT_PATTERN = re.compile(r"(--[^\n\r]*|/\*.*?\*/)", re.DOTALL)


def list_tables(db_path: str) -> list[str]:
    """Return user-created table names from a local SQLite database."""
    connection = _connect(db_path)
    try:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
    finally:
        connection.close()
    return [str(row["name"]) for row in rows]


def describe_table(db_path: str, table_name: str) -> dict[str, Any]:
    """Return column metadata for a table."""
    connection = _connect(db_path)
    try:
        columns = connection.execute(
            """
            SELECT name, type, "notnull" AS not_null, dflt_value AS default_value, pk
            FROM pragma_table_info(?)
            ORDER BY cid
            """,
            (table_name,),
        ).fetchall()
    finally:
        connection.close()

    if not columns:
        raise ValueError(f"Table not found or has no columns: {table_name}")

    return {
        "table": table_name,
        "columns": [
            {
                "name": row["name"],
                "type": row["type"],
                "not_null": bool(row["not_null"]),
                "default_value": row["default_value"],
                "primary_key": bool(row["pk"]),
            }
            for row in columns
        ],
    }


def run_sql(db_path: str, sql: str, max_rows: int = 50) -> dict[str, Any]:
    """Run one read-only SQL statement against a local SQLite database."""
    if max_rows < 1:
        raise ValueError("max_rows must be at least 1")

    safe_sql = _validate_readonly_sql(sql)
    connection = _connect(db_path)
    try:
        connection.set_authorizer(_readonly_authorizer)
        cursor = connection.execute(safe_sql)
        rows = cursor.fetchmany(max_rows + 1)
        columns = [item[0] for item in cursor.description or []]
    finally:
        connection.close()

    limited_rows = rows[:max_rows]
    return {
        "columns": columns,
        "rows": [dict(row) for row in limited_rows],
        "row_count": len(limited_rows),
        "truncated": len(rows) > max_rows,
        "max_rows": max_rows,
    }


def _connect(db_path: str) -> sqlite3.Connection:
    path = Path(db_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"SQLite database not found: {db_path}")
    if not path.is_file():
        raise ValueError(f"SQLite database path is not a file: {db_path}")

    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def _validate_readonly_sql(sql: str) -> str:
    statement = sql.strip()
    if not statement:
        raise ValueError("SQL must not be empty")

    statement_without_comments = _COMMENT_PATTERN.sub(" ", statement).strip()
    if not _READONLY_START_PATTERN.search(statement_without_comments):
        raise ValueError("Only read-only SELECT or WITH queries are allowed")

    trimmed = statement_without_comments.rstrip(";").strip()
    if ";" in trimmed:
        raise ValueError("Only one SQL statement is allowed")
    return statement


def _readonly_authorizer(
    action_code: int,
    arg1: str | None,
    arg2: str | None,
    db_name: str | None,
    trigger_name: str | None,
) -> int:
    allowed_actions = {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
    }
    if action_code in allowed_actions:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY
