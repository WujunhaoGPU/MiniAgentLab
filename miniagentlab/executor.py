from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter

from .memory import MemoryReferenceError, ShortTermMemory
from .schemas import Plan, Step
from .tool_registry import ToolRegistry
from .trace import TraceLogger


@dataclass
class ExecutionResult:
    success: bool
    outputs: dict[str, object] = field(default_factory=dict)
    error: str | None = None


class Executor:
    """Runs plan steps against registered tools."""

    def __init__(
        self,
        tools: ToolRegistry,
        trace_logger: TraceLogger,
        memory: ShortTermMemory,
        max_retries: int = 1,
        max_steps: int = 10,
    ) -> None:
        if max_steps < 1:
            raise ValueError("max_steps must be at least 1")

        self.tools = tools
        self.trace_logger = trace_logger
        self.memory = memory
        self.max_retries = max_retries
        self.max_steps = max_steps

    def execute(self, plan: Plan) -> ExecutionResult:
        outputs: dict[str, object] = {}

        if len(plan.steps) > self.max_steps:
            return ExecutionResult(
                success=False,
                outputs=outputs,
                error=f"Plan has {len(plan.steps)} steps, exceeding max_steps={self.max_steps}",
            )

        for step in plan.steps:
            attempts = 0
            last_error: str | None = None

            while attempts <= self.max_retries:
                attempts += 1
                started = perf_counter()
                try:
                    resolved_args = self.memory.resolve_references(step.args)
                except MemoryReferenceError as exc:
                    duration_ms = round((perf_counter() - started) * 1000, 3)
                    error = f"{type(exc).__name__}: {exc}"
                    self.trace_logger.record_step(
                        step=step,
                        attempt=attempts,
                        success=False,
                        output=None,
                        error=error,
                        duration_ms=duration_ms,
                    )
                    return ExecutionResult(success=False, outputs=outputs, error=error)

                resolved_step = Step(
                    id=step.id,
                    description=step.description,
                    tool=step.tool,
                    args=resolved_args,
                )
                result = self.tools.call(step.tool, **resolved_args)
                duration_ms = round((perf_counter() - started) * 1000, 3)

                self.trace_logger.record_step(
                    step=resolved_step,
                    attempt=attempts,
                    success=result.success,
                    output=result.output,
                    error=result.error,
                    duration_ms=duration_ms,
                )

                if result.success:
                    outputs[step.id] = result.output
                    self.memory.set(
                        key=step.id,
                        value=result.output,
                        source=step.tool,
                        args=resolved_args,
                        raw_args=step.args,
                        description=step.description,
                    )
                    break

                last_error = result.error

            else:
                return ExecutionResult(success=False, outputs=outputs, error=last_error)

            if last_error is not None and step.id not in outputs:
                return ExecutionResult(success=False, outputs=outputs, error=last_error)

        return ExecutionResult(success=True, outputs=outputs)
