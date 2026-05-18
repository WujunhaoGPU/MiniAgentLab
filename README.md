# MiniAgentLab：轻量级 Agent 编排框架

MiniAgentLab 是一个半学习、半实践的轻量级 Agent 编排框架项目。它的目标不是一开始就复刻 LangChain、AutoGen 或 CrewAI，而是从一个可运行、可测试、可观察的最小闭环开始，逐步理解并实现 Agent 系统中的核心工程模块。

当前版本已经完成一个最小闭环：

```text
用户任务
-> Planner 生成执行计划
-> Tool Registry 查找工具
-> Executor 调用工具并处理重试
-> Trace Logger 记录执行轨迹
-> Agent 汇总结果
```

## 当前架构图

```mermaid
flowchart TD
    User["用户任务"] --> Agent["Agent"]
    Agent --> Planner["Planner"]
    Planner --> RulePlanner["RuleBasedPlanner"]
    Planner --> LLMPlanner["LLMPlanner"]
    RulePlanner --> Plan["Plan / Steps"]
    LLMPlanner --> Plan
    Plan --> Validator["PlanValidator"]
    Validator -->|valid| Executor["Executor"]
    Validator -->|invalid| Reflection["Reflection"]
    Reflection --> Validator
    Executor --> Guard["max_steps 检查"]
    Guard --> Registry["Tool Registry"]
    Registry --> Tool["Python 工具函数"]
    Tool --> Result["ToolResult"]
    Result --> Executor
    Executor --> Trace["Trace Logger"]
    Trace --> RunTrace["run_id + plan + step logs + final answer"]
    Executor --> Answer["最终结果"]
    Answer --> Agent
```

你可以把这个项目理解为一个 Agent 框架学习实验室：每个模块都尽量小而清楚，方便继续扩展成网页检索 Agent、SQL 分析 Agent、文档问答 Agent 或多工具自动化 Agent。

## 项目定位

MiniAgentLab 主要用于学习和实践以下能力：

- Agent 的任务分解与执行流程
- 函数工具注册与统一调用
- 工具调用失败后的错误处理与重试
- 执行轨迹 Trace 的记录与导出
- 可测试的 Agent 框架设计
- 后续接入 LLM Planner、Memory、Reflection 的工程结构

这个项目适合作为个人项目、简历项目或 Agent 工程学习项目。

## 当前能力

当前版本是 `v0.1.0`，重点是把最小闭环跑通。

已经实现：

- `Agent`：统一协调 Planner、Executor、ToolRegistry 和 TraceLogger
- `RuleBasedPlanner`：基于规则的确定性 Planner，用于测试和最小闭环演示
- `LLMPlanner`：调用 LLM 生成结构化 JSON 计划，并在解析失败时重试修复
- `OpenAICompatibleLLM`：使用标准库封装 OpenAI-compatible chat completions API，可读取 `.env`
- `PlannerContext`：把对话历史等上下文传给 Planner，避免 Planner 直接依赖 Agent 内部状态
- `OperationHint`：对“上一步结果 + 加减乘除”这类 follow-up 指令做确定性解析
- `ShortTermMemory`：保存单次 Agent 运行中的 step 输出，供后续模块读取上下文
- `ConversationMemory`：保存多次 `agent.run()` 之间的 user / assistant 对话历史
- `ToolRegistry`：支持注册 Python 函数工具，并统一返回调用结果
- `Executor`：顺序执行计划步骤，支持失败重试和 `max_steps` 步数上限
- `TraceLogger`：记录任务、`run_id`、计划、每一步工具调用、输出、错误和最终结果
- `calculator` 示例工具：安全执行基础数学表达式
- 单元测试：覆盖工具注册、重复注册、未知工具、参数错误、calculator 异常、Agent 最小闭环执行、`run_id`、`max_steps`、`LLMPlanner`、`PlannerContext`、`OperationHint`、`ShortTermMemory` 和 `ConversationMemory`

后续仍待实现的扩展方向：

