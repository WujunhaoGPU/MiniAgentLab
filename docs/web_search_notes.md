# Web Search Agent 设计笔记

网页检索 Agent 第一版保持无额外依赖，使用 Python 标准库完成最小闭环。

## 当前工具链

```text
search_web
-> fetch_page
-> extract_text
-> summarize_text
```

所有工具都注册进 `ToolRegistry`，由普通 `Agent` 编排。示例使用 `$memory.step_1.0.url` 从搜索结果列表里取第一条 URL。

## 第一版取舍

- `search_web` 默认使用 DuckDuckGo HTML 页面，不需要搜索 API Key
- 测试和示例使用本地 `file://` 搜索结果，避免依赖外网
- `fetch_page` 支持 `http/https/file` 和普通本地路径
- `extract_text` 使用 `HTMLParser`，跳过 `script/style/noscript`
- `summarize_text` 使用 query-aware sentence ranking，不调用 LLM

## 后续优化方向

- 增加真实搜索 smoke test
- 支持 robots / rate limit / timeout 策略
- 增加网页正文抽取质量优化
- 增加 `WebReflection`：
  - 搜索无结果时改写 query
  - 抓取超时或 404 时换下一个结果
  - 页面正文过短时尝试其他结果
  - 摘要为空时降低过滤阈值或重新检索
