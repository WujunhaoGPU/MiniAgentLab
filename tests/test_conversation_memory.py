from __future__ import annotations

import unittest

from miniagentlab import Agent, ConversationMemory, RuleBasedPlanner, ToolRegistry, TraceLogger
from miniagentlab.builtin_tools import calculator


class ConversationMemoryTests(unittest.TestCase):
    def test_conversation_memory_add_recent_clear_and_snapshot(self) -> None:
        conversation = ConversationMemory(max_turns=5)

        conversation.add("system", "You are helpful.")
        conversation.add("user", "calculate 2 + 2")
        conversation.add("assistant", "Result: 4", success=True)

        self.assertEqual([turn.role for turn in conversation.recent(2)], ["user", "assistant"])
        self.assertEqual(conversation.to_dict()[2]["metadata"]["success"], True)

        conversation.clear()

        self.assertEqual(conversation.to_dict(), [])

    def test_conversation_memory_rejects_unsupported_role(self) -> None:
        conversation = ConversationMemory()

        with self.assertRaises(ValueError):
            conversation.add("tool", "not a supported chat role")

    def test_conversation_memory_rejects_invalid_max_turns(self) -> None:
        with self.assertRaises(ValueError):
            ConversationMemory(max_turns=0)

    def test_conversation_memory_keeps_only_recent_turns(self) -> None:
        conversation = ConversationMemory(max_turns=3)

        conversation.add("user", "one")
        conversation.add("assistant", "two")
        conversation.add("user", "three")
        conversation.add("assistant", "four")

        self.assertEqual(
            [turn.content for turn in conversation.recent()],
            ["two", "three", "four"],
        )
        self.assertEqual(conversation.recent(0), [])

    def test_agent_records_user_and_assistant_turns_across_runs(self) -> None:
        registry = ToolRegistry()
        registry.register(calculator, name="calculator")
        conversation = ConversationMemory(max_turns=10)
        agent = Agent(
            planner=RuleBasedPlanner(),
            tools=registry,
            trace_logger=TraceLogger(),
            conversation_memory=conversation,
        )

        first = agent.run("calculate 2 + 2")
        second = agent.run("calculate 3 + 3")

        self.assertEqual([turn["role"] for turn in first.conversation], ["user", "assistant"])
        self.assertEqual(
            [turn["role"] for turn in second.conversation],
            ["user", "assistant", "user", "assistant"],
        )
        self.assertEqual(second.conversation[0]["content"], "calculate 2 + 2")
        self.assertIn("Result: 6", second.conversation[-1]["content"])
        self.assertTrue(second.conversation[-1]["metadata"]["success"])
        self.assertTrue(second.conversation[-1]["metadata"]["run_id"].startswith("run_"))


if __name__ == "__main__":
    unittest.main()
