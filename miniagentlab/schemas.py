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
    trace: dict[str, Any]
