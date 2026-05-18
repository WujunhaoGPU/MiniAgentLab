from __future__ import annotations

import re
from typing import Any

from .executor import ExecutionResult
from .reflection import PlanReflection, ReflectionResult
from .schemas import Plan, PlannerContext


class SQLReflection(PlanReflection):
    """Reflection policy for read-only SQLite analysis tasks."""

    def reflect_execution(
        self,
        plan: Plan,
        execution: ExecutionResult,
        context: PlannerContext,
    ) -> ReflectionResult:
        error = execution.error or ""
        failed_step = execution.failed_step
        failed_step_data = failed_step.to_dict() if failed_step is not None else None

        if failed_step is None or failed_step.tool != "run_sql":
            return super().reflect_execution(plan, execution, context)

        error_type = self._classify_sql_error(error)
        feedback = {
            "source": "SQLReflection",
            "error_type": error_type,
            "error": error,
            "failed_step": failed_step_data,
            "guidance": self._guidance_for(error_type, error),
        }

        if error_type == "unsafe_sql":
            return ReflectionResult(
                action="fail",
                reason="Unsafe SQL must not be automatically rewritten.",
                feedback=feedback,
            )

        return ReflectionResult(
            action="replan",
            reason=f"SQL execution failed with {error_type}; ask planner to inspect schema and rewrite query.",
            feedback=feedback,
        )

    def _classify_sql_error(self, error: str) -> str:
        lowered = error.lower()
        if "only read-only select or with queries are allowed" in lowered:
            return "unsafe_sql"
        if "not authorized" in lowered:
            return "unsafe_sql"
        if "no such table" in lowered:
            return "missing_table"
        if "no such column" in lowered:
            return "missing_column"
        if "syntax error" in lowered:
            return "syntax_error"
        return "sql_execution_error"

    def _guidance_for(self, error_type: str, error: str) -> str:
        if error_type == "missing_table":
            table_name = self._extract_named_error_target(error, "no such table")
            if table_name:
                return f"Call list_tables, then use an existing table instead of {table_name}."
            return "Call list_tables, then use existing table names only."
        if error_type == "missing_column":
            column_name = self._extract_named_error_target(error, "no such column")
            if column_name:
                return f"Call describe_table for relevant tables, then use an existing column instead of {column_name}."
            return "Call describe_table for relevant tables, then use existing columns only."
        if error_type == "syntax_error":
            return "Rewrite the SQL as one valid SQLite SELECT or WITH statement."
        if error_type == "unsafe_sql":
            return "Do not rewrite unsafe write operations automatically; return a safe failure."
        return "Inspect available tables and schemas before rewriting the SQL."

    def _extract_named_error_target(self, error: str, marker: str) -> str | None:
        pattern = re.compile(rf"{re.escape(marker)}:\s*([^\s]+)", re.IGNORECASE)
        match = pattern.search(error)
        if match is None:
            return None
        return match.group(1)
