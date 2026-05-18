from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .operation_hints import extract_result_values
from .schemas import Plan, PlannerContext, Step
from .tool_registry import ToolRegistry


@dataclass(frozen=True)
class PlanValidationIssue:
    code: str
    message: str
    step_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PlanValidationResult:
    valid: bool
    issues: list[PlanValidationIssue] = field(default_factory=list)

    @classmethod
    def ok(cls) -> PlanValidationResult:
        return cls(valid=True)

    @classmethod
    def invalid(cls, issues: list[PlanValidationIssue]) -> PlanValidationResult:
        return cls(valid=False, issues=issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "issues": [issue.to_dict() for issue in self.issues],
        }


class PlanValidator:
    """Checks a generated plan before the executor runs tools."""

    def validate(
        self,
        plan: Plan,
        tools: ToolRegistry,
        context: PlannerContext | None = None,
        max_steps: int | None = None,
    ) -> PlanValidationResult:
        issues: list[PlanValidationIssue] = []

        if max_steps is not None and len(plan.steps) > max_steps:
            issues.append(
                PlanValidationIssue(
                    code="too_many_steps",
                    message=f"Plan has {len(plan.steps)} steps, exceeding max_steps={max_steps}",
                    metadata={"step_count": len(plan.steps), "max_steps": max_steps},
                )
            )

        seen_step_ids: set[str] = set()
        for step in plan.steps:
            if step.id in seen_step_ids:
                issues.append(
                    PlanValidationIssue(
                        code="duplicate_step_id",
                        message=f"Duplicate step id: {step.id}",
                        step_id=step.id,
                    )
                )
            seen_step_ids.add(step.id)

            if not tools.has(step.tool):
                issues.append(
                    PlanValidationIssue(
                        code="unknown_tool",
                        message=f"Step {step.id} references unknown tool: {step.tool}",
                        step_id=step.id,
                        metadata={"tool": step.tool},
                    )
                )

        issues.extend(self._validate_operation_hints(plan, context))

        if issues:
            return PlanValidationResult.invalid(issues)
        return PlanValidationResult.ok()

    def _validate_operation_hints(
        self,
        plan: Plan,
        context: PlannerContext | None,
    ) -> list[PlanValidationIssue]:
        if context is None or not context.operation_hints:
            return []

        prior_results = extract_result_values(context.recent_conversation())
        if not prior_results:
            return []

        hint = context.operation_hints[0]
        if hint.intent != "arithmetic_transform" or hint.reference != "previous_result":
            return []

        prior_value = prior_results[-1]["value"]
        expected_expression = f"{prior_value} {hint.operator} {hint.operand}"
        expected_compact = self._compact_expression(expected_expression)
        issues: list[PlanValidationIssue] = []

        for step in plan.steps:
            if step.tool != "calculator":
                continue

            expression = step.args.get("expression")
            if not isinstance(expression, str) or not expression.strip():
                issues.append(
                    PlanValidationIssue(
                        code="missing_calculator_expression",
                        message=f"Step {step.id} is missing a calculator expression",
                        step_id=step.id,
                        metadata={"expected_expression": expected_expression},
                    )
                )
                continue

            actual_compact = self._compact_expression(expression)
            if expected_compact not in actual_compact:
                issues.append(
                    PlanValidationIssue(
                        code="operation_hint_conflict",
                        message=(
                            f"Step {step.id} calculator expression conflicts with parsed operation hint: "
                            f"expected {expected_expression}, got {expression}"
                        ),
                        step_id=step.id,
                        metadata={
                            "expected_expression": expected_expression,
                            "actual_expression": expression,
                        },
                    )
                )

        return issues

    def _compact_expression(self, expression: str) -> str:
        return "".join(expression.split())
