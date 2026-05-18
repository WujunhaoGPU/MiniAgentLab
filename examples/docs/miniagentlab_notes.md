# MiniAgentLab Notes

MiniAgentLab is a lightweight agent orchestration project. It keeps planning,
tool execution, memory, reflection, and trace logging as separate modules.

Reflection analyzes failures from validation or tool execution. It can repair a
high-confidence plan issue or ask the planner to generate a new plan with
structured feedback.

ShortTermMemory stores outputs from successful steps during one agent run.
Later steps can reference earlier outputs with values such as `$memory.step_1`.

TraceLogger records the run id, generated plan, executed steps, tool outputs,
errors, durations, and final answer.
