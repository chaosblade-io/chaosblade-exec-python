# ChaosBlade Exec Python

English | [简体中文](doc/zh-cn/README.md)

The Python implementation of the [ChaosBlade](https://chaosblade.io) chaos engineering experiment executor, providing fault injection capabilities for Python applications.

## Features

- **Zero-dependency core** — Implemented with the pure Python standard library, no third-party dependencies
- **Runtime injection** — Intercepts target methods at runtime via a MonkeyPatch mechanism
- **Lazy loading** — ImportHook automatically applies patches the first time a module is imported
- **Plugin architecture** — Discovers and loads middleware plugins through `entry_points`
- **HTTP management API** — Built-in HTTP server exposes experiment management APIs (GET/POST)
- **Signal handling** — Graceful shutdown via SIGTERM/atexit

## Supported Fault Types

| Fault Type | Description |
|------------|-------------|
| `delay` | Method-level delay injection (millisecond precision, supports random offset) |
| `throwCustomException` | Throws a specified exception |
| `returnValue` | Tampers with the return value |

## Supported Middleware Plugins

| Plugin | target | Target Module | Matchers | Guide |
|--------|--------|---------------|----------|-------|
| Redis | `redis` | `redis.client.Redis` | cmd, key | [Docs](docs/plugins/redis.md) |
| HTTP/Requests | `http` | `requests.adapters.HTTPAdapter` | url, method, host | [Docs](docs/plugins/http-requests.md) |
| HTTPX | `httpx` | `httpx._client.AsyncClient` | url, method, host, path | [Docs](docs/plugins/httpx.md) |
| MySQL (mysql-connector) | `mysql` | `mysql.connector.cursor` | sql, sqltype, database | [Docs](docs/plugins/mysql.md) |
| MySQL (PyMySQL) | `mysql` | `pymysql.cursors` | sql, sqltype, database | [Docs](docs/plugins/mysql.md) |
| gRPC | `grpc` | `grpc._channel` | service, method | [Docs](docs/plugins/grpc.md) |
| Kafka Producer | `kafka` | `kafka.KafkaProducer` | topic, operation | [Docs](docs/plugins/kafka.md) |
| Kafka Consumer | `kafka` | `kafka.KafkaConsumer` | topic, operation | [Docs](docs/plugins/kafka.md) |
| SQLAlchemy | `sqlalchemy` | `sqlalchemy.engine.base` | sql, sqltype, database | [Docs](docs/plugins/sqlalchemy.md) |

## Running Modes

> **Core constraint**: The Agent intercepts target methods via MonkeyPatch, so it **must run in the same Python process as the target application** to take effect.

### Non-intrusive Attach (Recommended)

Using Python's native `sitecustomize.py` mechanism, the Agent starts automatically with the target application process, **without modifying any code of the target application**:

```bash
# 1. Install into the target application's virtualenv
pip install chaosblade-exec-python

# 2. Generate the sitecustomize.py hook (does not modify target app code)
chaosblade-exec-python attach --target-dir /tmp/chaosblade-hook --port 9526

# 3. Start the target app with PYTHONPATH set; the Agent starts with the process
PYTHONPATH="/tmp/chaosblade-hook:$PYTHONPATH" python your_app.py

# 4. Verify the Agent is running
curl http://127.0.0.1:9526/health

# 5. Uninstall the hook after the drill
chaosblade-exec-python detach --target-dir /tmp/chaosblade-hook
```

> **How it works**: On startup, Python automatically loads `sitecustomize.py` from `PYTHONPATH`. The Agent starts as a background thread inside the target process, with zero changes to the target application's source code, configuration, or startup scripts.
>
> **Environment variables** (optional):
> - `CHAOSBLADE_HOST` — Agent listening address (default `127.0.0.1`)
> - `CHAOSBLADE_PORT` — Agent listening port (default `9526`)

### Programmatic (Requires Application Code Changes)

Start the Agent manually in the application code, suitable when you control the code:

```python
from chaosblade import ChaosBladeAgent

agent = ChaosBladeAgent(port=9526)
agent.start()

# ... the application runs normally, the Agent intercepts target methods in the same process ...

agent.stop()
```

### Standalone Process Mode (Development/Debugging Only)

```bash
chaosblade-exec-python start --port 9526
```

> ⚠️ In this mode the Agent runs in a standalone process and **cannot inject faults into other applications** (MonkeyPatch only affects the current process). It is only intended for developing/debugging the Agent itself or feature validation.

## Installation

```bash
# Install from source
pip install -e .

# Or install from wheel
pip install chaosblade-exec-python
```

## Management API

Once the Agent is running, manage experiments over the HTTP interface:

```bash
# Create an experiment: inject 500ms delay into the Redis GET command
curl "http://127.0.0.1:9526/create?suid=exp001&target=redis&action=delay&time=500&cmd=GET"

# List all active experiments
curl "http://127.0.0.1:9526/list"

# Query hit count of a single experiment
curl "http://127.0.0.1:9526/status?suid=exp001"

# Destroy an experiment
curl "http://127.0.0.1:9526/destroy?suid=exp001"

# Health check
curl "http://127.0.0.1:9526/health"
```

POST + JSON body is also supported:

```bash
curl -X POST http://127.0.0.1:9526/create \
  -H "Content-Type: application/json" \
  -d '{"suid":"exp002","target":"redis","action":"throwCustomException","exception":"ConnectionError","exception-message":"chaos test"}'
```

## Common Parameters

All plugins share the following parameters:

| Parameter | Description |
|-----------|-------------|
| `suid` | Unique experiment ID (required, used for later query/destroy) |
| `target` | Target plugin name (see the target column above) |
| `action` | Fault type: `delay` / `throwCustomException` / `returnValue` |
| `time` | Delay duration (milliseconds, for delay only) |
| `offset` | Random offset (milliseconds, for delay only) |
| `exception` | Exception class name (for throwCustomException only) |
| `exception-message` | Exception message (for throwCustomException only) |
| `return-value` | Return value (for returnValue only) |
| `effect-count` | Limit the number of injections (optional) |
| `effect-percent` | Inject by probability (optional, 0-100) |

## Project Structure

```
src/chaosblade/
├── bootstrap/          # Agent startup, ImportHook, MonkeyPatcher, plugin loading
├── common/
│   ├── center/         # ManagerFactory, StatusManager, PluginManager
│   ├── injection/      # Injector core injection engine
│   ├── model/          # Model, EnhancerModel, MatcherModel
│   └── transport/      # Request/Response
├── executor/           # DelayExecutor, ExceptionExecutor, ReturnExecutor
├── plugins/            # Middleware plugins (redis, requests, httpx, mysql, grpc, kafka, sqlalchemy)
├── service/            # HTTP server + handlers (create/destroy/status/list/health)
├── spi/                # Interface definitions (Plugin, Enhancer, PointCut, ActionExecutor)
├── cli.py              # CLI entry (start/status/attach/detach)
└── config.py           # Configuration management (ENV > File > Defaults)

docs/plugins/               # Per-plugin usage guides
├── redis.md
├── http-requests.md
├── httpx.md
├── mysql.md
├── grpc.md
├── kafka.md
└── sqlalchemy.md
```

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=chaosblade --cov-report=html

# Build wheel
python -m build --wheel
```

## Architecture Alignment

This project aligns with the architecture design of [chaosblade-exec-jvm](https://github.com/chaosblade-io/chaosblade-exec-jvm):

| JVM Concept | Python Counterpart |
|-------------|--------------------|
| JVM Sandbox (moduleEventWatcher) | MonkeyPatcher |
| `-javaagent` attach | sitecustomize.py + PYTHONPATH |
| Java ServiceLoader | setuptools entry_points |
| BeforeEnhancer | DefaultBeforeEnhancer |
| Injector.inject() | Injector.inject() |
| PluginLifecycleListener | _PatchLifecycleListener |

## Documentation

- [Quick Start (中文)](doc/zh-cn/quick-start.md)
- [Design (English)](doc/en/design.md) | [设计文档 (中文)](doc/zh-cn/design.md)
- [Plugin Development (中文)](doc/zh-cn/plugin.md)

## License

[Apache License 2.0](LICENSE)
