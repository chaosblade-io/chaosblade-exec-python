![logo](https://chaosblade.oss-cn-hangzhou.aliyuncs.com/doc/image/chaosblade-logo.png)

# Chaosblade-exec-python: 系统设计

## 概述

Chaosblade-exec-python 通过 Python 的 MonkeyPatch + ImportHook 机制实现运行时故障注入，底层使用 `sys.meta_path` 拦截模块导入，通过插件的可拔插设计来扩展对不同 Python 应用中间件的支持。可以方便地扩展插件，参考[如何扩展插件](./plugin.md)。

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                       HTTP API Layer                          │
│   GET/POST /create  /destroy  /status  /list  /health       │
├─────────────────────────────────────────────────────────────┤
│                     DispatchService                           │
│   CreateHandler │ DestroyHandler │ StatusHandler │ ...       │
├─────────────────────────────────────────────────────────────┤
│                    Core Components                            │
│  StatusManager │ ModelSpecManager │ PluginManager │ Listener │
├─────────────────────────────────────────────────────────────┤
│                    Injection Layer                            │
│       MonkeyPatcher  │  ImportHook  │  EnhancerFactory       │
├─────────────────────────────────────────────────────────────┤
│                      Plugin Layer                             │
│   Redis │ Requests │ HTTPX │ MySQL │ gRPC │ Kafka │ SQLAlchemy │
└─────────────────────────────────────────────────────────────┘
```

## 模块管理

### ChaosBladeAgent

作为整个系统的入口（等价于 Java 版的 SandboxModule），协调所有子系统的生命周期：

1. 初始化 ManagerFactory（加载各管理器）
2. 安装 ImportHook 到 `sys.meta_path`
3. 设置 PluginLifecycleListener（MonkeyPatch 生命周期）
4. 通过 `entry_points` 发现和加载插件
5. 启动 HTTP 管理服务器
6. 注册信号处理器（SIGTERM / atexit）

### StatusManager

管理所有实验的状态。HTTP `/create` 请求或 ChaosBlade 主 CLI 下发的 create 指令会在 StatusManager 注册状态，包含攻击次数、命中计数、命令参数、攻击方式（Action）等。

### ModelSpecManager

管理插件的 ModelSpec，负责 ModelSpec 的注册和查找。每个 ModelSpec 定义了一个 target 及其支持的 Action 和 Matcher。

### PluginManager

管理插件的生命周期，插件的加载与卸载状态。当 `create` 命令触发时，对应插件会被延迟加载。

### DispatchService

HTTP 请求路由器，将请求路径映射到对应的 RequestHandler 处理：

| 命令 | Handler | 说明 |
|------|---------|------|
| `/create` | CreateHandler | 创建实验，注册状态，加载插件 |
| `/destroy` | DestroyHandler | 销毁实验，移除状态 |
| `/status` | StatusHandler | 查询指定实验状态 |
| `/list` | ListHandler | 列出所有活跃实验 |
| `/health` | HealthHandler | 健康检查 |

## 实现原理

以 Redis 的 `execute_command` 延迟注入为例：

### 实验步骤

```bash
# 1. 通过 attach 生成 sitecustomize.py 钩子
chaosblade-exec-python attach --target-dir /tmp/chaosblade-hook --port 9526

# 2. 使用 PYTHONPATH 启动目标应用，Agent 在目标进程内自动启动
PYTHONPATH="/tmp/chaosblade-hook:$PYTHONPATH" python your_app.py

# 3. 创建延迟实验
curl "http://127.0.0.1:9526/create?suid=abc123&target=redis&action=delay&time=3000&cmd=GET"

# 4. 销毁实验
curl http://127.0.0.1:9526/destroy?suid=abc123

# 5. 验收完毕后卸载钩子
chaosblade-exec-python detach --target-dir /tmp/chaosblade-hook
```

### Agent 启动

Agent 必须运行在目标 Python 进程内才能对目标应用生效。当前支持三种启动方式：

- **无侵入附加（推荐）**：通过 `chaosblade-exec-python attach` 生成 `sitecustomize.py`，再使用 `PYTHONPATH` 启动目标应用；
- **编程集成**：在目标应用代码中手动创建并启动 Agent；
- **独立进程模式**：通过 `chaosblade-exec-python start` 启动，仅用于调试 Agent 自身，不能对其他进程注入故障。

编程集成示例：

```python
from chaosblade import ChaosBladeAgent

agent = ChaosBladeAgent(port=9526)
agent.start()
```

启动后执行：
1. `ManagerFactory.load()` — 初始化各管理器
2. `ImportHook.install()` — 将 hook 插入 `sys.meta_path`
3. 设置 `_PatchLifecycleListener` — 当插件加载时自动安装 MonkeyPatch
4. `PluginLoader.load_plugins()` — 通过 `entry_points` 发现所有插件并注册 ModelSpec
5. `start_server()` — 启动 HTTP 管理服务器

### Plugin 加载方式

| 加载方式 | 加载条件 |
|---------|---------|
| Agent 启动时注册 ModelSpec | ModelSpec 和 ActionSpec 注册到管理器 |
| `create` 命令触发 lazy-load | 实际的 MonkeyPatch 在首次 create 时才安装 |

### MonkeyPatch 机制

Python 版不同于 Java 的字节码增强，使用 MonkeyPatch 替换目标方法：

```python
# MonkeyPatcher 保存原始函数引用
original = getattr(target_class, target_function)

# 用 wrapper 替换
setattr(target_class, target_function, wrapper)
```

wrapper 内部流程：
1. `StatusManager.exp_exists(target)` — 检查是否有活跃实验
2. `Enhancer.extract_matchers()` — 提取匹配参数（如 cmd、key）
3. `Injector.inject()` — 参数比对 + 执行故障能力

### ImportHook 延迟加载

当目标模块尚未导入时，MonkeyPatch 无法直接应用。ImportHook 解决此问题：

```python
class ImportHook(MetaPathFinder):
    def find_spec(fullname, path, target=None):
        # 如果该模块有 pending patches
        # 1. 临时移除自身避免递归
        # 2. 找到真实的 ModuleSpec
        # 3. 用 _PostImportLoader 包装真实 loader
        # 4. 在 exec_module() 后自动应用 patches
```

### 创建混沌实验

```
POST /create?suid=xxx&target=redis&action=delay&time=3000&cmd=GET
```

也支持 GET 请求和 POST JSON Body；请求参数会被解析为 `Request` 后交给对应 Handler。

CreateHandler 处理流程：
1. 验证必要参数（suid、target、action）
2. 查找 ModelSpec → 查找 ActionSpec
3. 解析请求参数为 Model（包含 matcher + action flags）
4. 执行 predicate 校验
5. 注册实验到 StatusManager
6. 如果是 DirectlyInjectionAction → 直接执行
7. 否则 → lazy-load 插件 → 安装 MonkeyPatch

### 故障触发

当被 patch 的方法被调用时：

```python
def wrapper(original_func, *args, **kwargs):
    # 1. 检查是否有活跃实验
    if not status_manager.exp_exists(target):
        return original_func(*args, **kwargs)
    
    # 2. 提取匹配器参数
    matchers = extractor(method_name, obj, args, kwargs)
    
    # 3. 逐个实验比对
    for metric in status_manager.get_exp_by_target(target):
        if compare(metric.model, matchers):
            # 4. 执行故障能力
            metric.model.action_executor.run(enhancer_model)
            break
    
    return original_func(*args, **kwargs)
```

### 销毁实验

```
GET /destroy?suid=xxx
```

DestroyHandler 处理：
1. 通过 suid 查找实验
2. 从 StatusManager 注销
3. 如果没有同 target/action 的其他实验 → 对应插件可在生命周期钩子中恢复资源

### Agent 停止

Agent 停止时（SIGTERM / atexit / 手动调用 `stop()`）：
1. 关闭 HTTP Server
2. `MonkeyPatcher.remove_all()` — 恢复所有原始方法
3. `ImportHook.uninstall()` — 从 `sys.meta_path` 移除
4. `ManagerFactory.unload()` — 清理所有管理器状态

## 运行模式边界

由于 Python 版依赖 MonkeyPatch 替换当前解释器进程内的对象引用，Agent 与被注入应用必须位于同一 Python 进程中。`chaosblade-exec-python start` 启动的独立进程只能验证 HTTP API、插件加载和生命周期管理，不能影响其他应用进程；真实业务场景推荐使用 `attach + PYTHONPATH` 或编程集成方式。

## 与 Java 版的对应关系

| Java 版 | Python 版 | 说明 |
|---------|-----------|------|
| JVM-Sandbox + JavaAgent | sitecustomize.py + ImportHook + MonkeyPatch | 运行时注入机制 |
| `-javaagent` 挂载 | attach 生成 sitecustomize.py + PYTHONPATH | 无侵入附加方式 |
| 字节码增强 (transform) | MonkeyPatch (setattr) | 方法拦截方式 |
| SandboxModule | ChaosBladeAgent | 系统入口 |
| PointCut (ClassMatcher + MethodMatcher) | DefaultPointCut (module + class + function) | 拦截点定义 |
| Enhancer (Before/After) | DefaultBeforeEnhancer + extractor | 参数提取 |
| SPI (ServiceLoader) | entry_points (setuptools) | 插件发现机制 |
| Jetty HTTP Server | http.server.HTTPServer | 管理接口 |
| EventListener | wrapper function | 事件回调 |

## 相关文档

- [快速入门](./quick-start.md)
- [插件开发指南](./plugin.md)
- [插件使用手册索引](./README.md#支持的中间件插件)
