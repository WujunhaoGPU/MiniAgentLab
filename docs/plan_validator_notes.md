# PlanValidator 设计笔记

`PlanValidator` 是放在 `Planner` 和 `Executor` 之间的一层执行前检查。

它目前不负责自动修复计划，只负责判断计划是否值得执行。这样设计是为了把职责拆开：

- `Planner`：生成计划
- `PlanValidator`：发现计划中的结构或语义问题
- `Executor`：只执行已经通过检查的计划
- 后续 `Reflection`：可以根据 Validator 或 Executor 的错误原因，决定是否重新生成计划或修复参数

## 当前检查项

- 计划步数是否超过 `max_steps`
- step 是否引用未知工具
- step id 是否重复
- 当 `OperationHint` 已经解析出“上一轮结果 + 运算符 + 新操作数”时，calculator 表达式是否与 hint 冲突

例如最近对话里有：

```text
Result: 100
```

用户接着说：

```text
subtract 12 from it
```

`OperationHint` 会得到：

```json
{
  "reference": "previous_result",
  "operator": "-",
  "operand": "12"
}
```

这时合理的 calculator 表达式应该包含：

```text
100 - 12
```

如果 Planner 生成 `100 * 12` 或只生成 `12`，`PlanValidator` 会在工具真正执行前拦截。

## 为什么现在不自动修正

自动修正确实可以做，但它属于更高一层的能力。

在工程里通常会先做“可解释的检测”，再做“有边界的修复”。原因是：

- 检测比修复更容易验证，适合先打稳地基
- 自动修复如果做错，可能会静默产生错误结果
- Reflection 需要清楚的错误原因，Validator 正好可以提供结构化 issue

当前 `PlanReflection` 已经会读取 `PlanValidationIssue`，再决定：

- 让 LLM 重新生成计划
- 或在非常确定的场景下自动修正参数
- 或直接失败并把原因返回给用户

第一版已经实现了两种路径：

- `repair_plan`：当错误来自 `operation_hint_conflict` 或 `missing_calculator_expression`，并且 Validator 已经给出 `expected_expression` 时，直接修复 calculator 参数
- `replan`：当错误不适合确定性修复时，把 Validator 的结构化 issue 放进 `PlannerContext.reflection_feedback`，再请求 Planner 重新生成计划