> 注：下面几项是项目早期路线记录。当前版本已经实现 SQL 分析 Agent、文档问答 Agent 和网页检索 Agent；最新能力说明见本文后面的“MiniAgentLab 当前版总览”。

- `VectorMemory`：文档检索记忆
- `Reflection`：失败分析、参数修正、重新规划
- SQL 分析 Agent
- 文档问答 Agent
- 网页检索 Agent

## 环境信息

本项目当前使用 Conda 环境：

```powershell
conda activate D:\conda_envs\miniagentlab
```

Python 版本：

```text
Python 3.11.15
```

如果你需要重新创建环境，可以参考：

```powershell
$env:CONDA_PKGS_DIRS="D:\conda_pkgs"
D:\miniconda3\Scripts\conda.exe create -y -p D:\conda_envs\miniagentlab python=3.11 pip
```

## 项目结构

```text
MiniAgentLab/
  miniagentlab/
    __init__.py
    agent.py              # Agent 主协调器
    builtin_tools.py      # 内置工具，例如 calculator
    executor.py           # 执行计划步骤
    llm.py                # OpenAI-compatible LLM 客户端
    memory.py             # 短期记忆与对话记忆
    planner.py            # Planner 抽象、规则 Planner 与 LLMPlanner
    schemas.py            # Plan、Step、PlannerContext、ToolResult 等数据结构
    tool_registry.py      # 工具注册与调用
    trace.py              # 执行轨迹记录与导出
  examples/
    calculator_agent.py   # 最小闭环示例
    llm_planner_agent.py  # LLMPlanner 示例
  tests/
    test_minimal_loop.py  # 单元测试
    test_llm_planner.py   # LLMPlanner 单元测试
    test_memory.py        # ShortTermMemory 单元测试
    test_conversation_memory.py # ConversationMemory 单元测试
  traces/
    calculator_trace.json # 示例运行后生成的 Trace
  pyproject.toml
  .env.example
  README.md
```

## 快速开始

进入项目目录：

```powershell
cd D:\MiniAgentLab
```

激活环境：

```powershell
conda activate D:\conda_envs\miniagentlab
```

运行最小闭环示例：

```powershell
python examples\calculator_agent.py
```

你应该看到类似输出：

```text
Done: 计算 123 * 456，并解释结果
Result: 56088
Trace saved to: traces\calculator_trace.json
```

运行单元测试：

```powershell
python -m unittest discover -s tests
```

预期输出：

```text
Ran 73 tests in 0.683s

OK
```

## 使用 LLMPlanner

如果要让大模型负责生成计划，可以先准备 `.env`。不要把真实 `.env` 提交到 Git。

```powershell
copy .env.example .env
```

然后填写：

```text
DEEPSEEK_API_KEY=你的 key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-v4-flash
```

运行 LLMPlanner 示例：

```powershell
python examples\llm_planner_agent.py
```

这个示例会让 LLM 输出结构化 JSON 计划，再交给现有的 `Executor` 和 `ToolRegistry` 执行。单元测试不会调用真实 API，而是使用 `FakeLLM` 返回固定 JSON，避免测试依赖网络和模型费用。

## 最小闭环示例说明

当前示例任务是：

```text
计算 123 * 456，并解释结果
```

执行流程如下：

```text
1. Agent 接收用户任务
2. RuleBasedPlanner 从任务中提取数学表达式：123 * 456
3. Planner 生成一个 Step，指定调用 calculator 工具
4. Executor 查找 calculator 工具并执行
5. ToolRegistry 返回统一的 ToolResult
6. TraceLogger 记录计划、工具参数、输出、耗时
7. Agent 汇总最终结果
```

对应生成的计划大致如下：

```json
{
  "goal": "计算 123 * 456，并解释结果",
  "steps": [
    {
      "id": "step_1",
      "description": "Evaluate the arithmetic expression.",
      "tool": "calculator",
      "args": {
        "expression": "123 * 456"
      }
    }
  ]
}
```

## 核心模块设计

### Agent

`Agent` 是整个系统的入口，负责串联完整流程：

```text
task -> plan -> execute -> trace -> final answer
```

