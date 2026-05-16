from __future__ import annotations

from .executor import Executor
from .planner import Planner
from .schemas import AgentResult
from .tool_registry import ToolRegistry
from .trace import TraceLogger


class Agent:
    """Coordinates planning, tool execution, and trace export."""

    def __init__(
        self,
        planner: Planner,
        tools: ToolRegistry,
        trace_logger: TraceLogger | None = None,
        max_retries: int = 1,
        max_steps: int = 10,
    ) -> None:
        self.planner = planner
        self.tools = tools
        self.trace_logger = trace_logger or TraceLogger()
        self.executor = Executor(
            tools=tools,
            trace_logger=self.trace_logger,
            max_retries=max_retries,
            max_steps=max_steps,
        )

    def run(self, task: str) -> AgentResult:
        self.trace_logger.start_task(task)
        plan = self.planner.plan(task, self.tools)
        self.trace_logger.record_plan(plan)
        execution = self.executor.execute(plan)

        if execution.success:
            final_answer = self._summarize_success(task, execution.outputs)
        else:
            final_answer = f"Task failed: {execution.error}"

        self.trace_logger.finish(final_answer)
        return AgentResult(
            task=task,
            plan=plan,
            success=execution.success,
            final_answer=final_answer,
            outputs=execution.outputs,
            trace=self.trace_logger.to_dict(),
        )

    def _summarize_success(self, task: str, outputs: dict[str, object]) -> str:
        if not outputs:
            return f"Done: {task}"
        last_step_id = list(outputs.keys())[-1]
        return f"Done: {task}\nResult: {outputs[last_step_id]}"
