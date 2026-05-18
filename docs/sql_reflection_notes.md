# SQLReflection 设计笔记

`SQLReflection` 用来处理 SQLite 工具执行阶段暴露的问题。

它和 `PlanValidator` 阶段的 Reflection 不一样：

- `PlanValidator` 发现的是执行前的问题，例如未知工具、计划结构错误
- `SQLReflection` 发现的是工具真实执行后的问题，例如表不存在、列不存在、SQL 语法错误、危险 SQL

## 当前策略

`SQLReflection` 会读取 `ExecutionResult.error` 和失败的 `run_sql` step，然后分类：

- `missing_table`：例如 `no such table: sales`
- `missing_column`：例如 `no such column: o.total`
- `syntax_error`：SQLite 语法错误
- `unsafe_sql`：非只读 SQL 或被 SQLite authorizer 拦截
- `sql_execution_error`：其他 SQL 执行错误

对于 `missing_table`、`missing_column`、`syntax_error` 这类问题，它会返回：

```text
action = "replan"
```

然后把结构化反馈放进 `PlannerContext.reflection_feedback`，让 Planner 重新生成计划。

对于 `unsafe_sql`，它会返回：

```text
action = "fail"
```

原因是危险 SQL 不应该被自动“修成另一个查询”。写库、删库、改库这类意图需要明确拒绝，而不是由 Reflection 静默改写。

## 当前闭环

现在 Agent 的执行顺序是：

```text
Planner
-> PlanValidator
-> Executor
-> SQLReflection if run_sql fails
-> Planner with reflection_feedback
-> PlanValidator
-> Executor
```

一个典型例子：

```text
Planner 生成：SELECT SUM(o.total) FROM orders o
Executor 报错：no such column: o.total
SQLReflection 分类：missing_column
SQLReflection 反馈：先 describe_table，再使用真实字段
Planner 重新生成：SELECT SUM(o.amount) FROM orders o
Executor 成功
```

这一步让 Reflection 真正开始从“真实工具错误”中长出来，而不是只处理我们提前想象出来的错误。
