# ChaosBlade Exec Python

[English](../../README.md) | 简体中文

[ChaosBlade](https://chaosblade.io) 混沌工程实验执行器的 Python 实现，提供对 Python 应用的故障注入能力。

## 特性

- **零依赖核心** — 纯 Python 标准库实现，无第三方依赖
- **运行时注入** — 通过 MonkeyPatch 机制在运行时拦截目标方法
- **延迟加载** — ImportHook 自动在模块首次导入时应用 patch
- **插件化架构** — 通过 `entry_points` 发现和加载中间件插件
- **HTTP 管理接口** — 内置 HTTP Server 提供实验管理 API（GET/POST）
- **信号处理** — SIGTERM/atexit 优雅退出

## 支持的故障类型

| 故障类型 | 说明 |
|---------|------|
| `delay` | 方法级延迟注入（毫秒级，支持随机偏移） |
| `throwCustomException` | 抛出指定异常 |
| `returnValue` | 篡改返回值 |

## 支持的中间件插件

| 插件 | target | 目标模块 | 匹配器 | 使用手册 |
|------|--------|---------|--------|----------|
| Redis | `redis` | `redis.client.Redis` | cmd, key | [详细文档](../../docs/plugins/redis.md) |
| HTTP/Requests | `http` | `requests.adapters.HTTPAdapter` | url, method, host | [详细文档](../../docs/plugins/http-requests.md) |
| HTTPX | `httpx` | `httpx._client.AsyncClient` | url, method, host, path | [详细文档](../../docs/plugins/httpx.md) |
| MySQL (mysql-connector) | `mysql` | `mysql.connector.cursor` | sql, sqltype, database | [详细文档](../../docs/plugins/mysql.md) |
| MySQL (PyMySQL) | `mysql` | `pymysql.cursors` | sql, sqltype, database | [详细文档](../../docs/plugins/mysql.md) |
| gRPC | `grpc` | `grpc._channel` | service, method | [详细文档](../../docs/plugins/grpc.md) |
| Kafka Producer | `kafka` | `kafka.KafkaProducer` | topic, operation | [详细文档](../../docs/plugins/kafka.md) |
| Kafka Consumer | `kafka` | `kafka.KafkaConsumer` | topic, operation | [详细文档](../../docs/plugins/kafka.md) |
| SQLAlchemy | `sqlalchemy` | `sqlalchemy.engine.base` | sql, sqltype, database | [详细文档](../../docs/plugins/sqlalchemy.md) |

## 运行模式

> **核心约束**：Agent 通过 MonkeyPatch 拦截目标方法，**必须与目标应用运行在同一 Python 进程中**才能生效。

### 无侵入附加（推荐）

通过 Python 原生 `sitecustomize.py` 机制，Agent 随目标应用进程自动启动，**无需修改目标应用任何代码**：

```bash
# 1. 在目标应用的 virtualenv 中安装
pip install chaosblade-exec-python

# 2. 生成 sitecustomize.py 钩子（不修改目标应用代码）
chaosblade-exec-python attach --target-dir /tmp/chaosblade-hook --port 9526

# 3. 设置 PYTHONPATH 后启动目标应用，Agent 自动随进程启动
PYTHONPATH="/tmp/chaosblade-hook:$PYTHONPATH" python your_app.py

# 4. 验证 Agent 已启动
curl http://127.0.0.1:9526/health

# 5. 验收完毕后卸载钩子
chaosblade-exec-python detach --target-dir /tmp/chaosblade-hook
```

> **原理**：Python 启动时自动加载 `PYTHONPATH` 中的 `sitecustomize.py`，Agent 以后台线程在目标进程内启动，对目标应用的源码、配置、启动脚本零改动。
>
> **环境变量配置**（可选）：
> - `CHAOSBLADE_HOST` — Agent 监听地址（默认 `127.0.0.1`）
> - `CHAOSBLADE_PORT` — Agent 监听端口（默认 `9526`）

### 编程方式（需改动应用代码）

在应用代码中手动启动 Agent，适合对代码有控制权的场景：

```python
from chaosblade import ChaosBladeAgent

agent = ChaosBladeAgent(port=9526)
agent.start()

# ... 应用正常运行，Agent 在同进程中拦截目标方法 ...

agent.stop()
```

### 独立进程模式（仅用于开发调试）

```bash
chaosblade-exec-python start --port 9526
```

> ⚠️ 此模式 Agent 运行在独立进程中，**无法注入其他应用的故障**（MonkeyPatch 仅对当前进程生效）。仅适用于 Agent 本身的开发调试或功能验证。

## 安装

```bash
# 从源码安装
pip install -e .

# 或从 wheel 安装
pip install chaosblade-exec-python
```

## 管理 API

Agent 启动后通过 HTTP 接口管理实验：

```bash
# 创建实验：对 Redis GET 命令注入 500ms 延迟
curl "http://127.0.0.1:9526/create?suid=exp001&target=redis&action=delay&time=500&cmd=GET"

# 查询所有活跃实验
curl "http://127.0.0.1:9526/list"

# 查询单个实验命中次数
curl "http://127.0.0.1:9526/status?suid=exp001"

# 销毁实验
curl "http://127.0.0.1:9526/destroy?suid=exp001"

# 健康检查
curl "http://127.0.0.1:9526/health"
```

也支持 POST + JSON Body：

```bash
curl -X POST http://127.0.0.1:9526/create \
  -H "Content-Type: application/json" \
  -d '{"suid":"exp002","target":"redis","action":"throwCustomException","exception":"ConnectionError","exception-message":"chaos test"}'
```

## 通用参数说明

所有插件共享以下参数：

| 参数 | 说明 |
|------|------|
| `suid` | 实验唯一 ID（必填，用于后续查询/销毁） |
| `target` | 目标插件名（见上表 target 列） |
| `action` | 故障类型：`delay` / `throwCustomException` / `returnValue` |
| `time` | 延迟时长（毫秒，delay 专用） |
| `offset` | 随机偏移（毫秒，delay 专用） |
| `exception` | 异常类名（throwCustomException 专用） |
| `exception-message` | 异常消息（throwCustomException 专用） |
| `return-value` | 返回值（returnValue 专用） |
| `effect-count` | 限制注入次数（可选） |
| `effect-percent` | 按概率注入（可选，0-100） |

## 项目结构

```
src/chaosblade/
├── bootstrap/          # Agent 启动、ImportHook、MonkeyPatcher、插件加载
├── common/
│   ├── center/         # ManagerFactory、StatusManager、PluginManager
│   ├── injection/      # Injector 核心注入引擎
│   ├── model/          # Model、EnhancerModel、MatcherModel
│   └── transport/      # Request/Response
├── executor/           # DelayExecutor、ExceptionExecutor、ReturnExecutor
├── plugins/            # 中间件插件（redis、requests、httpx、mysql、grpc、kafka、sqlalchemy）
├── service/            # HTTP Server + Handler（create/destroy/status/list/health）
├── spi/                # 接口定义（Plugin、Enhancer、PointCut、ActionExecutor）
├── cli.py              # CLI 入口（start/status/attach/detach）
└── config.py           # 配置管理（ENV > File > Defaults）

docs/plugins/               # 各插件使用手册
├── redis.md
├── http-requests.md
├── httpx.md
├── mysql.md
├── grpc.md
├── kafka.md
└── sqlalchemy.md
```

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest

# 运行测试 + 覆盖率
pytest --cov=chaosblade --cov-report=html

# 构建 wheel
python -m build --wheel
```

## 架构对标

本项目对标 [chaosblade-exec-jvm](https://github.com/chaosblade-io/chaosblade-exec-jvm) 的架构设计：

| JVM 概念 | Python 对应 |
|---------|-------------|
| JVM Sandbox (moduleEventWatcher) | MonkeyPatcher |
| `-javaagent` 挂载 | sitecustomize.py + PYTHONPATH |
| Java ServiceLoader | setuptools entry_points |
| BeforeEnhancer | DefaultBeforeEnhancer |
| Injector.inject() | Injector.inject() |
| PluginLifecycleListener | _PatchLifecycleListener |

## 文档

- [快速入门](./quick-start.md)
- [系统设计](./design.md) | [Design (English)](../en/design.md)
- [插件开发指南](./plugin.md)

## License

[Apache License 2.0](../../LICENSE)