它不直接关心某个工具怎么实现，也不直接决定任务怎么拆解，而是把职责交给 Planner、Executor 和 ToolRegistry。

### Planner

Planner 负责把用户任务转成结构化计划。

当前实现的是 `RuleBasedPlanner`，它只处理简单计算任务。这个设计的好处是稳定、可测试，适合作为项目第一步。

后续可以增加 `LLMPlanner`：

```text
用户任务
-> Prompt
-> LLM 输出 JSON
-> 校验为 Plan
-> 交给 Executor
```

### Tool Registry

`ToolRegistry` 用于管理工具函数。

它解决三个问题：

- 工具如何注册
- 工具如何按名称查找
- 工具调用失败后如何统一返回错误

示例：

```python
registry = ToolRegistry()
registry.register(calculator, name="calculator")

result = registry.call("calculator", expression="2 + 3 * 4")
```

返回结果统一是：

```python
ToolResult(success=True, output="14", error=None)
```

### Executor

Executor 负责执行计划中的每一个步骤。

它目前支持：

- 顺序执行
- 工具调用
- 失败重试
- 每次尝试写入 Trace

后续可以扩展：

- 最大步骤数限制
- 并行步骤执行
- 条件分支
- 失败后触发 Reflection
- 工具调用超时控制

### Trace Logger

Trace 是 Agent 项目里非常重要的一部分。没有 Trace，Agent 失败时很难知道问题出在哪里。

当前 Trace 会记录：

- 用户任务
- 开始时间
- 执行计划
- 每一步工具调用
- 工具参数
- 工具输出
- 错误信息
- 单步耗时
- 最终答案
- 结束时间

示例文件：

```text
traces/calculator_trace.json
```

## 为什么保留 RuleBasedPlanner

这个项目第一步故意使用 `RuleBasedPlanner`，而不是马上依赖大模型。

原因是：

- 规则 Planner 稳定，方便写测试
- 可以先验证 Agent 框架本身是否合理
- 避免一开始把错误来源混在一起
- 接入 LLM 时，只需要替换 Planner，不需要重写整个框架

一个成熟的 Agent 框架应该能做到：

```text
同一个 Executor + ToolRegistry + TraceLogger
既能跑 RuleBasedPlanner
也能跑 LLMPlanner
```

这也是当前架构的核心设计思想。

## 后续开发路线

### 第 1 阶段：完善最小框架

目标：让当前框架更稳。

已完成任务：

- 增加更多 calculator 异常测试
- 增加未知工具调用测试
- 增加工具参数错误测试
- 给 Trace 增加 `run_id`
- 给 Executor 增加 `max_steps`
- 给 README 增加架构图

### 第 2 阶段：接入 LLMPlanner

目标：让大模型根据用户任务生成计划。

已完成基础接入：

- 新增 `miniagentlab/llm.py`
- 从 `.env` 读取 `LLM_BASE_URL`、`LLM_MODEL`、`DEEPSEEK_API_KEY`
- 新增 `LLMPlanner`
- 要求 LLM 只输出 JSON
- 对 JSON 做格式校验
- JSON 解析失败时自动重试一次
- 使用 `FakeLLM` 编写不依赖真实 API 的单元测试
- 新增 `examples/llm_planner_agent.py`

注意事项：

- 不要把 API Key 写进 README 或提交到 Git
- `.env` 已经被 `.gitignore` 忽略
- LLM 输出一定要校验，不能直接相信

### 第 3 阶段：实现 Memory

目标：让 Agent 能保存上下文。

已完成简单版本：

