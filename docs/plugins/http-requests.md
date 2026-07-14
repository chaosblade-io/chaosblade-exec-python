# HTTP/Requests 插件使用手册

## 概述

HTTP/Requests 插件通过拦截 `requests.adapters.HTTPAdapter.send` 方法，对使用 `requests` 库发起的 HTTP 请求注入故障。适用于所有使用 `requests` 库的 Python 应用。

## 拦截点

| 属性 | 值 |
|------|------|
| 目标模块 | `requests.adapters` |
| 目标类 | `HTTPAdapter` |
| 目标方法 | `send` |
| target 参数 | `http` |

> **注意：** target 参数是 `http`，不是 `requests`。

## 匹配器（Matcher）

| 参数名 | 说明 | 示例 |
|--------|------|------|
| `url` | 完整请求 URL | `http://api.example.com/users` |
| `method` | HTTP 方法（大写） | `GET`, `POST`, `PUT`, `DELETE` |
| `host` | 目标主机名 | `api.example.com` |

> 匹配器为可选参数，不指定时对所有 HTTP 请求生效。多个匹配器同时指定时，需全部满足才会触发注入。

## 支持的故障类型

### 1. 延迟注入（delay）

对 HTTP 请求注入指定时长的延迟。

**参数：**

| 参数名 | 必填 | 说明 |
|--------|------|------|
| `time` | 是 | 延迟时长（毫秒） |
| `offset` | 否 | 随机偏移范围（毫秒） |

**示例：**

```bash
# 对所有 HTTP 请求注入 300ms 延迟
curl "http://127.0.0.1:9526/create?suid=http-delay-001&target=http&action=delay&time=300"

# 对指定主机的 POST 请求注入 2000ms 延迟
curl "http://127.0.0.1:9526/create?suid=http-delay-002&target=http&action=delay&time=2000&host=payment-service.internal&method=POST"
```

### 2. 异常注入（throwCustomException）

对 HTTP 请求抛出指定异常。

**参数：**

| 参数名 | 必填 | 说明 |
|--------|------|------|
| `exception` | 否 | 异常类名（如 `ConnectionError`, `Timeout`, `RuntimeError`） |
| `exception-message` | 否 | 异常消息内容 |

**示例：**

```bash
# 对所有 HTTP 请求抛出 ConnectionError
curl "http://127.0.0.1:9526/create?suid=http-exc-001&target=http&action=throwCustomException&exception=ConnectionError&exception-message=chaos:+network+unreachable"

# 仅对指定主机抛出异常
curl "http://127.0.0.1:9526/create?suid=http-exc-002&target=http&action=throwCustomException&exception=RuntimeError&exception-message=chaos:+service+unavailable&host=target-api.com"
```

### 3. 返回值篡改（returnValue）

覆盖 HTTP 请求的返回值。

**参数：**

| 参数名 | 必填 | 说明 |
|--------|------|------|
| `return-value` | 否 | 返回值内容 |

> **注意：** `returnValue` 直接替换 `HTTPAdapter.send` 的返回值。调用方（如 `requests.get()`）期望获得 `Response` 对象，返回非标准对象可能导致上层代码出错，适合验证错误处理逻辑。

**示例：**

```bash
# 返回自定义 JSON 响应
curl "http://127.0.0.1:9526/create?suid=http-ret-001&target=http&action=returnValue&return-value=%7B%22status%22%3A+%22mocked%22%7D"

# 返回 null
curl "http://127.0.0.1:9526/create?suid=http-ret-002&target=http&action=returnValue&return-value=null"
```

## 恢复（销毁实验）

```bash
curl "http://127.0.0.1:9526/destroy?suid=http-delay-001"
```

## 查看实验状态

```bash
curl "http://127.0.0.1:9526/status?suid=http-delay-001"
```

## 高级用法

### 按主机名精确注入

```bash
# 仅对 payment-service 的请求注入故障，不影响其他服务调用
curl "http://127.0.0.1:9526/create?suid=http-host-001&target=http&action=throwCustomException&exception=ConnectionError&exception-message=payment+service+down&host=payment-service.internal"
```

### 按 HTTP 方法过滤

```bash
# 仅对 POST 请求注入延迟（读请求不受影响）
curl "http://127.0.0.1:9526/create?suid=http-method-001&target=http&action=delay&time=3000&method=POST"
```

### 限制注入次数

```bash
# 前 5 次请求注入异常，之后恢复正常
curl "http://127.0.0.1:9526/create?suid=http-limit-001&target=http&action=throwCustomException&exception=ConnectionError&exception-message=intermittent+failure&effect-count=5"
```

## 典型场景

| 场景 | 命令 |
|------|------|
| 模拟第三方 API 不可达 | `target=http&action=throwCustomException&exception=ConnectionError&host=api.third-party.com` |
| 模拟接口响应慢 | `target=http&action=delay&time=5000&host=slow-service.internal` |
| 模拟写请求超时 | `target=http&action=delay&time=30000&method=POST` |
| 验证重试机制 | `target=http&action=throwCustomException&effect-count=2` |

## 与 HTTPX 插件的区别

| 对比项 | HTTP/Requests 插件 | HTTPX 插件 |
|--------|-------------------|-----------|
| target 参数 | `http` | `httpx` |
| 目标库 | `requests` | `httpx` |
| 拦截方法 | `HTTPAdapter.send`（同步） | `AsyncClient.send`（异步） |
| 适用场景 | 传统同步 HTTP 调用 | 异步 HTTP 调用（如 LLM SDK） |
