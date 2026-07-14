# gRPC 插件使用手册

## 概述

gRPC 插件通过拦截 `grpc._channel._UnaryUnaryMultiCallable.__call__` 方法，对 gRPC Unary-Unary 调用注入故障。适用于使用 `grpcio` 库的 Python 应用。

## 拦截点

| 属性 | 值 |
|------|------|
| 目标模块 | `grpc._channel` |
| 目标类 | `_UnaryUnaryMultiCallable` |
| 目标方法 | `__call__` |
| target 参数 | `grpc` |

## 匹配器（Matcher）

| 参数名 | 说明 | 示例 |
|--------|------|------|
| `method` | gRPC 方法完整路径 | `/package.Service/Method` |
| `service` | gRPC 服务名称 | `package.Service` |

> gRPC 方法路径格式为 `/package.ServiceName/MethodName`，service 会自动从 method 中提取。

## 支持的故障类型

### 1. 延迟注入（delay）

对 gRPC 调用注入指定时长的延迟。

**参数：**

| 参数名 | 必填 | 说明 |
|--------|------|------|
| `time` | 是 | 延迟时长（毫秒） |
| `offset` | 否 | 随机偏移范围（毫秒） |

**示例：**

```bash
# 对所有 gRPC 调用注入 100ms 延迟
curl "http://127.0.0.1:9526/create?suid=grpc-delay-001&target=grpc&action=delay&time=100"

# 对指定服务注入 500ms 延迟
curl "http://127.0.0.1:9526/create?suid=grpc-delay-002&target=grpc&action=delay&time=500&service=user.UserService"

# 对指定方法注入 1000ms 延迟
curl "http://127.0.0.1:9526/create?suid=grpc-delay-003&target=grpc&action=delay&time=1000&method=/user.UserService/GetUser"
```

### 2. 异常注入（throwCustomException）

对 gRPC 调用抛出指定异常。

**参数：**

| 参数名 | 必填 | 说明 |
|--------|------|------|
| `exception` | 否 | 异常类名（如 `RuntimeError`, `RpcError`） |
| `exception-message` | 否 | 异常消息内容 |

**示例：**

```bash
# 对所有 gRPC 调用抛出异常
curl "http://127.0.0.1:9526/create?suid=grpc-exc-001&target=grpc&action=throwCustomException&exception=RuntimeError&exception-message=chaos:+grpc+unavailable"

# 对指定服务抛出异常
curl "http://127.0.0.1:9526/create?suid=grpc-exc-002&target=grpc&action=throwCustomException&exception=RuntimeError&exception-message=chaos:+service+not+found&service=order.OrderService"

# 对指定方法抛出异常
curl "http://127.0.0.1:9526/create?suid=grpc-exc-003&target=grpc&action=throwCustomException&exception=RuntimeError&exception-message=chaos:+permission+denied&method=/auth.AuthService/Verify"
```

### 3. 返回值篡改（returnValue）

覆盖 gRPC 调用的返回值。

**参数：**

| 参数名 | 必填 | 说明 |
|--------|------|------|
| `return-value` | 否 | 返回值内容（JSON 格式） |

**示例：**

```bash
# 返回 mock 数据
curl "http://127.0.0.1:9526/create?suid=grpc-ret-001&target=grpc&action=returnValue&return-value=%7B%22result%22%3A+%22mock%22%7D"

# 对指定方法返回 null
curl "http://127.0.0.1:9526/create?suid=grpc-ret-002&target=grpc&action=returnValue&return-value=null&method=/user.UserService/GetUser"
```

## 恢复（销毁实验）

```bash
curl "http://127.0.0.1:9526/destroy?suid=grpc-delay-001"
```

## 查看实验状态

```bash
curl "http://127.0.0.1:9526/status?suid=grpc-delay-001"
```

## 高级用法

### 按服务过滤

```bash
# 仅对 OrderService 的所有方法注入延迟
curl "http://127.0.0.1:9526/create?suid=grpc-svc-001&target=grpc&action=delay&time=2000&service=order.OrderService"
```

### 限制注入次数

```bash
# 前 3 次调用注入异常（验证重试逻辑）
curl "http://127.0.0.1:9526/create?suid=grpc-limit-001&target=grpc&action=throwCustomException&exception=RuntimeError&exception-message=transient+failure&effect-count=3"
```

## 典型场景

| 场景 | 命令 |
|------|------|
| 模拟 gRPC 服务不可达 | `target=grpc&action=throwCustomException&exception=RuntimeError&exception-message=UNAVAILABLE` |
| 模拟 RPC 超时 | `target=grpc&action=delay&time=30000` |
| 模拟权限校验失败 | `target=grpc&action=throwCustomException&service=auth.AuthService` |
| 验证降级逻辑 | `target=grpc&action=throwCustomException&effect-count=5&service=recommend.Service` |

## 注意事项

- 当前仅拦截 **Unary-Unary** 调用模式（最常见的 gRPC 调用方式）
- Streaming 调用（Server Streaming / Client Streaming / Bidi Streaming）暂不支持
- gRPC 方法路径中的 `method` 参数需包含完整路径（如 `/package.Service/Method`），不能只写方法名