```text
ShortTermMemory
-> 保存当前任务中的中间结果
-> 每次 agent.run() 开始时清空
-> 每个成功 step 的输出会写入 memory[step_id]
-> 后续 step 可以用 "$memory.step_id" 引用前面 step 的输出
-> AgentResult.memory 会返回本次运行的 memory snapshot

ConversationMemory
-> 保存多轮对话历史
-> 不会在每次 agent.run() 开始时清空
-> Agent 会自动记录 user task 和 assistant final_answer
-> AgentResult.conversation 会返回截至本次运行的对话历史

PlannerContext
-> Agent 在规划前读取当前任务之前的 ConversationMemory
-> LLMPlanner 只取最近 N 轮 conversation 写入 prompt
-> 当前 user task 仍然通过 task 单独传入，避免在 prompt 中重复

OperationHint
-> Agent 对当前 task 做轻量规则解析
-> 识别“刚才/上一步/previous/that”等引用词和加减乘除操作
-> 当存在 prior result + operation hint + calculator 工具时，LLMPlanner 会走确定性 fast path
-> 例如 prior result=100，hint operator="-", operand="12"，直接生成 expression "100 - 12"
```

示例计划：

```json
{
  "goal": "复用前一步结果",
  "steps": [
    {
      "id": "step_1",
      "description": "计算数值",
      "tool": "calculator",
      "args": {"expression": "3 * 7"}
    },
    {
      "id": "step_2",
      "description": "使用前一步结果",
      "tool": "label_value",
      "args": {"value": "$memory.step_1"}
    }
  ]
}
```

当前规则：

- 只有完整字符串形式的 `"$memory.step_1"` 会被替换
- `dict` 和 `list` 中的引用会递归解析
- 引用不存在时，当前 step 会失败并写入 Trace

后续再考虑：

- SQLite 持久化
- 文档 chunk 存储
- 向量检索
- 记忆摘要

### 第 4 阶段：实现 Reflection

目标：让 Agent 在失败后有修正能力。

典型场景：

```text
工具调用失败
-> Reflection 分析错误
-> 修改参数
-> 重试工具
```

Reflection 不应该只是生成一段自然语言，而应该输出结构化动作：

```json
{
  "action": "retry_with_new_args",
  "reason": "参数 expression 中包含非法字符",
  "new_args": {
    "expression": "123 * 456"
  }
}
```

### 第 5 阶段：做 SQL 分析 Agent

目标：让 Agent 能分析本地 SQLite 数据库。

建议工具：

- `list_tables`
- `describe_table`
- `run_sql`

安全限制：

- 第一版只允许 `SELECT`
- 禁止 `DROP`、`DELETE`、`UPDATE`、`INSERT`
- 给 SQL 查询设置行数上限

这个示例很适合展示 Agent 的工具编排能力。

### 第 6 阶段：做文档问答 Agent

目标：让 Agent 能读取本地文档并回答问题。

建议流程：

```text
load_document
-> chunk_text
-> retrieve_chunks
-> answer_question
```

第一版可以先用关键词匹配，后续再接 embedding。

### 第 7 阶段：做网页检索 Agent

目标：让 Agent 能搜索网页、抓取页面、总结信息并给出来源。

建议工具：

- `search_web`
- `fetch_page`
- `extract_text`
- `summarize`

注意事项：

- 网络请求容易失败，要做好异常处理
- 需要记录来源 URL
- 总结时要区分事实和模型推断

## 常见问题与解决思路

### 1. LLM 输出格式不稳定

解决方法：

- 要求只输出 JSON
- 用数据结构校验
- 失败时让模型修复 JSON
- 保留原始输出到 Trace，方便排查

### 2. Agent 无限重试

解决方法：

- 设置 `max_retries`
- 设置 `max_steps`
- 设置 `max_reflections`
- 每次失败都写入 Trace

### 3. 工具参数不匹配

解决方法：

- 注册工具时读取函数签名
- 调用前校验参数
- 错误信息标准化

### 4. Trace 太乱

解决方法：

- 每个 Agent run 增加 `run_id`
- 每个 Step 增加稳定的 `step_id`
- 工具输入输出都转成 JSON 可序列化格式
- 大文本输出只保存摘要或截断版本

### 5. 项目容易变成“套壳”

解决方法：

- 不要只调用现成 Agent 框架
- 重点实现自己的编排逻辑
- 重点展示 ToolRegistry、Executor、Trace、Retry、Reflection
- README 中解释每个模块为什么这样设计

## 简历描述参考

