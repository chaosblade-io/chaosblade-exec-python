# SQLAlchemy 插件使用手册

## 概述

SQLAlchemy 插件通过拦截 `sqlalchemy.engine.base.Connection.execute` 方法，对通过 SQLAlchemy ORM 或 Core 执行的 SQL 操作注入故障。适用于所有使用 SQLAlchemy 作为数据库层的 Python 应用。

## 拦截点

| 属性 | 值 |
|------|------|
| 目标模块 | `sqlalchemy.engine.base` |
| 目标类 | `Connection` |
| 目标方法 | `execute` |
| target 参数 | `sqlalchemy` |

## 匹配器（Matcher）

| 参数名 | 说明 | 示例 |
|--------|------|------|
| `sql` | SQL 语句文本（包含匹配） | `SELECT`, `users`, `INSERT INTO orders` |
| `sqltype` | SQL 类型（首个关键词，大写） | `SELECT`, `INSERT`, `UPDATE`, `DELETE` |
| `database` | 数据库驱动/scheme | `postgresql`, `mysql`, `sqlite` |

> `database` 匹配器从 SQLAlchemy Engine 的 URL 中提取 drivername（如 `postgresql+psycopg2` 中的 `postgresql+psycopg2`）。

## 支持的故障类型

### 1. 延迟注入（delay）

对 SQL 执行注入指定时长的延迟。

**参数：**

| 参数名 | 必填 | 说明 |
|--------|------|------|
| `time` | 是 | 延迟时长（毫秒） |
| `offset` | 否 | 随机偏移范围（毫秒） |

**示例：**

```bash
# 对所有 SQL 注入 180ms 延迟
curl "http://127.0.0.1:9526/create?suid=sa-delay-001&target=sqlalchemy&action=delay&time=180"

# 仅对 SELECT 查询注入 500ms 延迟
curl "http://127.0.0.1:9526/create?suid=sa-delay-002&target=sqlalchemy&action=delay&time=500&sqltype=SELECT"

# 对 PostgreSQL 驱动的操作注入延迟
curl "http://127.0.0.1:9526/create?suid=sa-delay-003&target=sqlalchemy&action=delay&time=1000&database=postgresql"
```

### 2. 异常注入（throwCustomException）

对 SQL 执行抛出指定异常。

**参数：**

| 参数名 | 必填 | 说明 |
|--------|------|------|
| `exception` | 否 | 异常类名（如 `RuntimeError`, `OperationalError`） |
| `exception-message` | 否 | 异常消息内容 |

**示例：**

```bash
# 对所有 SQL 抛出异常
curl "http://127.0.0.1:9526/create?suid=sa-exc-001&target=sqlalchemy&action=throwCustomException&exception=RuntimeError&exception-message=chaos:+db+connection+pool+exhausted"

# 仅对 INSERT 操作抛出异常
curl "http://127.0.0.1:9526/create?suid=sa-exc-002&target=sqlalchemy&action=throwCustomException&exception=RuntimeError&exception-message=chaos:+write+permission+denied&sqltype=INSERT"

# 对包含特定表名的 SQL 抛出异常
curl "http://127.0.0.1:9526/create?suid=sa-exc-003&target=sqlalchemy&action=throwCustomException&exception=RuntimeError&exception-message=chaos:+table+not+found&sql=audit_logs"
```

### 3. 返回值篡改（returnValue）

覆盖 SQL 执行的返回值。

**参数：**

| 参数名 | 必填 | 说明 |
|--------|------|------|
| `return-value` | 否 | 返回值内容 |

**示例：**

```bash
# 所有查询返回空列表
curl "http://127.0.0.1:9526/create?suid=sa-ret-001&target=sqlalchemy&action=returnValue&return-value=%5B%5D"

# SELECT 返回 null
curl "http://127.0.0.1:9526/create?suid=sa-ret-002&target=sqlalchemy&action=returnValue&return-value=null&sqltype=SELECT"
```

## 恢复（销毁实验）

```bash
curl "http://127.0.0.1:9526/destroy?suid=sa-delay-001"
```

## 查看实验状态

```bash
curl "http://127.0.0.1:9526/status?suid=sa-delay-001"
```

## 高级用法

### 按 SQL 类型过滤

```bash
# 仅对写操作注入故障
curl "http://127.0.0.1:9526/create?suid=sa-write-001&target=sqlalchemy&action=throwCustomException&exception=RuntimeError&exception-message=write+failure&sqltype=INSERT"
curl "http://127.0.0.1:9526/create?suid=sa-write-002&target=sqlalchemy&action=throwCustomException&exception=RuntimeError&exception-message=write+failure&sqltype=UPDATE"
```

### 按数据库驱动过滤

```bash
# 仅对 PostgreSQL 注入故障（MySQL 不受影响）
curl "http://127.0.0.1:9526/create?suid=sa-pg-001&target=sqlalchemy&action=delay&time=3000&database=postgresql"
```

### 限制注入次数

```bash
# 前 10 次 SQL 执行注入延迟
curl "http://127.0.0.1:9526/create?suid=sa-limit-001&target=sqlalchemy&action=delay&time=500&effect-count=10"
```

## 与 MySQL 插件的区别

| 对比项 | MySQL 插件 | SQLAlchemy 插件 |
|--------|-----------|----------------|
| target 参数 | `mysql` | `sqlalchemy` |
| 拦截层 | 驱动层（cursor.execute） | ORM/Engine 层（Connection.execute） |
| 适用驱动 | mysql-connector / PyMySQL | 所有 SQLAlchemy 支持的数据库 |
| database 匹配 | 数据库名称 | 驱动名称（postgresql, mysql 等） |

> 如果应用同时使用 SQLAlchemy + MySQL 驱动，两个插件的实验可能会叠加生效。建议根据实际拦截需求选择一个使用。

## 典型场景

| 场景 | 命令 |
|------|------|
| 模拟数据库连接池耗尽 | `target=sqlalchemy&action=throwCustomException&exception=RuntimeError&exception-message=pool+exhausted` |
| 模拟慢查询 | `target=sqlalchemy&action=delay&time=5000&sqltype=SELECT` |
| 模拟事务提交失败 | `target=sqlalchemy&action=throwCustomException&sqltype=INSERT` |
| 模拟数据库响应超时 | `target=sqlalchemy&action=delay&time=30000` |
| 验证 ORM 查询降级 | `target=sqlalchemy&action=throwCustomException&effect-count=3` |
