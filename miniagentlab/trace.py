from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schemas import Plan, Step


class TraceLogger:
    """Collects a portable JSON trace of one agent run."""

    def __init__(self) -> None:
        self._trace: dict[str, Any] = {}

    def start_task(self, task: str) -> None:
        self._trace = {
            "task": task,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "plan": None,
            "steps": [],
            "final_answer": None,
        }

    def record_plan(self, plan: Plan) -> None:
        self._trace["plan"] = plan.to_dict()

    def record_step(
        self,
        step: Step,
        attempt: int,
        success: bool,
        output: object,
        error: str | None,
        duration_ms: float,
    ) -> None:
        self._trace["steps"].append(
            {
                "step": step.to_dict(),
                "attempt": attempt,
                "success": success,
                "output": output,
                "error": error,
                "duration_ms": duration_ms,
            }
        )

    def finish(self, final_answer: str) -> None:
        self._trace["finished_at"] = datetime.now(timezone.utc).isoformat()
        self._trace["final_answer"] = final_answer

    def to_dict(self) -> dict[str, Any]:
        return dict(self._trace)

    def export_json(self, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self._trace, ensure_ascii=True, indent=2), encoding="utf-8")
        return target