如果作为简历项目，可以这样描述：

```text
MiniAgentLab：轻量级 Agent 编排框架

- 实现 Planner、Tool Registry、Executor、Trace Logger 等核心模块，支持函数工具注册、任务分解、顺序执行、失败重试与执行轨迹导出。
- 构建 calculator 最小闭环示例，完成从用户任务、计划生成、工具调用到 Trace 记录的完整 Agent 执行流程。
- 使用单元测试覆盖工具注册、重复注册、Agent 执行闭环等关键逻辑，为后续 LLMPlanner、Memory、Reflection 和多类型 Agent 示例扩展预留接口。
```

后续实现 SQL、文档问答、网页检索后，可以升级为：

```text
- 提供 SQL 分析 Agent、文档问答 Agent、网页检索 Agent 示例，覆盖结构化数据分析、非结构化文档检索和外部信息获取等典型 Agent 应用场景。
```

## 当前状态

当前项目已经可以：

- 创建并使用 Conda 环境
- 运行 calculator Agent 示例
- 生成执行 Trace
- 运行单元测试

下一步推荐优先做：

> 注：这里也是早期阶段规划。当前已完成 LLMPlanner、Memory、Reflection、SQL Agent、Document QA Agent 和 Web Search Agent；后续更适合继续做 DocumentReflection、WebReflection 和搜索 Provider 抽象。

```text
LLMPlanner -> Memory -> Reflection -> SQL Agent
```

这样项目会从“最小闭环”逐步变成真正有展示价值的 Agent 编排框架。
## SQLite 分析 Agent 第一版

当前已经加入本地 SQLite 只读分析能力：

- `miniagentlab/sql_tools.py`
- `examples/sql_agent.py`
- `tests/test_sql_tools.py`
- `tests/test_sql_agent.py`

第一版支持：

- `list_tables(db_path)`：查看用户表
- `describe_table(db_path, table_name)`：查看表结构
- `run_sql(db_path, sql, max_rows=50)`：执行单条只读 `SELECT/WITH` 查询
- 拒绝 `DELETE`、`UPDATE`、`DROP`、多语句 SQL 等危险操作

运行示例：

```powershell
python examples\sql_agent.py
```

当前完整测试：

```text
Ran 73 tests in 0.621s
OK
```
# MiniAgentLab 当前版总览

MiniAgentLab 是一个半学习、半实践的轻量级 Agent 编排框架。它不是为了复刻 LangChain、AutoGen 或 CrewAI，而是用尽量少的代码把 Agent 工程里的关键环节做清楚：

```text
Planner -> PlanValidator -> Executor -> Reflection -> Memory -> Trace
```

当前项目已经包含四类可运行 Agent 示例：

- Calculator Agent：最小闭环与工具调用示例
- SQL 分析 Agent：本地 SQLite 只读分析与 SQLReflection
- Document QA Agent：本地文档问答与轻量 RAG
- Web Search Agent：网页检索、页面抓取、正文抽取与摘要

当前完整测试：

```text
Ran 73 tests
OK
```

## 当前架构

```mermaid
flowchart TD
    User["用户任务"] --> Agent["Agent"]
    Agent --> Planner["Planner / LLMPlanner"]
    Planner --> Plan["Plan / Steps"]
    Plan --> Validator["PlanValidator"]
    Validator -->|valid| Executor["Executor"]
    Validator -->|invalid| Reflection["PlanReflection"]
    Reflection --> Planner
    Executor --> ToolRegistry["ToolRegistry"]
    ToolRegistry --> Tools["Python Tools"]
    Tools --> Executor
    Executor -->|success| Memory["ShortTermMemory"]
    Executor -->|failure| ExecReflection["Execution Reflection / SQLReflection"]
    ExecReflection --> Planner
    Agent --> Conversation["ConversationMemory"]
    Agent --> Trace["TraceLogger"]
```

核心设计原则：

