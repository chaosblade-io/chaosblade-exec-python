# Redis 插件使用手册

## 概述

Redis 插件通过拦截 `redis.client.Redis.execute_command` 方法，对 Redis 操作注入故障。适用于使用 `redis-py` 库的 Python 应用。

## 拦截点

| 属性 | 值 |
|------|------|
| 目标模块 | `redis.client` |
| 目标类 | `Redis` |
| 目标方法 | `execute_command` |
| target 参数 | `redis` |

## 匹配器（Matcher）

| 参数名 | 说明 | 示例 |
|--------|------|------|
| `cmd` | Redis 命令名称（大写） | `GET`, `SET`, `HGET`, `DEL` |
| `key` | Redis 键名 | `user:1001`, `cache:token` |

> 匹配器为可选参数，不指定时对所有 Redis 操作生效。多个匹配器同时指定时，需全部满足才会触发注入。

## 支持的故障类型

### 1. 延迟注入（delay）

对 Redis 操作注入指定时长的延迟。

**参数：**

| 参数名 | 必填 | 说明 |
|--------|------|------|
| `time` | 是 | 延迟时长（毫秒） |
| `offset` | 否 | 随机偏移范围（毫秒），实际延迟 = time ± random(offset) |

**示例：**

```bash
# 对所有 SET 命令注入 500ms 延迟
curl "http://127.0.0.1:9526/create?suid=redis-delay-001&target=redis&action=delay&time=500&cmd=SET"

# 对指定 key 的 GET 命令注入 1000ms 延迟（±200ms 随机）
curl "http://127.0.0.1:9526/create?suid=redis-delay-002&target=redis&action=delay&time=1000&offset=200&cmd=GET&key=cache:token"
```

### 2. 异常注入（throwCustomException）

对 Redis 操作抛出指定异常。

**参数：**

| 参数名 | 必填 | 说明 |
|--------|------|------|
| `exception` | 否 | 异常类名（如 `ConnectionError`, `TimeoutError`, `RuntimeError`） |
| `exception-message` | 否 | 异常消息内容 |

**示例：**

```bash
# 对 GET 命令抛出 ConnectionError
curl "http://127.0.0.1:9526/create?suid=redis-exc-001&target=redis&action=throwCustomException&exception=ConnectionError&exception-message=chaos:+redis+connection+refused&cmd=GET"

# 对所有 Redis 操作抛出 TimeoutError
curl "http://127.0.0.1:9526/create?suid=redis-exc-002&target=redis&action=throwCustomException&exception=TimeoutError&exception-message=chaos:+redis+timeout"
```

### 3. 返回值篡改（returnValue）

覆盖 Redis 操作的返回值。

**参数：**

| 参数名 | 必填 | 说明 |
|--------|------|------|
| `return-value` | 否 | 返回值（支持 JSON、字符串、数字、布尔值、null） |

**return-value 解析规则：**
- `null` / `none` → Python `None`
- `true` / `false` → Python `True` / `False`
- 纯数字 → `int` 或 `float`
- 以 `{` 或 `[` 开头 → 解析为 JSON 对象/数组
- 其他 → 原始字符串

**示例：**

```bash
# GET 命令返回自定义缓存数据
curl "http://127.0.0.1:9526/create?suid=redis-ret-001&target=redis&action=returnValue&return-value=fake-cached-data&cmd=GET"

# GET 命令返回 null（模拟缓存未命中）
curl "http://127.0.0.1:9526/create?suid=redis-ret-002&target=redis&action=returnValue&return-value=null&cmd=GET"
```

## 恢复（销毁实验）

```bash
curl "http://127.0.0.1:9526/destroy?suid=redis-delay-001"
```

## 查看实验状态

```bash
curl "http://127.0.0.1:9526/status?suid=redis-delay-001"
```

返回示例：
```json
{"code": 200, "result": "{\"count\": 5}"}
```

## 高级用法

### 限制注入次数（effect-count）

```bash
# 仅对前 3 次 GET 命令注入异常，之后恢复正常
curl "http://127.0.0.1:9526/create?suid=redis-limit-001&target=redis&action=throwCustomException&exception=ConnectionError&exception-message=limited+fault&cmd=GET&effect-count=3"
```

### 按概率注入（effect-percent）

```bash
# 50% 概率对 SET 命令注入 200ms 延迟
curl "http://127.0.0.1:9526/create?suid=redis-pct-001&target=redis&action=delay&time=200&cmd=SET&effect-percent=50"
```

## 典型场景

| 场景 | 命令 |
|------|------|
| 模拟 Redis 连接断开 | `action=throwCustomException&exception=ConnectionError` |
| 模拟 Redis 响应超时 | `action=delay&time=5000` |
| 模拟缓存穿透（返回空） | `action=returnValue&return-value=null&cmd=GET` |
| 验证熔断器触发 | `action=throwCustomException&effect-count=5` |
