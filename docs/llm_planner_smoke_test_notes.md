# LLMPlanner 多轮 Smoke Test 复盘

本文记录 `LLMPlanner + PlannerContext + ConversationMemory` 在真实 API smoke test 中暴露的问题、修复尝试和下一步方案。

## 背景

目标是让 Agent 支持多轮规划：

```text
第一轮：计算 3 * 7
Agent：Result: 21

第二轮：把刚才的结果加 5
期望：LLMPlanner 生成 calculator 参数 {"expression": "21 + 5"}
```

单元测试使用 `FakeLLM`，主要验证：

- `ConversationMemory` 能记录历史对话
- `Agent` 能把历史对话打包进 `PlannerContext`
- `LLMPlanner` prompt 中包含 recent conversation
- LLM 返回结构化 JSON 后，框架能解析并执行

但单元测试不能验证真实模型是否会正确理解“刚才的结果”“上一步”等指代表达。因此需要真实 API smoke test。

## 第一轮问题：模型看到历史，但忽略历史值

真实测试：

```text
第一轮：计算 3 * 7 -> Result: 21
第二轮：把刚才的结果加 5
```

观察到：

```text
SECOND_PROMPT_HAS_FIRST_TASK=True
SECOND_PROMPT_HAS_FIRST_RESULT=True
```

说明 `ConversationMemory -> PlannerContext -> LLMPlanner prompt` 链路是通的。

但模型生成：

```json
{
  "tool": "calculator",
  "args": {
    "expression": "5"
  }
}
```

结果变成：

```text
Result: 5
```

问题结论：

```text
上下文已经进入 prompt，但模型没有把历史结果和当前操作组合起来。
```

## 第一次修复：增强 prompt 的引用解析规则

加入规则：

```text
当用户提到 previous result、last answer、刚才的结果、上一步等表达时，
从 recent conversation 中提取对应值，并放进 tool args。
```

并加入示例：

```text
Recent assistant says "Result: 21";
user asks "add 5 to the previous result"
-> expression should be "21 + 5", not "5"
```

结果：

```text
模型开始使用历史值，但行为仍不稳定。
```

## 第二轮问题：模型用了历史值，但理解错操作

一次真实测试中，模型生成：

```json
{
  "expression": "21 * 5"
}
```

结果：

```text
Result: 105
```

而用户输入是：

```text
把刚才的结果加 5
```

问题结论：

```text
模型引用历史值成功了，但把“加 5”错误理解成了乘以 5。
```

## 第二次修复：增加通用运算符规则

加入规则：

```text
Preserve the user's requested operation exactly.
加/add means '+',
减/subtract means '-',
乘/multiply means '*',
除/divide means '/'.
```

结果：

```text
英文 multiply / divide 场景较稳定；
中文减法 / 除法仍不稳定。
```

## 第三轮问题：中文 follow-up 运算仍失败

测试用例：

```text
第一轮：计算 50 * 2 -> Result: 100
第二轮：把上一步的结果减 12
期望：100 - 12 = 88
```

观察：

```text
prompt 中包含 Resolved prior result: 100
```

但模型生成：

```json
{
  "expression": "100 + 12"
}
```

或在另一次测试中只生成：

```json
{
  "expression": "12"
}
```

另一个测试：

```text
第一轮：计算 9 * 5 -> Result: 45
第二轮：把刚才的结果除以 5
期望：45 / 5 = 9
```

模型生成：

```json
{
  "expression": "45 * 5"
}
```

问题结论：

```text
仅靠自然语言 prompt 和 few-shot examples 仍然不够稳。
真实模型可能忽略历史值，也可能误解中文运算意图。
```

## 第三次修复：结构化 prior results

为了减少模型从长文本里抽取结果的负担，在 `LLMPlanner` 中先从 conversation 中提取：

```text
Result: 21
```

并写入 prompt：

```json
[
  {
    "role": "assistant",
    "value": "21"
  }
]
```

