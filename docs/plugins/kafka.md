# Kafka 插件使用手册

## 概述

Kafka 插件通过拦截 `kafka-python` 库的 Producer 和 Consumer 方法，对 Kafka 消息操作注入故障。

- **Producer** — 拦截 `kafka.KafkaProducer.send`
- **Consumer** — 拦截 `kafka.KafkaConsumer.poll`

两者共享相同的 target 参数（`kafka`），通过 `operation` 匹配器区分。

## 拦截点

| 角色 | 目标模块 | 目标类 | 目标方法 |
|------|---------|--------|---------|
| Producer | `kafka` | `KafkaProducer` | `send` |
| Consumer | `kafka` | `KafkaConsumer` | `poll` |

| 属性 | 值 |
|------|------|
| target 参数 | `kafka` |

## 匹配器（Matcher）

| 参数名 | 说明 | 示例 |
|--------|------|------|
| `topic` | Kafka Topic 名称 | `orders`, `user-events` |
| `operation` | 操作类型 | `produce`, `consume` |

> `operation` 由插件自动提取：Producer 操作为 `produce`，Consumer 操作为 `consume`。

## 支持的故障类型

### 1. 延迟注入（delay）

对 Kafka 操作注入指定时长的延迟。

**参数：**

| 参数名 | 必填 | 说明 |
|--------|------|------|
| `time` | 是 | 延迟时长（毫秒） |
| `offset` | 否 | 随机偏移范围（毫秒） |

**示例：**

```bash
# 对指定 Topic 的 Producer 发送注入 120ms 延迟
curl "http://127.0.0.1:9526/create?suid=kafka-delay-001&target=kafka&action=delay&time=120&topic=orders"

# 对所有 Consumer poll 注入 500ms 延迟
curl "http://127.0.0.1:9526/create?suid=kafka-delay-002&target=kafka&action=delay&time=500&operation=consume"

# 对所有 Kafka 操作注入 200ms 延迟
curl "http://127.0.0.1:9526/create?suid=kafka-delay-003&target=kafka&action=delay&time=200"
```

### 2. 异常注入（throwCustomException）

对 Kafka 操作抛出指定异常。

**参数：**

| 参数名 | 必填 | 说明 |
|--------|------|------|
| `exception` | 否 | 异常类名（如 `RuntimeError`, `KafkaError`） |
| `exception-message` | 否 | 异常消息内容 |

**示例：**

```bash
# 对指定 Topic 的 Producer 发送抛出异常
curl "http://127.0.0.1:9526/create?suid=kafka-exc-001&target=kafka&action=throwCustomException&exception=RuntimeError&exception-message=chaos:+broker+unavailable&topic=orders"

# 对所有 Consumer poll 抛出异常
curl "http://127.0.0.1:9526/create?suid=kafka-exc-002&target=kafka&action=throwCustomException&exception=RuntimeError&exception-message=chaos:+consumer+timeout&operation=consume"

# 对所有 Kafka 操作抛出异常
curl "http://127.0.0.1:9526/create?suid=kafka-exc-003&target=kafka&action=throwCustomException&exception=RuntimeError&exception-message=chaos:+kafka+cluster+down"
```

### 3. 返回值篡改（returnValue）

覆盖 Kafka 操作的返回值。

**参数：**

| 参数名 | 必填 | 说明 |
|--------|------|------|
| `return-value` | 否 | 返回值内容 |

**示例：**

```bash
# Producer.send 返回 null（丢弃消息）
curl "http://127.0.0.1:9526/create?suid=kafka-ret-001&target=kafka&action=returnValue&return-value=null&topic=events"

# Consumer.poll 返回空
curl "http://127.0.0.1:9526/create?suid=kafka-ret-002&target=kafka&action=returnValue&return-value=%7B%7D&operation=consume"
```

## 恢复（销毁实验）

```bash
curl "http://127.0.0.1:9526/destroy?suid=kafka-delay-001"
```

## 查看实验状态

```bash
curl "http://127.0.0.1:9526/status?suid=kafka-delay-001"
```

## 高级用法

### 按 Topic 精确注入

```bash
# 仅对 payment-events Topic 注入故障，其他 Topic 不受影响
curl "http://127.0.0.1:9526/create?suid=kafka-topic-001&target=kafka&action=throwCustomException&exception=RuntimeError&exception-message=payment+topic+error&topic=payment-events"
```

### 区分 Producer 和 Consumer

```bash
# 仅对 Producer 注入延迟（Consumer 不受影响）
curl "http://127.0.0.1:9526/create?suid=kafka-prod-001&target=kafka&action=delay&time=1000&operation=produce"

# 仅对 Consumer 注入异常（Producer 不受影响）
curl "http://127.0.0.1:9526/create?suid=kafka-cons-001&target=kafka&action=throwCustomException&exception=RuntimeError&exception-message=poll+failure&operation=consume"
```

### 限制注入次数

```bash
# 前 5 次消息发送失败，之后恢复
curl "http://127.0.0.1:9526/create?suid=kafka-limit-001&target=kafka&action=throwCustomException&exception=RuntimeError&exception-message=intermittent+failure&topic=orders&effect-count=5"
```

## 典型场景

| 场景 | 命令 |
|------|------|
| 模拟 Broker 不可达 | `target=kafka&action=throwCustomException&exception=RuntimeError&exception-message=broker+unavailable` |
| 模拟消息发送延迟 | `target=kafka&action=delay&time=5000&operation=produce` |
| 模拟消费者超时 | `target=kafka&action=throwCustomException&operation=consume` |
| 模拟消息丢失 | `target=kafka&action=returnValue&return-value=null&topic=orders` |
| 验证生产者重试 | `target=kafka&action=throwCustomException&effect-count=3&topic=orders` |
