![logo](https://chaosblade.oss-cn-hangzhou.aliyuncs.com/doc/image/chaosblade-logo.png)

# Chaosblade-exec-python: System Design

## Overview

Chaosblade-exec-python implements runtime fault injection through Python's MonkeyPatch + ImportHook mechanism. Under the hood it uses `sys.meta_path` to intercept module imports, and extends support for different Python application middleware through a pluggable plugin design. Plugins can be extended easily — see [How to Extend Plugins](../zh-cn/plugin.md).

## Architecture

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

## Module Management

### ChaosBladeAgent

As the entry point of the whole system (equivalent to the SandboxModule in the Java version), it coordinates the lifecycle of all subsystems:

1. Initialize the ManagerFactory (load all managers)
2. Install the ImportHook into `sys.meta_path`
3. Set up the PluginLifecycleListener (MonkeyPatch lifecycle)
4. Discover and load plugins through `entry_points`
5. Start the HTTP management server
6. Register signal handlers (SIGTERM / atexit)

### StatusManager

Manages the state of all experiments. An HTTP `/create` request, or a create command issued by the ChaosBlade main CLI, registers state in the StatusManager, including attack count, hit count, command parameters, and the attack method (Action).

### ModelSpecManager

Manages the ModelSpec of plugins, responsible for registering and looking up ModelSpecs. Each ModelSpec defines a target and the Actions and Matchers it supports.

### PluginManager

Manages the lifecycle of plugins and their loaded/unloaded state. When a `create` command is triggered, the corresponding plugin is lazily loaded.

### DispatchService

The HTTP request router that maps request paths to the corresponding RequestHandler:

| Command | Handler | Description |
|---------|---------|-------------|
| `/create` | CreateHandler | Create an experiment, register state, load plugin |
| `/destroy` | DestroyHandler | Destroy an experiment, remove state |
| `/status` | StatusHandler | Query the status of a given experiment |
| `/list` | ListHandler | List all active experiments |
| `/health` | HealthHandler | Health check |

## Implementation Principles

Take delay injection into Redis `execute_command` as an example:

### Experiment Steps

```bash
# 1. Generate the sitecustomize.py hook via attach
chaosblade-exec-python attach --target-dir /tmp/chaosblade-hook --port 9526

# 2. Start the target app with PYTHONPATH; the Agent starts inside the target process
PYTHONPATH="/tmp/chaosblade-hook:$PYTHONPATH" python your_app.py

# 3. Create a delay experiment
curl "http://127.0.0.1:9526/create?suid=abc123&target=redis&action=delay&time=3000&cmd=GET"

# 4. Destroy the experiment
curl http://127.0.0.1:9526/destroy?suid=abc123

# 5. Uninstall the hook after the drill
chaosblade-exec-python detach --target-dir /tmp/chaosblade-hook
```

### Agent Startup

The Agent must run inside the target Python process to take effect on the target application. Three startup methods are currently supported:

- **Non-intrusive attach (recommended)**: Generate `sitecustomize.py` via `chaosblade-exec-python attach`, then start the target app with `PYTHONPATH`;
- **Programmatic integration**: Manually create and start the Agent in the target application code;
- **Standalone process mode**: Start via `chaosblade-exec-python start`, used only for debugging the Agent itself; it cannot inject faults into other processes.

Programmatic integration example:

```python
from chaosblade import ChaosBladeAgent

agent = ChaosBladeAgent(port=9526)
agent.start()
```

After startup, the following steps execute:
1. `ManagerFactory.load()` — Initialize all managers
2. `ImportHook.install()` — Insert the hook into `sys.meta_path`
3. Set up `_PatchLifecycleListener` — Automatically install MonkeyPatch when a plugin loads
4. `PluginLoader.load_plugins()` — Discover all plugins via `entry_points` and register ModelSpecs
5. `start_server()` — Start the HTTP management server

### Plugin Loading

| Loading Method | Loading Condition |
|----------------|-------------------|
| Register ModelSpec at Agent startup | ModelSpec and ActionSpec registered to the manager |
| `create` command triggers lazy-load | The actual MonkeyPatch is installed only on the first create |

### MonkeyPatch Mechanism

Unlike the Java version's bytecode enhancement, the Python version uses MonkeyPatch to replace target methods:

```python
# MonkeyPatcher saves the original function reference
original = getattr(target_class, target_function)

# Replace with a wrapper
setattr(target_class, target_function, wrapper)
```

Internal flow of the wrapper:
1. `StatusManager.exp_exists(target)` — Check whether there is an active experiment
2. `Enhancer.extract_matchers()` — Extract matching parameters (such as cmd, key)
3. `Injector.inject()` — Parameter comparison + execute the fault capability

### ImportHook Lazy Loading

When the target module has not yet been imported, MonkeyPatch cannot be applied directly. ImportHook solves this problem:

```python
class ImportHook(MetaPathFinder):
    def find_spec(fullname, path, target=None):
        # If the module has pending patches
        # 1. Temporarily remove itself to avoid recursion
        # 2. Find the real ModuleSpec
        # 3. Wrap the real loader with _PostImportLoader
        # 4. Automatically apply patches after exec_module()
```

### Creating a Chaos Experiment

```
POST /create?suid=xxx&target=redis&action=delay&time=3000&cmd=GET
```

GET requests and POST JSON bodies are also supported; request parameters are parsed into a `Request` and then handed to the corresponding Handler.

CreateHandler processing flow:
1. Validate required parameters (suid, target, action)
2. Look up ModelSpec → look up ActionSpec
3. Parse request parameters into a Model (containing matcher + action flags)
4. Execute predicate validation
5. Register the experiment to the StatusManager
6. If it is a DirectlyInjectionAction → execute directly
7. Otherwise → lazy-load the plugin → install MonkeyPatch

### Fault Triggering

When a patched method is called:

```python
def wrapper(original_func, *args, **kwargs):
    # 1. Check whether there is an active experiment
    if not status_manager.exp_exists(target):
        return original_func(*args, **kwargs)

    # 2. Extract matcher parameters
    matchers = extractor(method_name, obj, args, kwargs)

    # 3. Compare experiment by experiment
    for metric in status_manager.get_exp_by_target(target):
        if compare(metric.model, matchers):
            # 4. Execute the fault capability
            metric.model.action_executor.run(enhancer_model)
            break

    return original_func(*args, **kwargs)
```

### Destroying an Experiment

```
GET /destroy?suid=xxx
```

DestroyHandler processing:
1. Look up the experiment by suid
2. Deregister from the StatusManager
3. If no other experiment shares the same target/action → the corresponding plugin can restore resources in its lifecycle hook

### Agent Shutdown

When the Agent stops (SIGTERM / atexit / manual `stop()` call):
1. Shut down the HTTP server
2. `MonkeyPatcher.remove_all()` — Restore all original methods
3. `ImportHook.uninstall()` — Remove from `sys.meta_path`
4. `ManagerFactory.unload()` — Clean up all manager state

## Running Mode Boundaries

Since the Python version relies on MonkeyPatch to replace object references within the current interpreter process, the Agent and the injected application must reside in the same Python process. The standalone process started by `chaosblade-exec-python start` can only validate the HTTP API, plugin loading, and lifecycle management; it cannot affect other application processes. For real business scenarios, `attach + PYTHONPATH` or programmatic integration is recommended.

## Correspondence with the Java Version

| Java Version | Python Version | Description |
|--------------|----------------|-------------|
| JVM-Sandbox + JavaAgent | sitecustomize.py + ImportHook + MonkeyPatch | Runtime injection mechanism |
| `-javaagent` attach | attach generates sitecustomize.py + PYTHONPATH | Non-intrusive attach method |
| Bytecode enhancement (transform) | MonkeyPatch (setattr) | Method interception method |
| SandboxModule | ChaosBladeAgent | System entry point |
| PointCut (ClassMatcher + MethodMatcher) | DefaultPointCut (module + class + function) | Interception point definition |
| Enhancer (Before/After) | DefaultBeforeEnhancer + extractor | Parameter extraction |
| SPI (ServiceLoader) | entry_points (setuptools) | Plugin discovery mechanism |
| Jetty HTTP Server | http.server.HTTPServer | Management interface |
| EventListener | wrapper function | Event callback |

## Related Documents

- [README (English)](../../README.md)
- [Quick Start (中文)](../zh-cn/quick-start.md)
- [Plugin Development Guide (中文)](../zh-cn/plugin.md)
- [系统设计 (中文)](../zh-cn/design.md)