Prompt 中新增：

```text
Resolved prior results from recent conversation:
...

Prefer the 'Resolved prior results' list when a prior result is needed.
```

结果：

```text
“把刚才的结果加 5” 场景通过：
21 + 5 -> 26
```

但中文减法和除法仍然出现错误。

## 当前结论

目前可以确认：

```text
ConversationMemory -> PlannerContext -> LLMPlanner prompt
```

链路是正确的。

真实问题集中在：

```text
LLM 对 follow-up 指令的语义解析不稳定，
尤其是中文“减 / 除以”等操作。
```

继续堆 prompt 示例可以短期改善，但不是最稳的工程方案。

## 下一步方案：结构化 operation hints

下一步建议在进入 LLMPlanner prompt 之前，先对当前用户任务做轻量规则解析，生成结构化 hint。

例如：

```text
用户输入：把上一步的结果减 12
```

解析为：

```json
{
  "reference": "previous_result",
  "operator": "-",
  "operand": "12"
}
```

再把它放进 prompt：

```text
Parsed operation hints:
[
  {
    "reference": "previous_result",
    "operator": "-",
    "operand": "12"
  }
]
```

这样模型不需要自己完全理解中文运算词，而是可以根据结构化 hint 生成：

```json
{
  "expression": "100 - 12"
}
```

## 为什么这是更工程化的方向

相比继续加 prompt 示例，结构化 hint 有几个优势：

- 把确定性的文本解析交给代码
- 减少 LLM 对中文运算词的误解
- 让 prompt 更短、更稳定
- 可以用单元测试覆盖 hint 解析逻辑
- 真实 API smoke test 只需要验证 LLM 是否使用 hint

推荐实现路径：

```text
1. 新增 OperationHint 数据结构
2. 在 PlannerContext 中增加 operation_hints
3. 编写轻量 parser，识别加、减、乘、除和对应数字
4. Agent.run() 构造 PlannerContext 时加入 operation_hints
5. LLMPlanner prompt 写入 Parsed operation hints
6. 增加单元测试
7. 重新跑真实 API smoke test
```

## 后续实现结果：operation hints fast path

实现 `parse_operation_hints()` 后，系统会先对当前用户任务做轻量规则解析：

```text
把上一步的结果减 12
```

解析为：

```json
{
  "intent": "arithmetic_transform",
  "reference": "previous_result",
  "operator": "-",
  "operand": "12",
  "raw_text": "把上一步的结果减 12"
}
```

如果同时满足：

- `PlannerContext` 中存在 prior result
- 当前任务解析出了 `OperationHint`
- `calculator` 工具可用

那么 `LLMPlanner` 会走确定性 fast path，直接生成：

```json
{
  "tool": "calculator",
  "args": {
    "expression": "100 - 12"
  }
}
```

这一步不再让模型猜中文“减 / 除以”的语义，而是把确定性运算交给代码处理。

真实 API smoke test 结果：

```text
zh_add:       3 * 7  -> 刚才的结果加 5   -> 26  PASS
zh_subtract: 50 * 2 -> 上一步的结果减 12 -> 88  PASS
zh_divide:   9 * 5  -> 刚才的结果除以 5 -> 9   PASS
en_multiply: 8      -> multiply that by 3 -> 24 PASS
```

这个结果说明：

```text
对明显的 arithmetic follow-up，结构化 hint + deterministic fast path
比纯 prompt 规则更稳定。
```

## 测试分层

后续每个涉及 LLM 的功能都按两层验证：

```text
单元测试：
使用 FakeLLM，验证代码链路、结构化数据、错误处理。

真实 API smoke test：
调用真实模型，验证 prompt 和模型行为是否能跑通关键路径。
```

这次问题说明：

```text
单元测试通过只能证明框架链路正确；
真实 API smoke test 才能暴露模型理解和 prompt 稳定性问题。
```
