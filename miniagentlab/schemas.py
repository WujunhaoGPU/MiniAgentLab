from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Step:
    id: str
    description: str
    tool: str
    args: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Plan:
    goal: str
    steps: list[Step]

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "steps": [step.to_dict() for step in self.steps],
        }


@dataclass(frozen=True)
class OperationHint:
    intent: str
    reference: str
    operator: str
    operand: str
    raw_text: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class PlannerContext:
    conversation: list[dict[str, Any]] = field(default_factory=list)
    operation_hints: list[OperationHint] = field(default_factory=list)
    reflection_feedback: list[dict[str, Any]] = field(default_factory=list)
    max_conversation_turns: int = 6

    def recent_conversation(self) -> list[dict[str, Any]]:
        if self.max_conversation_turns < 1:
            return []
        return self.conversation[-self.max_conversation_turns :]

    def operation_hints_as_dicts(self) -> list[dict[str, str]]:
        return [hint.to_dict() for hint in self.operation_hints]

    def with_reflection_feedback(self, feedback: dict[str, Any]) -> PlannerContext:
        return PlannerContext(
            conversation=self.conversation,
            operation_hints=self.operation_hints,
            reflection_feedback=[*self.reflection_feedback, feedback],
            max_conversation_turns=self.max_conversation_turns,
        )


@dataclass(frozen=True)
class ToolResult:
    success: bool
    output: Any = None
    error: str | None = None


@dataclass(frozen=True)
class AgentResult:
    task: str
    plan: Plan
    success: bool
    final_answer: str
    outputs: dict[str, Any]
    memory: dict[str, Any]
    conversation: list[dict[str, Any]]
    trace: dict[str, Any]
    validation: dict[str, Any] = field(default_factory=dict)
    reflections: list[dict[str, Any]] = field(default_factory=list)
