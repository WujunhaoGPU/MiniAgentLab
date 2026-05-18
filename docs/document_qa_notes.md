# Document QA Agent 设计笔记

文档问答 Agent 第一版采用轻量本地 RAG 闭环，重点验证 MiniAgentLab 的工具编排能力，而不是追求最强检索效果。

## 当前工具链

```text
load_document
-> chunk_document
-> index_chunks
-> retrieve_chunks
-> answer_question
```

所有工具都注册进 `ToolRegistry`，由普通 `Agent` 执行。示例里使用 `$memory.step_x` 把上一步输出传给下一步：

```text
load_document -> $memory.step_1
chunk_document -> $memory.step_2
index_chunks -> $memory.step_3
retrieve_chunks -> $memory.step_4
answer_question -> final answer
```

## 第一版取舍

- 只支持 `.txt` 和 `.md`
- 使用进程内内存向量库
- 使用词频向量和 cosine similarity
- 使用 Markdown 标题/段落感知切片
- 检索采用轻量 hybrid score：cosine、关键词重合、标题命中和短语命中
- 回答阶段使用句子级排序，而不是直接拼接整个 chunk
- `answer_question` 只基于检索片段做证据式回答，不调用 LLM
- 显式传递 `store_id`，避免隐式“当前索引”状态
- 支持 `$memory.step_id.field` 这类嵌套字段引用，例如 `$memory.step_3.store_id`

## 后续优化方向

- 支持 PDF / DOCX
- 增加 embedding API 或 sentence-transformers
- 向量库持久化
- 增量索引
- `answer_question` 接入 LLM
- 增加 `DocumentReflection`：
  - 没有检索结果时改写 query
  - 回答没有 sources 时失败
  - chunk 太短或太长时调整 chunk 参数
  - 检索分数太低时扩大 `top_k`
