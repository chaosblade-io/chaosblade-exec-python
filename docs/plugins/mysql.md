# MySQL 插件使用手册

## 概述

MySQL 插件通过拦截数据库游标的 `execute` 方法，对 SQL 操作注入故障。支持两种 MySQL 驱动：
- **mysql-connector-python** — 拦截 `mysql.connector.cursor.MySQLCursor.execute`
- **PyMySQL** — 拦截 `pymysql.cursors.Cursor.execute`

两种驱动共享相同的 target 参数（`mysql`），会同时生效。

## 拦截点

| 驱动 | 目标模块 | 目标类 | 目标方法 |
|------|---------|--------|---------|
| mysql-connector-python | `mysql.connector.cursor` | `MySQLCursor` | `execute` |
| PyMySQL | `pymysql.cursors` | `Cursor` | `execute` |

| 属性 | 值 |
|------|------|
| target 参数 | `mysql` |

## 匹配器（Matcher）

| 参数名 | 说明 | 示例 |
|--------|------|------|
| `sql` | SQL 语句文本（包含匹配） | `SELECT * FROM users` |
| `sqltype` | SQL 类型（首个关键词，大写） | `SELECT`, `INSERT`, `UPDATE`, `DELETE` |
| `database` | 数据库名称 | `mydb`, `production` |

> 匹配器为可选参数。`sql` 匹配器通过包含关系匹配（实际 SQL 中包含指定文本即命中）。

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
# 对所有 SQL 注入 150ms 延迟
curl "http://127.0.0.1:9526/create?suid=mysql-delay-001&target=mysql&action=delay&time=150"

# 仅对 SELECT 查询注入 500ms 延迟
curl "http://127.0.0.1:9526/create?suid=mysql-delay-002&target=mysql&action=delay&time=500&sqltype=SELECT"

# 对指定数据库的操作注入 1000ms 延迟
curl "http://127.0.0.1:9526/create?suid=mysql-delay-003&target=mysql&action=delay&time=1000&database=production"
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
curl "http://127.0.0.1:9526/create?suid=mysql-exc-001&target=mysql&action=throwCustomException&exception=RuntimeError&exception-message=chaos:+database+unavailable"

# 仅对 INSERT 操作抛出异常
curl "http://127.0.0.1:9526/create?suid=mysql-exc-002&target=mysql&action=throwCustomException&exception=RuntimeError&exception-message=chaos:+write+denied&sqltype=INSERT"

# 对包含特定表名的 SQL 抛出异常
curl "http://127.0.0.1:9526/create?suid=mysql-exc-003&target=mysql&action=throwCustomException&exception=RuntimeError&exception-message=chaos:+table+locked&sql=orders"
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
curl "http://127.0.0.1:9526/create?suid=mysql-ret-001&target=mysql&action=returnValue&return-value=%5B%5D"

# UPDATE/INSERT 返回 0（表示未影响任何行）
curl "http://127.0.0.1:9526/create?suid=mysql-ret-002&target=mysql&action=returnValue&return-value=0&sqltype=UPDATE"
```

## 恢复（销毁实验）

```bash
curl "http://127.0.0.1:9526/destroy?suid=mysql-delay-001"
```

## 查看实验状态

```bash
curl "http://127.0.0.1:9526/status?suid=mysql-delay-001"
```

## 高级用法

### 按 SQL 类型过滤

```bash
# 仅对写操作（INSERT/UPDATE/DELETE）注入延迟
curl "http://127.0.0.1:9526/create?suid=mysql-write-001&target=mysql&action=delay&time=2000&sqltype=INSERT"
curl "http://127.0.0.1:9526/create?suid=mysql-write-002&target=mysql&action=delay&time=2000&sqltype=UPDATE"
curl "http://127.0.0.1:9526/create?suid=mysql-write-003&target=mysql&action=delay&time=2000&sqltype=DELETE"
```

### 按数据库名过滤

```bash
# 仅对 production 库注入故障
curl "http://127.0.0.1:9526/create?suid=mysql-db-001&target=mysql&action=throwCustomException&exception=RuntimeError&exception-message=production+db+error&database=production"
```

### 限制注入次数

```bash
# 前 10 次查询注入延迟，之后恢复正常
curl "http://127.0.0.1:9526/create?suid=mysql-limit-001&target=mysql&action=delay&time=500&effect-count=10"
```

## 典型场景

| 场景 | 命令 |
|------|------|
| 模拟数据库连接异常 | `target=mysql&action=throwCustomException&exception=RuntimeError&exception-message=connection+refused` |
| 模拟慢查询 | `target=mysql&action=delay&time=5000&sqltype=SELECT` |
| 模拟写入失败 | `target=mysql&action=throwCustomException&sqltype=INSERT` |
| 模拟空结果集 | `target=mysql&action=returnValue&return-value=%5B%5D&sqltype=SELECT` |
| 验证连接池耗尽 | `target=mysql&action=delay&time=30000` |