- 工具只是普通 Python 函数，通过 `ToolRegistry` 注册。
- Planner 只生成结构化 `Plan`，不直接执行工具。
- Executor 只负责顺序执行、重试、记录 trace 和写入短期记忆。
- Reflection 不做玄学自省，而是根据结构化错误决定修复、重规划或失败。
- 单元测试使用本地、可复现的数据；真实 API 只用于 smoke test。

## 已实现模块

| 模块 | 文件 | 作用 |
| --- | --- | --- |
| Agent 主流程 | `miniagentlab/agent.py` | 协调规划、校验、执行、反思、记忆和 trace |
| Planner | `miniagentlab/planner.py` | `RuleBasedPlanner` 与 `LLMPlanner` |
| Tool Registry | `miniagentlab/tool_registry.py` | 注册和调用 Python 工具 |
| Executor | `miniagentlab/executor.py` | 执行计划步骤、处理重试、记录失败 step |
| Memory | `miniagentlab/memory.py` | 支持 `$memory.step_id` 和 `$memory.step_id.field` 引用 |
| PlanValidator | `miniagentlab/validator.py` | 校验未知工具、步数、重复 step、错误 memory 引用等 |
| Reflection | `miniagentlab/reflection.py` | 处理计划校验失败和默认执行失败 |
| SQLReflection | `miniagentlab/sql_reflection.py` | 处理 SQL 执行错误并触发 replan |
| Trace | `miniagentlab/trace.py` | 记录 run_id、plan、step、输出、错误和最终答案 |
| LLM Client | `miniagentlab/llm.py` | OpenAI-compatible Chat Completions 调用 |

## 工具与 Agent 示例

### 1. Calculator Agent

文件：

- `miniagentlab/builtin_tools.py`
- `examples/calculator_agent.py`
- `tests/test_minimal_loop.py`

能力：

- 安全计算基础数学表达式
- 验证 ToolRegistry、Executor、TraceLogger 的最小闭环
- 作为后续 Memory、Reflection、LLMPlanner 的基准场景

运行：

```powershell
python examples\calculator_agent.py
```

### 2. SQL 分析 Agent

文件：

- `miniagentlab/sql_tools.py`
- `miniagentlab/sql_reflection.py`
- `examples/sql_agent.py`
- `tests/test_sql_tools.py`
- `tests/test_sql_agent.py`
- `tests/test_sql_reflection.py`

工具：

```text
list_tables(db_path)
describe_table(db_path, table_name)
run_sql(db_path, sql, max_rows=50)
```

能力：

- 查看本地 SQLite 数据库中的用户表
- 查看表结构
- 执行单条只读 `SELECT/WITH`
- 拒绝 `DELETE`、`UPDATE`、`DROP`、多语句 SQL
- 使用 SQLite authorizer 作为第二层只读保护
- 当 SQL 执行失败时，`SQLReflection` 可以识别错误并触发重规划

SQLReflection 当前支持：

```text
missing_table
missing_column
syntax_error
unsafe_sql
sql_execution_error
```

典型闭环：

```text
Planner 写错字段 total
-> run_sql 报 no such column: total
-> SQLReflection 分类为 missing_column
-> Planner 收到 reflection_feedback
-> 重新生成使用 amount 字段的 SQL
-> Executor 执行成功
```

运行：

```powershell
python examples\sql_agent.py
```

### 3. Document QA Agent

文件：

- `miniagentlab/document_tools.py`
- `examples/document_qa_agent.py`
- `examples/docs/miniagentlab_notes.md`
- `tests/test_document_tools.py`
- `tests/test_document_qa_agent.py`
- `docs/document_qa_notes.md`

工具：

```text
load_document(path)
chunk_document(document, chunk_size=500, overlap=80)
index_chunks(chunks, store_id=None)
retrieve_chunks(store_id, query, top_k=3)
answer_question(question, chunks)
```

第一版支持 `.txt` 和 `.md`。为了保持项目精简，当前没有引入 Chroma、FAISS、sentence-transformers 或 embedding API，而是使用进程内内存索引和轻量词频向量。

为了在不增加依赖的情况下提升 RAG 质量，已经做了三处轻量优化：

