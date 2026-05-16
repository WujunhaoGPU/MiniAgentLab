from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

from .schemas import Plan
from .tool_registry import ToolRegistry
from .trace import TraceLogger


@dataclass
class ExecutionResult:
    success: bool
    outputs: dict[str, object] = field(default_factory=dict)
    error: str | None = None


class Executor:
    """Runs plan steps against registered tools."""

    def __init__(self, tools: ToolRegistry, trace_logger: TraceLogger, max_retries: int = 1) -> None:
        self.tools = tools
        self.trace_logger = trace_logger
        self.max_retries = max_retries

    def execute(self, plan: Plan) -> ExecutionResult:
        outputs: dict[str, object] = {}

        for step in plan.steps:
            attempts = 0
            last_error: str | None = None

            while attempts <= self.max_retries:
                attempts += 1
                started = perf_counter()
                result = self.tools.call(step.tool, **step.args)
                duration_ms = round((perf_counter() - started) * 1000, 3)

                self.trace_logger.record_step(
                    step=step,
                    attempt=attempts,
                    success=result.success,
                    output=result.output,
                    error=result.error,
                    duration_ms=duration_ms,
                )

                if result.success:
                    outputs[step.id] = result.output
                    break

                last_error = result.error

            else:
                return ExecutionResult(success=False, outputs=outputs, error=last_error)

            if last_error is not None and step.id not in outputs:
                return ExecutionResult(success=False, outputs=outputs, error=last_error)

        return ExecutionResult(success=True, outputs=outputs)
