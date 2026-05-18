from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .executor import ExecutionResult
from .schemas import Plan, PlannerContext, Step
from .validator import PlanValidationResult


@dataclass(frozen=True)
class ReflectionResult:
    action: str
    reason: str
    plan: Plan | None = None
    feedback: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.plan is not None:
            data["plan"] = self.plan.to_dict()
        return data


class PlanReflection:
    """Decides how to respond to failed validation or execution."""

    _REPAIRABLE_CODES = {"operation_hint_conflict", "missing_calculator_expression"}

    def reflect(
        self,
        plan: Plan,
        validation: PlanValidationResult,
        context: PlannerContext,
    ) -> ReflectionResult:
        if validation.valid:
            return ReflectionResult(action="none", reason="Plan is already valid.")

        if self._can_repair_calculator_expression(validation):
            return ReflectionResult(
                action="repair_plan",
                reason="High-confidence operation hint repair.",
                plan=self._repair_calculator_expression(plan, validation),
                feedback={
                    "source": "PlanValidator",
                    "issues": [issue.to_dict() for issue in validation.issues],
                },
            )

        return ReflectionResult(
            action="replan",
            reason="Validation issues are not safe to repair deterministically.",
            feedback={
                "source": "PlanValidator",
                "issues": [issue.to_dict() for issue in validation.issues],
            },
        )

    def reflect_execution(
        self,
        plan: Plan,
        execution: ExecutionResult,
        context: PlannerContext,
    ) -> ReflectionResult:
        return ReflectionResult(
            action="fail",
            reason="Execution failure is not handled by the default reflection policy.",
            feedback={
                "source": "Executor",
                "error": execution.error,
                "failed_step": execution.failed_step.to_dict() if execution.failed_step is not None else None,
            },
        )

    def _can_repair_calculator_expression(self, validation: PlanValidationResult) -> bool:
        if not validation.issues:
            return False
        for issue in validation.issues:
            if issue.code not in self._REPAIRABLE_CODES:
                return False
            if issue.step_id is None:
                return False
            expected_expression = issue.metadata.get("expected_expression")
            if not isinstance(expected_expression, str) or not expected_expression.strip():
                return False
        return True

    def _repair_calculator_expression(self, plan: Plan, validation: PlanValidationResult) -> Plan:
        repairs = {
            issue.step_id: issue.metadata["expected_expression"]
            for issue in validation.issues
            if issue.step_id is not None
        }
        repaired_steps: list[Step] = []

        for step in plan.steps:
            if step.id not in repairs:
                repaired_steps.append(step)
                continue

            repaired_args = dict(step.args)
            repaired_args["expression"] = repairs[step.id]
            repaired_steps.append(
                Step(
                    id=step.id,
                    description=f"{step.description} Reflection repaired calculator expression.",
                    tool=step.tool,
                    args=repaired_args,
                )
            )

        return Plan(goal=plan.goal, steps=repaired_steps)