- 标题/段落感知切片：保留 Markdown heading 到 chunk metadata
- hybrid 检索打分：结合 cosine、关键词重合、标题命中和短语命中
- 句子级回答：从检索片段中选最相关证据句，而不是直接拼接整个 chunk

典型计划：

```json
{
  "steps": [
    {"id": "step_1", "tool": "load_document", "args": {"path": "examples/docs/miniagentlab_notes.md"}},
    {"id": "step_2", "tool": "chunk_document", "args": {"document": "$memory.step_1"}},
    {"id": "step_3", "tool": "index_chunks", "args": {"chunks": "$memory.step_2", "store_id": "notes"}},
    {"id": "step_4", "tool": "retrieve_chunks", "args": {"store_id": "$memory.step_3.store_id", "query": "What does Reflection do?"}},
    {"id": "step_5", "tool": "answer_question", "args": {"question": "What does Reflection do?", "chunks": "$memory.step_4"}}
  ]
}
```

运行：

```powershell
python examples\document_qa_agent.py
```

当前本地输出示例：

```text
Reflection analyzes failures from validation or tool execution.
```

### 4. Web Search Agent

文件：

- `miniagentlab/web_tools.py`
- `examples/web_search_agent.py`
- `tests/test_web_tools.py`
- `tests/test_web_search_agent.py`
- `docs/web_search_notes.md`

工具：

```text
search_web(query, max_results=5, search_url=None)
fetch_page(url, timeout=10)
extract_text(page)
summarize_text(text, query, max_sentences=3)
```

能力：

- 从搜索结果页解析标题和 URL
- 抓取 `http/https/file` 页面
- 从 HTML 中抽取可读正文
- 跳过 `script/style/noscript`
- 基于 query 做句子级摘要
- 支持 `$memory.step_1.0.url` 从搜索结果列表中取第一条 URL

重要说明：

当前单元测试和示例使用本地 `file://` HTML 页面模拟搜索结果。这是为了保证测试稳定、可复现，不受真实搜索引擎反爬、结果变化、网络超时影响。

`search_web` 默认实现写了 DuckDuckGo HTML 入口：

```text
https://duckduckgo.com/html/?q=...
```

但真实搜索应该作为 smoke test，而不是单元测试依赖。当前已经验证过 LLMPlanner 能生成完整网页检索工具链：

```text
search_web -> fetch_page -> extract_text -> summarize_text
```

运行本地示例：

```powershell
python examples\web_search_agent.py
```

输出示例：

```text
Reflection analyzes failed plans and tool execution errors.
```

## Memory 引用规则

Agent 的 step 之间通过 `ShortTermMemory` 传递结果。

支持：

```text
$memory.step_1
$memory.step_3.store_id
$memory.step_1.0.url
```

含义：

- `$memory.step_1`：引用整个 step 输出
- `$memory.step_3.store_id`：引用 step 输出 dict 中的字段
- `$memory.step_1.0.url`：引用 step 输出 list 的第 0 个元素中的 url 字段

不支持：

```text
$step_1.result
$steps.step_1
```

`PlanValidator` 会提前拦截这类错误引用，避免执行到工具层才失败。

## Smoke Test 记录

这个项目区分两类测试：

- 单元测试：稳定、离线、可重复
- smoke test：真实跑一遍关键链路，尽早暴露工程问题

已经做过的 smoke test：

| 场景 | 结果 |
| --- | --- |
| LLMPlanner 多轮 calculator | 通过，支持“把刚才结果加 5” |
| SQLReflection 真实 API | 通过，`no such column` 后 replan |
| Document QA LLMPlanner | 通过，生成完整文档问答工具链 |
| Web Search LLMPlanner | 通过，生成完整网页检索工具链 |

## Coding 中遇到的问题与修复

### 1. 单元测试没有暴露 LLM prompt 问题

问题：

单元测试使用 `FakeLLM`，只能验证框架逻辑，不能验证真实模型是否理解“刚才的结果”“上一步”等表达。

修复：

