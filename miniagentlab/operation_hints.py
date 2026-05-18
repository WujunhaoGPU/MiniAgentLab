from __future__ import annotations

import re
from typing import Any

from .schemas import OperationHint


_NUMBER = r"(-?\d+(?:\.\d+)?)"
_REFERENCE_PATTERN = re.compile(
    r"(刚才|上一步|前面|之前|上次|previous|last|that|it)",
    re.IGNORECASE,
)

_OPERATION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(rf"加(?:上|以)?\s*{_NUMBER}"), "+"),
    (re.compile(rf"减(?:去|掉)?\s*{_NUMBER}"), "-"),
    (re.compile(rf"乘(?:以)?\s*{_NUMBER}"), "*"),
    (re.compile(rf"除(?:以)?\s*{_NUMBER}"), "/"),
    (re.compile(rf"(?:add|plus)\s+{_NUMBER}", re.IGNORECASE), "+"),
    (re.compile(rf"(?:subtract|minus)\s+{_NUMBER}", re.IGNORECASE), "-"),
    (re.compile(rf"(?:multiply|times).*?(?:by\s*)?{_NUMBER}", re.IGNORECASE), "*"),
    (re.compile(rf"divide.*?(?:by\s*)?{_NUMBER}", re.IGNORECASE), "/"),
]


def parse_operation_hints(text: str) -> list[OperationHint]:
    """Extract arithmetic follow-up hints that refer to a prior result."""
    if not _REFERENCE_PATTERN.search(text):
        return []

    hints: list[OperationHint] = []
    for pattern, operator in _OPERATION_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue
        hints.append(
            OperationHint(
                intent="arithmetic_transform",
                reference="previous_result",
                operator=operator,
                operand=match.group(1),
                raw_text=text,
            )
        )
        break

    return hints


def extract_result_values(conversation: list[dict[str, Any]]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for turn in conversation:
        content = str(turn.get("content", ""))
        for match in re.finditer(r"Result:\s*([^\n\r]+)", content):
            results.append(
                {
                    "role": str(turn.get("role", "")),
                    "value": match.group(1).strip(),
                }
            )
    return results
