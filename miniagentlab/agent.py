from __future__ import annotations

from .executor import Executor
from .memory import ConversationMemory, ShortTermMemory
from .operation_hints import parse_operation_hints
from .planner import Planner
from .reflection import PlanReflection
from .schemas import AgentResult, PlannerContext
from .tool_registry import ToolRegistry
from .trace import TraceLogger
from .validator import PlanValidator


class Agent:
    """Coordinates planning, tool execution, and trace export."""

    def __init__(
        self,
        planner: Planner,
        tools: ToolRegistry,
        trace_logger: TraceLogger | None = None,
        memory: ShortTermMemory | None = None,
        conversation_memory: ConversationMemory | None = None,
        plan_validator: PlanValidator | None = None,
        reflection: PlanReflection | None = None,
        max_retries: int = 1,
        max_steps: int = 10,
        max_reflections: int = 1,
    ) -> None:
        self.planner = planner
        self.tools = tools
        self.trace_logger = trace_logger or TraceLogger()
        self.memory = memory or ShortTermMemory()
        self.conversation_memory = conversation_memory or ConversationMemory()
        self.plan_validator = plan_validator or PlanValidator()
        self.reflection = reflection or PlanReflection()
        self.max_reflections = max_reflections
        self.executor = Executor(
            tools=tools,
            trace_logger=self.trace_logger,
            memory=self.memory,
            max_retries=max_retries,
            max_steps=max_steps,
        )

    def run(self, task: str) -> AgentResult:
        self.memory.clear()
        planner_context = PlannerContext(
            conversation=self.conversation_memory.to_dict(),
            operation_hints=parse_operation_hints(task),
        )
        self.conversation_memory.add("user", task)
        self.trace_logger.start_task(task)
        plan = self.planner.plan(task, self.tools, context=planner_context)
        self.trace_logger.record_plan(plan)
        validation = self.plan_validator.validate(
            plan=plan,
            tools=self.tools,
            context=planner_context,
            max_steps=self.executor.max_steps,
        )
        reflections: list[dict[str, object]] = []
        reflection_attempts = 0
        while not validation.valid and reflection_attempts < self.max_reflections:
            reflection_attempts += 1
            reflection = self.reflection.reflect(plan, validation, planner_context)
            reflections.append(reflection.to_dict())

            if reflection.action == "repair_plan" and reflection.plan is not None:
                plan = reflection.plan
            elif reflection.action == "replan":
                planner_context = planner_context.with_reflection_feedback(reflection.feedback)
                plan = self.planner.plan(task, self.tools, context=planner_context)
            else:
                break

            self.trace_logger.record_plan(plan)
            validation = self.plan_validator.validate(
                plan=plan,
                tools=self.tools,
                context=planner_context,
                max_steps=self.executor.max_steps,
            )

        if not validation.valid:
            issue_messages = "; ".join(issue.message for issue in validation.issues)
            final_answer = f"Task failed validation: {issue_messages}"
            self.trace_logger.finish(final_answer)
            run_id = self.trace_logger.to_dict().get("run_id")
            self.conversation_memory.add(
                "assistant",
                final_answer,
                success=False,
                run_id=run_id,
            )
            return AgentResult(
                task=task,
                plan=plan,
                success=False,
                final_answer=final_answer,
                outputs={},
                memory=self.memory.to_dict(),
                conversation=self.conversation_memory.to_dict(),
                trace=self.trace_logger.to_dict(),
                validation=validation.to_dict(),
                reflections=reflections,
            )

        execution = self.executor.execute(plan)
        while not execution.success and reflection_attempts < self.max_reflections:
            reflection_attempts += 1
            reflection = self.reflection.reflect_execution(plan, execution, planner_context)
            reflections.append(reflection.to_dict())

            if reflection.action != "replan":
                break

            planner_context = planner_context.with_reflection_feedback(reflection.feedback)
            plan = self.planner.plan(task, self.tools, context=planner_context)
            self.trace_logger.record_plan(plan)
            validation = self.plan_validator.validate(
                plan=plan,
                tools=self.tools,
                context=planner_context,
                max_steps=self.executor.max_steps,
            )

            while not validation.valid and reflection_attempts < self.max_reflections:
                reflection_attempts += 1
                reflection = self.reflection.reflect(plan, validation, planner_context)
                reflections.append(reflection.to_dict())

                if reflection.action == "repair_plan" and reflection.plan is not None:
                    plan = reflection.plan
                elif reflection.action == "replan":
                    planner_context = planner_context.with_reflection_feedback(reflection.feedback)
                    plan = self.planner.plan(task, self.tools, context=planner_context)
                else:
                    break

                self.trace_logger.record_plan(plan)
                validation = self.plan_validator.validate(
                    plan=plan,
                    tools=self.tools,
                    context=planner_context,
                    max_steps=self.executor.max_steps,
                )

            if not validation.valid:
                break

            execution = self.executor.execute(plan)

        if execution.success:
            final_answer = self._summarize_success(task, execution.outputs)
        else:
            final_answer = f"Task failed: {execution.error}"

        self.trace_logger.finish(final_answer)
        run_id = self.trace_logger.to_dict().get("run_id")
        self.conversation_memory.add(
            "assistant",
            final_answer,
            success=execution.success,
            run_id=run_id,
        )
        return AgentResult(
            task=task,
            plan=plan,
            success=execution.success,
            final_answer=final_answer,
            outputs=execution.outputs,
            memory=self.memory.to_dict(),
            conversation=self.conversation_memory.to_dict(),
            trace=self.trace_logger.to_dict(),
            validation=validation.to_dict(),
            reflections=reflections,
        )

    def _summarize_success(self, task: str, outputs: dict[str, object]) -> str:
        if not outputs:
            return f"Done: {task}"
        last_step_id = list(outputs.keys())[-1]
        return f"Done: {task}\nResult: {outputs[last_step_id]}"