- 增加真实 API smoke test
- 引入 `ConversationMemory`
- 引入 `PlannerContext`
- 引入 `OperationHint`
- 对高确定性 arithmetic follow-up 使用 fast path

### 2. prompt 过度针对具体例子

问题：

一开始为了让模型理解“刚才结果加 5”，prompt 写得很具体，工程泛化性不足。

修复：

- 把自然语言提示改为结构化 `operation_hints`
- LLMPlanner 优先使用结构化 hint
- 再用 PlanValidator 检查计划是否违背 hint

### 3. LLM 生成错误 memory 引用

问题：

文档问答真实 API smoke test 中，模型生成了：

```text
$step_1.result
```

但框架约定是：

```text
$memory.step_1
```

修复：

- LLMPlanner prompt 明确 memory 引用语法
- PlanValidator 新增 `invalid_memory_reference`
- 错误引用在执行前被拦截

### 4. LLM 传了整个 dict，而不是字段

问题：

`index_chunks` 返回：

```json
{"store_id": "doc_smoke", "chunk_count": 1}
```

LLM 把 `$memory.step_3` 传给 `retrieve_chunks.store_id`，导致工具收到 dict。

修复：

- `ShortTermMemory` 支持嵌套引用
- 使用 `$memory.step_3.store_id`
- 同时支持 list index，如 `$memory.step_1.0.url`

### 5. SQLite 临时文件在 Windows 上无法删除

问题：

测试中使用 `with sqlite3.connect(path) as connection:` 后，Windows 删除临时数据库失败。

原因：

sqlite3 connection 的 context manager 管事务，不自动 close。

修复：

- 所有 SQLite 连接都显式 `connection.close()`

### 6. SQL 工具不能只靠字符串判断安全

问题：

只用字符串判断 `SELECT` 不够稳。

修复：

- 第一层：只允许单条 `SELECT/WITH`
- 第二层：SQLite `set_authorizer` 拦截写操作

### 7. SQLReflection 不能自动修复危险 SQL

问题：

如果用户或 Planner 生成 `DELETE/UPDATE/DROP`，不应该由 Reflection 静默改成别的查询。

修复：

- `unsafe_sql` 直接失败
- 只有 `missing_table`、`missing_column`、`syntax_error` 等进入 replan

### 8. 文档切片质量影响答案质量

问题：

固定字符切片会把标题、段落和句子切乱，答案像“整块摘录”。

修复：

- Markdown heading/paragraph aware chunking
- hybrid scoring
- sentence-level answer selection

### 9. 网页检索示例一开始不是绝对 file URI

问题：

`Path.as_uri()` 不能用于相对路径。

修复：

- 示例中使用 `.resolve()` 转为绝对路径

### 10. 网页摘要重复标题

问题：

HTML title、h1 和正文混在一起，摘要出现重复标题。

修复：

- HTML block tag 作为文本边界
- 摘要时过滤过短标题句
- query-aware sentence ranking

### 11. 真实 API smoke test 可能超时

问题：

SQLReflection 第一次真实 API smoke test 遇到 API 读取超时。

修复：

- 保留单元测试为离线稳定验证
- smoke test 缩小输入和 prompt
- 对真实 API 结果只做关键断言，不依赖长输出

## 后续路线

建议接下来做：

1. WebReflection
   - 搜索无结果时改写 query
   - 抓取失败时换下一个结果
   - 页面正文过短时继续尝试其他搜索结果

2. DocumentReflection
   - 检索为空时改写 query
   - 检索分数过低时扩大 `top_k`
   - chunk 参数不合适时调整切片

3. Prompt Profile
   - `LLMPlanner` 支持 SQL / Document QA / Web Search 专用 instructions
   - 不急着做复杂 Router，先保持显式选择 Agent 示例

4. 真实搜索 Provider 抽象
   - `DuckDuckGoHTMLProvider`
   - `MockSearchProvider`
   - 后续可换 Tavily、SerpAPI、Bing API

5. 更强文档检索
   - 支持 PDF / DOCX
   - 接 embedding API 或 sentence-transformers
   - 向量库持久化
