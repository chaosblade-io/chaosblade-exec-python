# HTTPX 插件使用手册

## 概述

HTTPX 插件通过拦截 `httpx._client.AsyncClient.send` 方法，对使用 `httpx` 库发起的异步 HTTP 请求注入故障。适用于使用 `httpx`、`openai`、`langchain-openai` 等库的 Python 应用（这些库底层均使用 httpx 进行 HTTP 通信）。

## 拦截点

| 属性 | 值 |
|------|------|
| 目标模块 | `httpx._client` |
| 目标类 | `AsyncClient` |
| 目标方法 | `send` |
| target 参数 | `httpx` |

## 匹配器（Matcher）

| 参数名 | 说明 | 示例 |
|--------|------|------|
| `url` | 完整请求 URL | `https://api.openai.com/v1/chat/completions` |
| `method` | HTTP 方法（大写） | `GET`, `POST` |
| `host` | 目标主机名 | `dashscope.aliyuncs.com`, `api.openai.com` |
| `path` | URL 路径 | `/v1/chat/completions` |

> 匹配器为可选参数，不指定时对所有 httpx 异步请求生效。多个匹配器同时指定时，需全部满足才会触发注入。

## 支持的故障类型

### 1. 延迟注入（delay）

对 HTTP 异步请求注入指定时长的延迟。

**参数：**

| 参数名 | 必填 | 说明 |
|--------|------|------|
| `time` | 是 | 延迟时长（毫秒） |
| `offset` | 否 | 随机偏移范围（毫秒） |

**示例：**

```bash
# 对 DashScope LLM 调用注入 3000ms 延迟
curl "http://127.0.0.1:9526/create?suid=httpx-delay-001&target=httpx&action=delay&time=3000&host=dashscope.aliyuncs.com"

# 对 OpenAI API 注入 5000ms 延迟
curl "http://127.0.0.1:9526/create?suid=httpx-delay-002&target=httpx&action=delay&time=5000&host=api.openai.com"

# 仅对 chat completions 路径注入延迟
curl "http://127.0.0.1:9526/create?suid=httpx-delay-003&target=httpx&action=delay&time=2000&path=/v1/chat/completions"
```

### 2. 异常注入（throwCustomException）

对 HTTP 异步请求抛出指定异常。

**参数：**

| 参数名 | 必填 | 说明 |
|--------|------|------|
| `exception` | 否 | 异常类名（如 `ConnectError`, `TimeoutException`, `RuntimeError`） |
| `exception-message` | 否 | 异常消息内容 |

**示例：**

```bash
# 模拟 LLM 服务连接异常
curl "http://127.0.0.1:9526/create?suid=httpx-exc-001&target=httpx&action=throwCustomException&exception=ConnectError&exception-message=chaos:+LLM+service+connection+refused&host=dashscope.aliyuncs.com"

# 模拟所有 httpx 请求超时
curl "http://127.0.0.1:9526/create?suid=httpx-exc-002&target=httpx&action=throwCustomException&exception=TimeoutException&exception-message=chaos:+request+timeout"

# 仅对 POST 请求注入异常
curl "http://127.0.0.1:9526/create?suid=httpx-exc-003&target=httpx&action=throwCustomException&exception=RuntimeError&exception-message=chaos:+write+failure&method=POST"
```

### 3. 返回值篡改（returnValue）

覆盖 HTTP 异步请求的返回值。

**参数：**

| 参数名 | 必填 | 说明 |
|--------|------|------|
| `return-value` | 否 | 返回值内容 |

> **注意：** httpx `AsyncClient.send` 正常返回 `httpx.Response` 对象。`returnValue` 直接替换返回值，上层 SDK（如 openai）处理非 Response 对象时通常会抛出 `AttributeError`，适合验证应用的错误处理逻辑。

**示例：**

```bash
# 返回自定义错误 JSON（会导致 openai SDK 解析失败）
curl "http://127.0.0.1:9526/create?suid=httpx-ret-001&target=httpx&action=returnValue&return-value=%7B%22error%22%3A%22service+unavailable%22%7D&host=dashscope.aliyuncs.com"

# 返回 null
curl "http://127.0.0.1:9526/create?suid=httpx-ret-002&target=httpx&action=returnValue&return-value=null"
```

## 恢复（销毁实验）

```bash
curl "http://127.0.0.1:9526/destroy?suid=httpx-delay-001"
```

## 查看实验状态

```bash
curl "http://127.0.0.1:9526/status?suid=httpx-delay-001"
```

返回示例：
```json
{"code": 200, "result": "{\"count\": 12}"}
```

## 高级用法

### 按路径精确注入

```bash
# 仅对 embeddings 接口注入故障，chat 接口不受影响
curl "http://127.0.0.1:9526/create?suid=httpx-path-001&target=httpx&action=throwCustomException&exception=ConnectError&exception-message=embeddings+service+down&path=/v1/embeddings"
```

### 限制注入次数

```bash
# 前 3 次 LLM 调用注入异常（验证重试机制）
curl "http://127.0.0.1:9526/create?suid=httpx-limit-001&target=httpx&action=throwCustomException&exception=ConnectError&exception-message=intermittent+failure&host=dashscope.aliyuncs.com&effect-count=3"
```

### 按概率注入

```bash
# 30% 概率对 LLM 请求注入 2s 延迟
curl "http://127.0.0.1:9526/create?suid=httpx-pct-001&target=httpx&action=delay&time=2000&host=dashscope.aliyuncs.com&effect-percent=30"
```

## 典型场景

| 场景 | 命令 |
|------|------|
| 模拟 LLM 服务不可达 | `target=httpx&action=throwCustomException&exception=ConnectError&host=dashscope.aliyuncs.com` |
| 模拟 LLM 响应超时 | `target=httpx&action=delay&time=30000&host=api.openai.com` |
| 验证 LLM 重试机制 | `target=httpx&action=throwCustomException&effect-count=2&host=dashscope.aliyuncs.com` |
| 模拟 Embeddings 失败 | `target=httpx&action=throwCustomException&path=/v1/embeddings` |

## 适用的 Python 库

以下库底层使用 httpx，均可通过本插件注入：

| 库 | 说明 |
|----|------|
| `httpx` | 异步 HTTP 客户端 |
| `openai` | OpenAI Python SDK（v1+） |
| `langchain-openai` | LangChain 的 OpenAI 集成 |
| `dashscope` | 阿里云 DashScope SDK |
| 其他基于 httpx 的 SDK | 任何使用 httpx.AsyncClient 的库 |
