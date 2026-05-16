from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class LLMClient(Protocol):
    """Minimal interface required by LLMPlanner."""

    def complete(self, prompt: str) -> str:
        raise NotImplementedError


class LLMError(RuntimeError):
    """Raised when an LLM provider call fails."""


@dataclass(frozen=True)
class OpenAICompatibleLLM:
    """Small OpenAI-compatible chat completions client using only stdlib."""

    api_key: str
    base_url: str
    model: str
    timeout: float = 30.0
    temperature: float = 0.0

    @classmethod
    def from_env(cls, env_path: str | Path = ".env") -> "OpenAICompatibleLLM":
        env = _load_env_file(env_path)
        api_key = (
            os.environ.get("DEEPSEEK_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or env.get("DEEPSEEK_API_KEY")
            or env.get("OPENAI_API_KEY")
        )
        base_url = os.environ.get("LLM_BASE_URL") or env.get("LLM_BASE_URL")
        model = os.environ.get("LLM_MODEL") or env.get("LLM_MODEL")

        missing = [
            name
            for name, value in {
                "DEEPSEEK_API_KEY or OPENAI_API_KEY": api_key,
                "LLM_BASE_URL": base_url,
                "LLM_MODEL": model,
            }.items()
            if not value
        ]
        if missing:
            raise LLMError(f"Missing LLM environment values: {', '.join(missing)}")

        return cls(api_key=api_key, base_url=base_url, model=model)

    def complete(self, prompt: str) -> str:
        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a strict planning engine. Return only valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
        }
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise LLMError(f"LLM HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise LLMError(f"LLM request failed: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise LLMError(f"LLM response was not valid JSON: {exc}") from exc

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("LLM response did not include choices[0].message.content") from exc


def _load_env_file(path: str | Path) -> dict[str, str]:
    target = Path(path)
    if not target.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in target.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values
