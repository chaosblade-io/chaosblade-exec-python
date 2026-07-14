![logo](https://chaosblade.oss-cn-hangzhou.aliyuncs.com/doc/image/chaosblade-logo.png)

# Chaosblade-exec-python: 快速入门

## 介绍

该项目是 ChaosBlade 混沌工程平台的 Python 执行器，通过 MonkeyPatch 机制对 Python 应用程序进行运行时故障注入。支持通过 HTTP API 或 blade CLI 进行实验管理。

## 环境要求

- Python >= 3.9
- pip（推荐使用虚拟环境）

## 安装

### 从源码安装

```bash
git clone https://github.com/chaosblade-io/chaosblade-exec-python.git
cd chaosblade-exec-python
pip install -e ".[dev]"
```

### 从 PyPI 安装

```bash
pip install chaosblade-exec-python
```

### 从本地 wheel 包安装

```bash
python -m build --wheel
pip install dist/chaosblade_exec_python-*.whl
```

## 快速入门 — 无侵入附加模式（推荐）

Agent 通过 MonkeyPatch 注入故障，**必须运行在目标应用同一个 Python 进程内**才会影响目标应用。推荐使用 `attach` 生成 `sitecustomize.py` 钩子，再通过 `PYTHONPATH` 让 Agent 随目标应用启动。

### 生成附加钩子

```bash
# 在独立目录生成 sitecustomize.py 钩子
chaosblade-exec-python attach --target-dir /tmp/chaosblade-hook --port 9526

# 启动目标应用时加入该目录，Agent 会在目标进程内自动启动
PYTHONPATH="/tmp/chaosblade-hook:$PYTHONPATH" python your_app.py
```

### 验证 Agent

```bash
curl http://127.0.0.1:9526/health
```

返回示例：
```json
{
  "code": 200,
  "success": true,
  "result": {
    "status": "running",
    "active_experiments": 0,
    "registered_targets": 7
  }
}
```

### 创建混沌实验

对目标应用进程内的 Redis GET 操作注入 3 秒延迟：

```bash
curl "http://127.0.0.1:9526/create?suid=exp001&target=redis&action=delay&time=3000&cmd=GET"
```

返回：
```json
{"code": 200, "success": true, "result": "Model(target=redis, action=delay)"}
```

此后，目标应用进程内匹配 `cmd=GET` 的 Redis 操作会延迟 3 秒响应。

### 查看实验状态

```bash
# 查看单个实验命中次数
curl "http://127.0.0.1:9526/status?suid=exp001"

# 列出所有活跃实验
curl "http://127.0.0.1:9526/list"
```

### 销毁实验

```bash
# 按实验 ID 销毁
curl "http://127.0.0.1:9526/destroy?suid=exp001"

# 或按 target + action 批量销毁
curl "http://127.0.0.1:9526/destroy?target=redis&action=delay"
```

销毁后故障即停止，Redis 操作恢复正常。

### 卸载附加钩子

```bash
chaosblade-exec-python detach --target-dir /tmp/chaosblade-hook
```

## 快速入门 — 独立进程模式（仅用于开发调试）

```bash
chaosblade-exec-python start --port 9526 --debug
```

> ⚠️ 独立进程模式只会在独立 Agent 进程内安装 MonkeyPatch，**无法对其他 Python 应用进程注入故障**。该模式仅用于验证 Agent HTTP API、插件加载和生命周期管理，不适用于真实业务应用故障注入。

停止方式：

```bash
# 方式 1: Ctrl+C
# 方式 2: 发送 SIGTERM
kill -15 <pid>
```

Agent 停止时会恢复其所在进程内的 MonkeyPatch。

## 快速入门 — 编程集成模式

在 Python 应用中手动启动 Agent。该方式需要修改应用代码，适合需要深度集成 Agent 生命周期的场景：

```python
from chaosblade import ChaosBladeAgent

# 创建并启动 Agent
agent = ChaosBladeAgent(port=9526)
agent.start()

# ... 应用正常运行，Agent 在同一进程内拦截目标方法 ...

# 应用退出前停止 Agent（也可依赖 atexit 自动清理）
agent.stop()
```

## 快速入门 — 使用 ChaosBlade 主 CLI

如果已安装 [chaosblade](https://github.com/chaosblade-io/chaosblade) 主项目，可通过 `blade` CLI 连接已运行在目标进程内的 Python Agent。注意：`blade` 是 ChaosBlade 主项目命令，`chaosblade-exec-python` 是本项目提供的 Agent 管理命令。

```bash
# 确认 Python Agent 已运行
chaosblade-exec-python status --port 9526

# 创建实验：对 HTTP 请求注入 2 秒延迟
blade create http delay --time=2000 --url=/api/users --method=GET

# 查看实验
blade status --type create

# 销毁
blade destroy <uid>
```

## 支持的故障类型

| Action | 说明 | 必需参数 |
|--------|------|---------|
| `delay` | 方法延迟（毫秒） | `time` |
| `throwCustomException` | 抛出异常 | `exception` 或 `exception-message` |
| `returnValue` | 篡改返回值 | `return-value` |

## 支持的中间件插件

| Target | 拦截模块 | 拦截类/方法 | 匹配器 |
|--------|---------|-------------|--------|
| redis | `redis.client` | `Redis.execute_command` | cmd, key |
| http | `requests.adapters` | `HTTPAdapter.send` | url, method, host |
| httpx | `httpx._client` | `AsyncClient.send` | url, method, host, path |
| mysql | `mysql.connector.cursor` | `MySQLCursor.execute` | sql, sqltype, database |
| mysql | `pymysql.cursors` | `Cursor.execute` | sql, sqltype, database |
| grpc | `grpc._channel` | `_UnaryUnaryMultiCallable.__call__` | service, method |
| kafka | `kafka` | `KafkaProducer.send` / `KafkaConsumer.poll` | topic, operation |
| sqlalchemy | `sqlalchemy.engine.base` | `Connection.execute` | sql, sqltype, database |

## POST 请求方式

除 GET 外，也支持 POST + JSON Body：

```bash
curl -X POST http://127.0.0.1:9526/create \
  -H "Content-Type: application/json" \
  -d '{
    "suid": "exp002",
    "target": "http",
    "action": "delay",
    "time": "2000",
    "url": "/api/users"
  }'
```

## 调试模式

在 create 请求中添加 `debug=true` 可开启详细日志：

```bash
curl "http://127.0.0.1:9526/create?suid=exp001&target=redis&action=delay&time=3000&debug=true"
```

## 健康检查

```bash
curl http://127.0.0.1:9526/health
```

返回示例：
```json
{
  "code": 200,
  "success": true,
  "result": {
    "status": "running",
    "uptime_seconds": 10,
    "python_version": "3.12.0",
    "platform": "Darwin-...",
    "active_experiments": 0,
    "registered_targets": 7
  }
}
```

## 相关文档

- [系统设计](./design.md)
- [插件开发指南](./plugin.md)
- [插件使用手册索引](./README.md#支持的中间件插件)

## 常见问题

### 1. 模块尚未导入时 patch 不生效？

这是正常的。Agent 使用 ImportHook 机制，当目标模块（如 `redis.client`）首次被导入时会自动应用 patch。确保在应用导入目标库之前启动 Agent。

### 2. 如何确认 patch 已安装？

通过 `/list` 接口查看活跃实验，或查看 Agent 日志中的 "Deferred patch applied" 信息。

### 3. 多个实验可以叠加吗？

可以。同一 target 可以有多个实验（不同 matcher），它们按顺序匹配，第一个匹配成功的实验会被触发。
